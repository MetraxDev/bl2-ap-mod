from mods_base import (
    command, 
    get_pc,
    hook,
)
from unrealsdk import logging, find_all, find_class
from unrealsdk.hooks import Type #type:ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct #type:ignore
from typing import Any

locationDisplayNames = []
locationStationDefinitions = []
locationStationStrings = []

def get_fasttravel_definitions():
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            logging.info(f"Fast Travel: {fasttravel}")
            logging.info(f"Fast Travel: {fasttravel.StationDisplayName}")
            logging.info(f"Fast Travel: {fasttravel.MissionDependencies}")

def get_fasttravel_definition_by_name(name):
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            if name in fasttravel.StationDisplayName:
                return fasttravel
    return None

def try_teleport_to_fasttravel_station(name):
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            if name in fasttravel.StationDisplayName:
                get_pc().ServerTeleportPlayerToStation(fasttravel)

def get_fasttravels():
    if get_pc():
        for station in find_all("FastTravelStation"):
            logging.info(f"Fast Travel: {station}")

def set_fasttravels_usability():
    if get_pc():
        for station in find_all("FastTravelStation"):
            if station and station.InteractiveObjectDefinition:
                station.SetUsability(True, 1)

def register_fasttravels():
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            fasttravel.MissionDependencies = []
            get_pc().Behavior_RegisterStationDefinition(fasttravel, True)

def register_fasttravel(name):
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            if name == fasttravel.StationDisplayName:
                locationDisplayNames.append(fasttravel.StationDisplayName)
                locationStationDefinitions.append(fasttravel)
                locationStationStrings.append(fasttravel.StationDisplayName)

def unregister_fasttravel(name):
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            if name == fasttravel.StationDisplayName:
                locationDisplayNames.remove(fasttravel.StationDisplayName)
                locationStationDefinitions.remove(fasttravel)
                locationStationStrings.remove(fasttravel.StationDisplayName)

@command("ap_get_fasttravels", description="Get all fast travel locations and their unlock status")
def cmd_get_fasttravels(args):
    get_fasttravels()

@command("ap_register_fasttravels", description="Register all fast travel locations")
def cmd_register_fasttravels(args):
    register_fasttravels()

@command("ap_get_fasttravel_defs", description="Get all fast travel definitions")
def cmd_get_fasttravel_defs(args):
    get_fasttravel_definitions()

@command("ap_set_fasttravels_usable", description="Set all fast travel locations to usable")
def cmd_set_fasttravels_usable(args):
    set_fasttravels_usability()

@command("ap_teleport_to_sanctuary", description="Teleport to Sanctuary fast travel station")
def cmd_teleport_to_sanctuary(args):
    try_teleport_to_fasttravel_station(args.name)
cmd_teleport_to_sanctuary.add_argument("name", type=str, help="Name of the fast travel station to teleport to")

@command("ap_register_fasttravel", description="Register a specific fast travel location")
def cmd_register_fasttravel(args):
    register_fasttravel(args.name)
cmd_register_fasttravel.add_argument("name", type=str, help="Name of the fast travel station to register")

@command("ap_unregister_fasttravel", description="Unregister a specific fast travel location")
def cmd_unregister_fasttravel(args):
    unregister_fasttravel(args.name)
cmd_unregister_fasttravel.add_argument("name", type=str, help="Name of the fast travel station to unregister")

commands = [
    cmd_get_fasttravels,
    cmd_register_fasttravels,
    cmd_get_fasttravel_defs,
    cmd_set_fasttravels_usable,
    cmd_teleport_to_sanctuary,
    cmd_register_fasttravel,
    cmd_unregister_fasttravel,
]

@hook("WillowGame.FastTravelStationGFxMovie:HandleOpen", Type.PRE)
def HandleOpen(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] Fast Travel Station Opened: {obj}")
    # obj.LocationDisplayNames = []
    # obj.LocationStationDefinitions = []
    # obj.LocationStationStrings = []
    return False

@hook("WillowGame.FastTravelStationGFxMovie:HandleOpen", Type.POST)
def HandleOpenPost(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] POST Fast Travel Station Opened: {obj}")
    # obj.LocationDisplayNames = []
    # obj.LocationStationDefinitions = []
    # obj.LocationStationStrings = []
    return False

@hook("WillowGame.FastTravelStationGFxMovie:BuildLocationData", Type.PRE)
def BuildLocationData(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] Building Location Data for: {obj}")
    return False

@hook("WillowGame.FastTravelStationGFxMovie:BuildLocationData", Type.POST)
def BuildLocationDataPost(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] POST Building Location Data for: {obj}")

    # for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
    #     obj.LocationDisplayNames.append(fasttravel.StationDisplayName)
    #     obj.LocationStationDefinitions.append(fasttravel)
    #     obj.LocationStationStrings.append(fasttravel.StationDisplayName)

    obj.LocationDisplayNames = locationDisplayNames
    obj.LocationStationDefinitions = locationStationDefinitions
    obj.LocationStationStrings = locationStationStrings

    return False

@hook("WillowGame.FastTravelStationGFxMovie:extActivate", Type.PRE)
def ExtActivate(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] ExtActivate called for: {obj}")
    return False

@hook("WillowGame.FastTravelStationGFxMovie:extActivate", Type.POST)
def ExtActivatePost(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] POST ExtActivate called for: {obj}")
    return False

@hook("WillowGame.FastTravelStationGFxObject:SendLocationData", Type.PRE)
def SendLocationData(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] Sending Location Data for: {obj}")
    # for displayName in args.LocationDisplayNames:
    #     logging.info(f"[Archipelago] Arg: {displayName}")
    #     displayName = "Fast Travel Disabled"
    # for stationStrings in args.LocationStationNames:
    #     logging.info(f"[Archipelago] Arg: {stationStrings}")
    #     stationStrings = "Fast Travel Disabled"

    # Infinite recursion, oops
    #func(args.LocationDisplayNames, args.LocationStationNames, args.InitialSelectionIndex, args.CurrentWaypointIndex)
    return False

@hook("WillowGame.FastTravelStationGFxObject:SendLocationData", Type.POST)
def SendLocationDataPost(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] POST Sending Location Data for: {obj}")
    # for displayName in args.LocationDisplayNames:
    #     logging.info(f"[Archipelago] Arg: {displayName}")
    #     displayName = "Fast Travel Disabled"
    # for stationStrings in args.LocationStationNames:
    #     logging.info(f"[Archipelago] Arg: {stationStrings}")
    #     stationStrings = "Fast Travel Disabled"

    # Infinite recursion, oops
    #func(args.LocationDisplayNames, args.LocationStationNames, args.InitialSelectionIndex, args.CurrentWaypointIndex)
    return False

#/mnt/SSD/Projects/Archipelago/bl2-mods/downloaded/loot/Mod/tps/locations.py

hooks = [
    HandleOpen,
    HandleOpenPost,
    BuildLocationData,
    SendLocationData,
    ExtActivate,
    BuildLocationDataPost,
    SendLocationDataPost,
    ExtActivatePost,
]