from mods_base import (
    command, 
    get_pc,
)
from unrealsdk import logging, find_all

def get_fasttravel_definitions():
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            logging.info(f"Fast Travel: {fasttravel}")

def get_fasttravels():
    if get_pc():
        for station in find_all("FastTravelStation"):
            logging.info(f"Fast Travel: {station}")

def register_fasttravels():
    if get_pc():
        for fasttravel in get_pc().GetWillowGlobals().GetFastTravelStationsLookup().FastTravelStationLookupList:
            get_pc().Behavior_RegisterStationDefinition(fasttravel, False)

@command("ap_get_fasttravels", description="Get all fast travel locations and their unlock status")
def cmd_get_fasttravels(args):
    get_fasttravels()

@command("ap_register_fasttravels", description="Register all fast travel locations")
def cmd_register_fasttravels(args):
    register_fasttravels()

@command("ap_get_fasttravel_defs", description="Get all fast travel definitions")
def cmd_get_fasttravel_defs(args):
    get_fasttravel_definitions()

commands = [
    cmd_get_fasttravels,
    cmd_register_fasttravels,
    cmd_get_fasttravel_defs,
]