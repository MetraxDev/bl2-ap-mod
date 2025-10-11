import os
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
            logging.info(f"Fast Travel: {fasttravel.bSendOnly}")
            logging.info(f"Fast Travel: {fasttravel.bInitiallyActive}")
            logging.info(f"Fast Travel: {fasttravel.DlcExpansion}")

def export_fasttravel_names():
    import json
    if get_pc():
        fasttravels = get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList
        names = []
        for fasttravel in fasttravels:
            if fasttravel.bSendOnly or fasttravel.DlcExpansion: continue

            names.append(fasttravel.StationDisplayName)

        with open(os.path.join(os.path.expandvars(r"%localappdata%/BL2Archipelago"), "ap_fasttravels.json"), "w") as f:
            json.dump(names, f, indent=2)

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

def register_fasttravel(name):
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            if fasttravel.bSendOnly or fasttravel.DlcExpansion: continue

            if name == fasttravel.StationDisplayName:
                fasttravel.MissionDependencies = []
                locationDisplayNames.append(fasttravel.StationDisplayName)
                locationStationDefinitions.append(fasttravel)
                locationStationStrings.append(fasttravel.StationDisplayName)

def register_all_fasttravel():
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            if fasttravel.bSendOnly or fasttravel.DlcExpansion: continue
            
            fasttravel.MissionDependencies = []
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

@command("ap_get_fasttravel_defs", description="Get all fast travel definitions")
def cmd_get_fasttravel_defs(args):
    get_fasttravel_definitions()

@command("ap_teleport_to_sanctuary", description="Teleport to Sanctuary fast travel station")
def cmd_teleport_to_sanctuary(args):
    try_teleport_to_fasttravel_station(args.name)
cmd_teleport_to_sanctuary.add_argument("name", type=str, help="Name of the fast travel station to teleport to")

@command("ap_register_fasttravel", description="Register a specific fast travel location")
def cmd_register_fasttravel(args):
    register_fasttravel(args.name)
cmd_register_fasttravel.add_argument("name", type=str, help="Name of the fast travel station to register")

@command("ap_register_all_fasttravels", description="Register all fast travel locations")
def cmd_register_all_fasttravels(args):
    register_all_fasttravel()

@command("ap_unregister_fasttravel", description="Unregister a specific fast travel location")
def cmd_unregister_fasttravel(args):
    unregister_fasttravel(args.name)
cmd_unregister_fasttravel.add_argument("name", type=str, help="Name of the fast travel station to unregister")

@command("ap_export_fasttravel_names", description="Export all fast travel names to a JSON file")
def cmd_export_fasttravel_names(args):
    export_fasttravel_names()

commands = [
    cmd_get_fasttravel_defs,
    cmd_teleport_to_sanctuary,
    cmd_register_fasttravel,
    cmd_unregister_fasttravel,
    cmd_register_all_fasttravels,
    cmd_export_fasttravel_names
]

@hook("WillowGame.FastTravelStationGFxMovie:BuildLocationData", Type.POST)
def BuildLocationDataPost(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    obj.LocationDisplayNames = locationDisplayNames
    obj.LocationDisplayNamesAlphabetical = sorted(locationDisplayNames)
    obj.LocationStationDefinitions = locationStationDefinitions
    obj.LocationStationStrings = locationStationStrings
    obj.LocationIsHeader = [False] * len(locationDisplayNames)

    return False

@hook("WillowGame.PlayerBehavior_RegisterFastTravelStation:ApplyBehaviorToContext")
def RegisterFastTravelStation(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] Found Station: {args.SelfObject.GetTravelStationDefinition().StationDisplayName}")

    return False

hooks = [
    BuildLocationDataPost,
    RegisterFastTravelStation,
]