import sys
import random
import json
import os
import asyncio
import time
from pathlib import Path

import unrealsdk
from unrealsdk import find_object, logging
from mods_base import (
    ENGINE,
    command, 
    build_mod, 
    hook, Mod, 
    register_mod, 
    Game, 
    CoopSupport,
    get_pc
)
from ui_utils import show_hud_message

from .Locations import id_lookup_table, boss_lookup_table

SKILL_POINTS = find_object("AttributeInitializationDefinition", "GD_Globals.Skills.INI_SkillPointsPerLevelUp")

LocalModDir: str = os.path.dirname(os.path.realpath(__file__))
_last_known_level = 0
player_loaded = False
config = False
connected = False
completed_checks = set()
savefile_bindings_path = ""
game_communication_path = ""
seed = ""

def init():
    global game_communication_path
    global savefile_bindings_path

    if "localappdata" in os.environ:
        game_communication_path = os.path.expandvars(r"%localappdata%/BL2Archipelago")
    else:
        game_communication_path = os.path.expandvars(r"$HOME/BL2Archipelago")
    
    if not os.path.exists(game_communication_path):
        logging.info(f"[Archipelago] Path {game_communication_path} does not exist. Please start the archipelago client first.")
        
    savefile_bindings_path = os.path.join(game_communication_path, "savefile_bindings.json")
    if not os.path.exists(savefile_bindings_path):
        logging.info(f"[Archipelago] savefile_bindings.json not found. Please start the archipelago client first.")
        return

    reset()

def reset():
    global player_loaded
    global config
    global connected
    global completed_checks

    player_loaded = False
    config = False
    connected = False
    completed_checks = set()

def get_seed_path():
    if not seed:
        return None

    return os.path.join(game_communication_path, str(seed))

def is_player_in_game():
    try:
        # Check if player controller exists
        pc = get_pc()
        if not pc:
            return False
            
        # Check if not in main menu
        world_info = ENGINE.GetCurrentWorldInfo()
        map_name = world_info.GetStreamingPersistentMapName().lower()
        if map_name == "menumap":
            return False
            
        # Check if player pawn exists (character is spawned)
        pawn = pc.Pawn
        return pawn is not None
        
    except (IndexError, AttributeError):
        return False

def send_check(check_id, check_name):
    if check_id in completed_checks:
        return
        
    check_data = {
        "type": "check",
        "id": check_id,
        "name": check_name,
        "timestamp": time.time()
    }
    
    check_file = os.path.join(get_seed_path(), f"check{check_id}.json")
    with open(check_file, 'w') as f:
        json.dump(check_data, f)
        
    completed_checks.add(check_id)
    logging.info(f"[Archipelago] Check completed: {check_name}")

def enable():
    logging.info(f"[Archipelago] Hello!")
    show_hud_message("Archipelago", "Hello!")
    init()

def disable():
    logging.info(f"[Archipelago] Bye bye!")
    show_hud_message("Archipelago", "Bye bye!")

@hook("WillowGame.WillowPlayerController:PlayerTick")
def PlayerTick(caller, function, params, method) -> bool:
    if is_player_in_game() and connected and config:
        return True

    return True

@hook("WillowGame.WillowPlayerController:WillowClientDisableLoadingMovie")
def on_loading_complete(caller, function, params, method):
    global player_loaded

    player_loaded = True
    logging.info(f"[Archipelago] Player Loaded: {player_loaded}")

    if not connected:
        connect_to_archipelago()

    if not config:
        load_config()

    disable_skillpoints_on_levelup()

    return True

@hook("WillowGame.WillowPlayerController:LoadTheBank")
def check_level_change(caller, function, params, method):
    current_level = caller.PlayerReplicationInfo.ExpLevel
    global _last_known_level
    if current_level > _last_known_level:
        logging.info(f"[Archipelago] Player Level Up: {_last_known_level} -> {current_level}")
        _last_known_level = current_level

@hook("WillowGame.WillowPlayerController:CompleteQuitToMenu")
def on_disconnect(caller, function, params, method):
    reset()
    logging.info(f"[Archipelago] Player disconnected: {player_loaded}")
    return True

@hook("WillowGame.WillowPlayerPawn:PickupInventory")
def on_pickup_inventory(caller, function, params, method):
    logging.info(f"[Archipelago] on_pickup_inventory: {params}")
    if is_player_in_game():
        # Example: Send check for picking up any item
        # You'd want to filter this based on specific items
        item_name = "Unknown Item"  # Extract actual item name from params
        send_check(f"pickup_{item_name}", f"Picked up {item_name}")
    return True

@hook("WillowGame.MissionTracker:SetMissionStatus")
def on_mission_status_change(caller, function, params, method):
    logging.info(f"[Archipelago] on_mission_status_change: {params}")
    if is_player_in_game():
        # Check if mission was completed
        # params.NewStatus would indicate completion
        mission_name = "Unknown Mission"  # Extract from params
        send_check(f"mission_{mission_name}", f"Completed {mission_name}")
    return True

@hook("WillowGame.WillowPawn:Died")
def on_enemy_died(caller, function, params, method):
    # Check if it's a boss or important enemy
    # Send boss defeat check
    if caller.IsChampion() or caller.IsBoss():
        *_, name = caller.GetTargetName("")

        if name not in boss_lookup_table:
            return False

        check_name = f"Kill {name}"
        check_id = id_lookup_table[check_name]

        logging.info(f"[Archipelago] on_enemy_died: {name}")
        send_check(check_id, check_name)
        
    return True

@hook("WillowGame.WillowPlayerController:SpawningProcessComplete")
def on_spawning_process_complete(obj, args, ret, HookedMethod):
    logging.info(f"[Archipelago] {HookedMethod} has been hooked")

def disable_skillpoints_on_levelup():
    logging.info(f"[Archipelago] Disabling vanilla skillpoints {SKILL_POINTS}!")
    expression_list = SKILL_POINTS.ConditionalInitialization.ConditionalExpressionList
    if expression_list:
        expression = expression_list[0].Expressions
        if expression:
            expression[0].ConstantOperand2 = 999

def connect_to_archipelago():
    savefile_bindings = []
    try:
        with open(savefile_bindings_path, 'r') as f:
            savefile_bindings = json.load(f)
    except OSError:
        logging.info(f"[Archipelago] Could not read file: {savefile_bindings_path}")
        return

    if not is_connected_to_seed(savefile_bindings):
        logging.info(f"[Archipelago] Savefile not connected to any seed. Connecting..")
        establish_new_connection(savefile_bindings)

    logging.info(f"[Archipelago] Savefile connected.")

    connected = True

def is_connected_to_seed(savefile_bindings):
    global seed

    savefile_id = get_savefile_id()

    for b in savefile_bindings:
        if b["save_file"] == savefile_id:
            seed = b["seed"]
            return True

    return False    

def establish_new_connection(savefile_bindings):
    global seed

    binding = -1
    for i, b in enumerate(savefile_bindings):
        if b["seed"] and not b["save_file"]:
            binding = i
            break

    if binding < 0:
        logging.info(f"[Archipelago] Could not find empty seed.")
        return
    else:
        savefile_bindings[binding]["save_file"] = get_savefile_id()

    try:
        with open(savefile_bindings_path, 'w') as f:
            json.dump(savefile_bindings, f)

        seed = savefile_bindings[binding]["seed"]
        logging.info(f"[Archipelago] Connected seed {savefile_bindings[binding]["seed"]} to savefile {savefile_bindings[binding]["save_file"]}")
    except OSError:
        logger.warning(f"Could not write file: {savefile_bindings_path}")

def get_savefile_id():
    pc = get_pc()
    if pc == None:
        return None
    
    save_game = pc.GetCachedSaveGame()

    if not save_game:
        return None
    
    return save_game.SaveGameId

def load_config():
    config_path = os.path.join(get_seed_path(), "config.json")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except OSError:
        logging.info(f"[Archipelago] Could not read file: {config_path}")

def get_player_controller():
    """
    Get the current WillowPlayerController Object.
    :return: WillowPlayerController
    """
    return get_pc()

def get_world_info():
    return ENGINE.GetCurrentWorldInfo()

build_mod(
    coop_support=CoopSupport.Incompatible,
    on_enable=enable,
    on_disable=disable,
    hooks=[
        PlayerTick,
        on_loading_complete,
        check_level_change,
        on_disconnect,
        on_pickup_inventory,
        on_mission_status_change,
        on_enemy_died,
        on_spawning_process_complete
    ]
)
# register_mod(mod)
# RegisterMod(instance)