import unrealsdk
from unrealsdk import find_object
import sys
import random
import json
import os
import asyncio
import time
from pathlib import Path
from ..ModManager import BL2MOD, RegisterMod
from Mods.ModMenu import Game, Hook
from mods_base import command, build_mod
import command_extensions
from .Locations import id_lookup_table, boss_lookup_table

SKILL_POINTS = find_object("AttributeInitializationDefinition", "GD_Globals.Skills.INI_SkillPointsPerLevelUp")

class Archipelago(BL2MOD):
    Name: str = "Archipelago"
    Description: str = "Archipelago!"
    Version: str = "0.0"
    Author: str = "Metrax"
    SupportedGames = Game.BL2
    LocalModDir: str = os.path.dirname(os.path.realpath(__file__))
    _last_known_level = 0

    def __init__(self):
        if "localappdata" in os.environ:
            self.game_communication_path = os.path.expandvars(r"%localappdata%/BL2Archipelago")
        else:
            self.game_communication_path = os.path.expandvars(r"$HOME/BL2Archipelago")
        
        if not os.path.exists(self.game_communication_path):
            unrealsdk.Log(f"[Archipelago] Path {self.game_communication_path} does not exist. Please start the archipelago client first.")
            
        self.savefile_bindings_path = os.path.join(self.game_communication_path, "savefile_bindings.json")
        if not os.path.exists(self.savefile_bindings_path):
            unrealsdk.Log(f"[Archipelago] savefile_bindings.json not found. Please start the archipelago client first.")
            return

        self.reset()

    def reset(self):
        self.player_loaded = False
        self.config = False
        self.connected = False
        self.completed_checks = set()

    def get_seed_path(self):
        if not self.seed:
            return None

        return os.path.join(self.game_communication_path, str(self.seed))

    def is_player_in_game(self):
        try:
            # Check if player controller exists
            pc = unrealsdk.GetEngine().GamePlayers[0].Actor
            if not pc:
                return False
                
            # Check if not in main menu
            world_info = unrealsdk.GetEngine().GetCurrentWorldInfo()
            map_name = world_info.GetStreamingPersistentMapName().lower()
            if map_name == "menumap":
                return False
                
            # Check if player pawn exists (character is spawned)
            pawn = pc.Pawn
            return pawn is not None
            
        except (IndexError, AttributeError):
            return False

    def send_check(self, check_id, check_name):
        if check_id in self.completed_checks:
            return
            
        check_data = {
            "type": "check",
            "id": check_id,
            "name": check_name,
            "timestamp": time.time()
        }
        
        check_file = os.path.join(self.get_seed_path(), f"check{check_id}.json")
        with open(check_file, 'w') as f:
            json.dump(check_data, f)
            
        self.completed_checks.add(check_id)
        unrealsdk.Log(f"[Archipelago] Check completed: {check_name}")

    def Enable(self):
        unrealsdk.Log(f"[Archipelago] Hello!")
        super().Enable()

    def Disable(self):
        unrealsdk.Log(f"[Archipelago] Bye bye!")
        super().Disable()

    @Hook("WillowGame.WillowPlayerController.PlayerTick")
    def PlayerTick(self, caller: unrealsdk.UObject, function: unrealsdk.UFunction, params: unrealsdk.FStruct) -> bool:
        if self.is_player_in_game() and self.connected and self.config:
            return True

        return True

    @Hook("WillowGame.WillowPlayerController.WillowClientDisableLoadingMovie")
    def on_loading_complete(self, caller, function, params):
        self.player_loaded = True
        unrealsdk.Log(f"[Archipelago] Player Loaded: {self.player_loaded}")

        if not self.connected:
            self.connect_to_archipelago()

        if not self.config:
            self.load_config()

        self.disable_skillpoints_on_levelup()

        return True

    @Hook("WillowGame.WillowPlayerController:LoadTheBank")
    def check_level_change(self, caller, function, params):
        current_level = caller.PlayerReplicationInfo.ExpLevel
        if current_level > self._last_known_level:
            unrealsdk.Log(f"[Archipelago] Player Level Up: {self._last_known_level} -> {current_level}")
            self._last_known_level = current_level

    @Hook("WillowGame.WillowPlayerController.CompleteQuitToMenu")
    def on_disconnect(self, caller, function, params):
        self.reset()
        unrealsdk.Log(f"[Archipelago] Player disconnected: {self.player_loaded}")
        return True

    @Hook("WillowGame.WillowPlayerPawn.PickupInventory")
    def on_pickup_inventory(self, caller, function, params):
        unrealsdk.Log(f"[Archipelago] on_pickup_inventory: {params}")
        if self.is_player_in_game():
            # Example: Send check for picking up any item
            # You'd want to filter this based on specific items
            item_name = "Unknown Item"  # Extract actual item name from params
            self.send_check(f"pickup_{item_name}", f"Picked up {item_name}")
        return True

    @Hook("WillowGame.MissionTracker.SetMissionStatus")
    def on_mission_status_change(self, caller, function, params):
        unrealsdk.Log(f"[Archipelago] on_mission_status_change: {params}")
        if self.is_player_in_game():
            # Check if mission was completed
            # params.NewStatus would indicate completion
            mission_name = "Unknown Mission"  # Extract from params
            self.send_check(f"mission_{mission_name}", f"Completed {mission_name}")
        return True

    @Hook("WillowGame.WillowPawn.Died")
    def on_enemy_died(self, caller, function, params):
        # Check if it's a boss or important enemy
        # Send boss defeat check
        if caller.IsChampion() or caller.IsBoss():
            name, *_ = caller.GetTargetName()

            if name not in boss_lookup_table:
                return False

            check_name = f"Kill {name}"
            check_id = id_lookup_table[check_name]

            unrealsdk.Log(f"[Archipelago] on_enemy_died: {name}")
            self.send_check(check_id, check_name)
            
        return True

    def disable_skillpoints_on_levelup(self):
        unrealsdk.Log(f"[Archipelago] Disabling vanilla skillpoints {SKILL_POINTS}!")
        expression_list = SKILL_POINTS.ConditionalInitialization.ConditionalExpressionList
        if expression_list:
            expression = expression_list[0].Expressions
            if expression:
                expression[0].ConstantOperand2 = 999

    def connect_to_archipelago(self):
        savefile_bindings = []
        try:
            with open(self.savefile_bindings_path, 'r') as f:
                savefile_bindings = json.load(f)
        except OSError:
            unrealsdk.Log(f"[Archipelago] Could not read file: {self.savefile_bindings_path}")
            return

        if not self.is_connected_to_seed(savefile_bindings):
            unrealsdk.Log(f"[Archipelago] Savefile not connected to any seed. Connecting..")
            self.establish_new_connection(savefile_bindings)

        unrealsdk.Log(f"[Archipelago] Savefile connected.")

        self.connected = True

    def is_connected_to_seed(self, savefile_bindings):
        savefile_id = self.get_savefile_id()

        for b in savefile_bindings:
            if b["save_file"] == savefile_id:
                self.seed = b["seed"]
                return True

        return False    

    def establish_new_connection(self, savefile_bindings):
        binding = -1
        for i, b in enumerate(savefile_bindings):
            if b["seed"] and not b["save_file"]:
                binding = i
                break

        if binding < 0:
            unrealsdk.Log(f"[Archipelago] Could not find empty seed.")
            return
        else:
            savefile_bindings[binding]["save_file"] = self.get_savefile_id()

        try:
            with open(self.savefile_bindings_path, 'w') as f:
                json.dump(savefile_bindings, f)

            self.seed = savefile_bindings[binding]["seed"]
            unrealsdk.Log(f"[Archipelago] Connected seed {savefile_bindings[binding]["seed"]} to savefile {savefile_bindings[binding]["save_file"]}")
        except OSError:
            logger.warning(f"Could not write file: {self.savefile_bindings_path}")

    def get_savefile_id(self):
        pc = unrealsdk.GetEngine().GamePlayers[0].Actor
        if pc == None:
            return None
        
        save_game = pc.GetCachedSaveGame()

        if not save_game:
            return None
        
        return save_game.SaveGameId

    def load_config(self):
        config_path = os.path.join(self.get_seed_path(), "config.json")
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except OSError:
            unrealsdk.Log(f"[Archipelago] Could not read file: {config_path}")

def get_player_controller():
    """
    Get the current WillowPlayerController Object.
    :return: WillowPlayerController
    """
    return unrealsdk.GetEngine().GamePlayers[0].Actor

def get_world_info():
    return unrealsdk.GetEngine().GetCurrentWorldInfo()

RegisterMod(Archipelago())