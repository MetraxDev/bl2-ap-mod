import json
import os
import time

import fasttravels
from items import cmd_ap_get_def_from_pool, cmd_ap_give_weapon, cmd_ap_give_weapon_from_pool, cmd_ap_spawn_weapon, cmd_spawn_loot

import items
from skills import cmd_ap_export_skills, cmd_ap_get_skills, cmd_ap_give_skillpoints, cmd_ap_random_skill, cmd_ap_reset_skilltree, cmd_ap_set_skill, cmd_ap_set_skillpoints, cmd_ap_take_skillpoints, cmd_ap_unlock_all_skills, cmd_ap_unlock_skilltree
import skills
from unrealsdk import find_object, logging

from mods_base import (
    ENGINE,
    build_mod, 
    hook, 
    CoopSupport,
    get_pc,
)
from ui_utils import show_hud_message

from .shared.bl2_data import get_bosses_only, get_regions_only, find_unlock_by_id

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

    logging.info(f"[Archipelago] send_check seed path {get_seed_path()}")
    
    check_file = os.path.join(get_seed_path(), f"check{check_id}.json")
    with open(check_file, 'w') as f:
        json.dump(check_data, f)
        
    completed_checks.add(check_id)
    logging.info(f"[Archipelago] Check {check_id} -> {check_name}")

def on_enable():
    logging.info(f"[Archipelago] Hello!")
    show_hud_message("Archipelago", "Hello!")
    init()

def on_disable():
    logging.info(f"[Archipelago] Bye bye!")
    show_hud_message("Archipelago", "Bye bye!")

ap_check_count=0
ap_check_max=100

@hook("WillowGame.WillowPlayerController:PlayerTick")
def on_player_tick(caller, function, params, method) -> bool:
    global ap_check_count

    if is_player_in_game() and connected and config:
        ap_check_count = ap_check_count + 1

        if ap_check_count > ap_check_max:
            # check_for_unlocks()
            # on ap get skillpoint: GeneralSkillPoints + 1
            # get_pc().PlayerReplicationInfo.GeneralSkillPoints = 0
            ap_check_count=0

        return True

    return True

def check_for_unlocks():
    hud_message = ""
    try:
        for root, dirs, files in os.walk(get_seed_path()):
            for file in files:
                if file.startswith("AP"):
                    json = convert_json_to_map(os.path.join(root, file))
                    player = json["player"]
                    item = find_unlock_by_id(json["item_id"])
                    logging.info(f"[Archipelago] Player {player} sent {item["name"]}")
                    hud_message += f"Player {player} sent {item["name"]}\n"
                    handle_unlock(item)

    except OSError:
        # Directory access error, continue
        pass

    if hud_message:
        show_hud_message("Archipelago", hud_message)

def handle_unlock(item):
    match item["name"]:
        case "Weapon" | "Artifact" | "Classmod":
            pass
            # spawn_item()

def convert_json_to_map(filepath):
    jsonmap = {}
    try:
        with open(filepath, 'r') as f:
            jsonmap = json.load(f)
    except OSError:
        logger.warning(f"Could not read file: {filepath}")
    
    return jsonmap

@hook("WillowGame.WillowPlayerController:SpawningProcessComplete")
def on_spawning_process_complete(obj, args, ret, HookedMethod):
    logging.info(f"[Archipelago] {HookedMethod} has been hooked")

# @hook("WillowGame.WillowPlayerController:WillowClientDisableLoadingMovie")
@hook("WillowGame.WillowPlayerController:SpawningProcessComplete")
def on_loading_complete(caller, function, params, method):

    disable_skillpoints_on_levelup()

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

    internal_name = ENGINE.GetCurrentWorldInfo().GetMapName()
    area_name = get_pc().GetWillowGlobals().GetLevelDependencyList().GetFriendlyLevelNameFromMapName(internal_name)

    if area_name not in get_regions_only().keys():
        return False

    loc = get_regions_only()[area_name]

    check_name = f"{loc["action"]} {loc["name"]}"

    send_check(loc["full_id"], check_name)

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

        if name not in get_bosses_only().keys():
            return False

        loc = get_bosses_only()[name]

        check_name = f"{loc["action"]} {loc["name"]}"

        send_check(loc["full_id"], check_name)
        
    return True

def disable_skillpoints_on_levelup():
    logging.info(f"[Archipelago] Disabling vanilla skillpoints {SKILL_POINTS}!")
    expression_list = SKILL_POINTS.ConditionalInitialization.ConditionalExpressionList
    if expression_list:
        expression = expression_list[0].Expressions
        if expression:
            expression[0].ConstantOperand2 = 999

def connect_to_archipelago():
    global connected

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
    global config

    config_path = os.path.join(get_seed_path(), "config.json")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except OSError:
        logging.info(f"[Archipelago] Could not read file: {config_path}")

build_mod(
    coop_support=CoopSupport.Incompatible,
    on_enable=on_enable,
    on_disable=on_disable,
    commands=[
        *items.commands,
        *skills.commands,
        *fasttravels.commands,
    ],
    hooks=[
        on_player_tick,
        on_loading_complete,
        check_level_change,
        on_disconnect,
        on_pickup_inventory,
        on_mission_status_change,
        on_enemy_died,
        on_spawning_process_complete
    ]
)