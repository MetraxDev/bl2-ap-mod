import unrealsdk
from unrealsdk import *
import sys
import random
import json
import os
import asyncio
from pathlib import Path
from ..ModManager import BL2MOD, RegisterMod
from Mods.ModMenu import Game, Hook

class Archipelago(BL2MOD):
    Name: str = "Archipelago"
    Description: str = "Archipelago!"
    Version: str = "0.0"
    Author: str = "Metrax"
    SupportedGames = Game.BL2
    LocalModDir: str = os.path.dirname(os.path.realpath(__file__))

    def __init__(self):
        if "localappdata" in os.environ:
            self.game_communication_path = os.path.expandvars(r"%localappdata%/BL2Archipelago")
        else:
            self.game_communication_path = os.path.expandvars(r"$HOME/BL2Archipelago")
        
        if not os.path.exists(self.game_communication_path):
            os.makedirs(self.game_communication_path)
            
        self.player_loaded = False
        self.completed_checks = set()

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
        
        check_file = os.path.join(self.game_communication_path, f"check_{check_id}.json")
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
        if self.is_player_in_game():
            # Player is loaded and in-game, safe to do checks
            pass
        return True

    @Hook("WillowGame.WillowPlayerController.WillowClientDisableLoadingMovie")
    def on_loading_complete(self, caller, function, params):
        self.player_loaded = True
        unrealsdk.Log(f"[Archipelago] Player Loaded: {self.player_loaded}")
        return True

    @Hook("WillowGame.WillowPlayerController.CompleteQuitToMenu")
    def on_disconnect(self, caller, function, params):
        self.player_loaded = False
        unrealsdk.Log(f"[Archipelago] Player Loaded: {self.player_loaded}")
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

            unrealsdk.Log(f"[Archipelago] on_enemy_died: {name}")
            
        return True

def get_player_controller():
    """
    Get the current WillowPlayerController Object.
    :return: WillowPlayerController
    """
    return unrealsdk.GetEngine().GamePlayers[0].Actor

def get_world_info():
    return unrealsdk.GetEngine().GetCurrentWorldInfo()

RegisterMod(Archipelago())