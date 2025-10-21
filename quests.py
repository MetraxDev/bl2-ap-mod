
from argparse import Namespace
import os
from random import choice
from mods_base import (
    command, 
    get_pc,
    hook,
)
from unrealsdk import logging, find_all, find_class
from unrealsdk.hooks import Type #type:ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct #type:ignore
from typing import Any

@command("ap_activate_all_quests", description="Activate all quests for testing purposes")
def cmd_ap_activate_all_quests(args: Namespace) -> None:
    logging.info(f"Quest test command received with args: {args}")
    mission_tracker = get_pc().WorldInfo.GRI.MissionTracker
    logging.info(f"Mission Tracker: {mission_tracker}")

    for mission in mission_tracker.MissionList:
        if not mission.MissionDef.DlcExpansion:
            logging.info(f"Mission: {mission.MissionDef.MissionName}, State: {mission.Status}")

    not_active_missions = [mission for mission in mission_tracker.MissionList if mission.Status == 0]
    active_missions = [mission for mission in mission_tracker.MissionList if mission.Status == 1]
    completed_missions = [mission for mission in mission_tracker.MissionList if mission.Status == 4]

    for mission in mission_tracker.MissionList:
        if not mission.MissionDef.DlcExpansion and mission.Status == 0:
            mission.Status = 1  # Set all missions to completed for testing

@command("ap_set_quest_status", description="Set specific quest status")
def cmd_ap_set_quest_status(args: Namespace) -> None:
    quest_name = args.quest_name
    new_status = args.new_status
    logging.info(f"Setting quest {quest_name} status to {new_status}.")
    mission_tracker = get_pc().WorldInfo.GRI.MissionTracker

    for mission in mission_tracker.MissionList:
        if mission.MissionDef.MissionName == quest_name:
            mission.Status = new_status
            logging.info(f"Quest {quest_name} status set to {new_status}.")
            return

    logging.error(f"Quest {quest_name} not found.")
cmd_ap_set_quest_status.add_argument("quest_name", help="Name of the quest to set status", type=str)
cmd_ap_set_quest_status.add_argument("new_status", help="New status for the quest", type=int)

@command("ap_activate_quest")
def cmd_ap_activate_quest(args: Namespace) -> None:
    quest_name = args.quest_name
    logging.info(f"Activating quest: {quest_name}")
    mission_tracker = get_pc().WorldInfo.GRI.MissionTracker

    for mission in mission_tracker.MissionList:
        if mission.MissionDef.MissionName == quest_name:
            mission.Status = 1  # Set mission to active
            logging.info(f"Quest {quest_name} activated.")
            return

    logging.error(f"Quest {quest_name} not found.")
cmd_ap_activate_quest.add_argument("quest_name", help="Name of the quest to activate", type=str)

@command("ap_random_quest", description="Activate a random quest")
def cmd_ap_random_quest(args: Namespace) -> None:
    logging.info("Activating a random quest.")
    mission_tracker = get_pc().WorldInfo.GRI.MissionTracker
    not_active_missions = [mission for mission in mission_tracker.MissionList if not mission.MissionDef.DlcExpansion and mission.Status == 0]

    if not_active_missions:
        choice(not_active_missions).Status = 1
    else:
        logging.info("No inactive missions available.")

@command("ap_get_plot_missions", description="Get all plot missions")
def cmd_ap_get_plot_missions(args: Namespace) -> None:
    logging.info("Retrieving all plot missions.")
    mission_tracker = get_pc().WorldInfo.GRI.MissionTracker

    plot_missions = [mission for mission in mission_tracker.MissionList if mission.MissionDef.bPlotCritical]
    for mission in plot_missions:
        if mission.MissionDef.bPlotCritical:
            logging.info(f"Plot Mission: {mission.MissionDef.MissionName}, Status: {mission.Status}")

@command("ap_setup_quests", description="Setup quests for Archipelago integration")
def cmd_ap_setup_quests(args: Namespace) -> None:
    logging.info("Setting up quests for Archipelago integration.")
    mission_tracker = get_pc().WorldInfo.GRI.MissionTracker

    for mission in mission_tracker.MissionList:
            mission.MissionDef.MissionGiver = ""

commands = [
    cmd_ap_activate_all_quests,
    cmd_ap_set_quest_status,
    cmd_ap_activate_quest,
    cmd_ap_random_quest,
    cmd_ap_get_plot_missions,
    cmd_ap_setup_quests,
]
hooks = []