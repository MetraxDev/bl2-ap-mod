from argparse import Namespace
import os
from random import choice
from mods_base import (
    command, 
    get_pc,
)
from unrealsdk import logging, make_struct

def add_skillpoints(amount):
    if get_pc():
        get_pc().PlayerReplicationInfo.GeneralSkillPoints += amount

def set_skillpoints(amount):
    if get_pc():
        get_pc().PlayerReplicationInfo.GeneralSkillPoints = amount

def get_skills():
    for skill in get_pc().PlayerSkillTree.Skills:
        _, skill_state = get_pc().PlayerSkillTree.GetSkillState(skill.Definition, make_struct("SkillTreeSkillStateData"))
        logging.info(f"Skill: {skill}, Grade: {skill_state.SkillGrade}")

def export_skills():
    import json
    if get_pc():
        skills = get_pc().PlayerSkillTree.Skills
        # Convert skills to a serializable format if needed
        skill_list = []
        for skill in skills:
            # Try to get a dict representation, fallback to str
            if hasattr(skill, '__dict__'):
                skill_list.append(skill.__dict__)
            else:
                skill_list.append(str(skill))
        with open(os.path.join(os.path.expandvars(r"%localappdata%/BL2Archipelago"), "ap_skills.json"), "w") as f:
            json.dump(skill_list, f, indent=2)

def reset_skilltree():
    if get_pc():
        get_pc().ResetSkillTree(True)

def random_skill():
    if get_pc():
        locked_skills = []
        for skill in get_pc().PlayerSkillTree.Skills:
            _, skill_state = get_pc().PlayerSkillTree.GetSkillState(skill.Definition, make_struct("SkillTreeSkillStateData"))
            if skill_state.SkillGrade == 0:
                locked_skills.append(skill)
        if not locked_skills:
            logging.info("All skills are already unlocked.")
            return

        skill = choice(locked_skills)
        logging.info(f"Randomly selected skill: {skill.Definition}")
        get_pc().PlayerSkillTree.SetSkillGrade(skill.Definition, 99)

def set_skill(skill_name, grade):
    if get_pc():
        logging.info(f"Setting skill {skill_name} to grade {grade}")
        skilldef = None
        for skill in get_pc().PlayerSkillTree.Skills:
            if skill.Definition.SkillName == skill_name:
                skilldef = skill.Definition
                break
        if not skilldef:
            logging.error(f"Skill {skill_name} not found!")
            return
        get_pc().PlayerSkillTree.SetSkillGrade(skilldef, grade)

def unlock_skilltree():
    if get_pc():
        for tier in get_pc().PlayerSkillTree.Tiers:
            tier.bUnlocked = True

def unlock_all_skills():
    if get_pc():
        for skill in get_pc().PlayerSkillTree.Skills:
            get_pc().PlayerSkillTree.SetSkillGrade(skill.Definition, 99)

# ap_set_skill "Death Bl0ss0m" 5
@command("ap_set_skill", description="Set specific skill from tree")
def cmd_ap_set_skill(args: Namespace) -> None:
    set_skill(args.skill_name, args.grade)
cmd_ap_set_skill.add_argument("skill_name", help="Name of the skill to set", type=str)
cmd_ap_set_skill.add_argument("grade", help="Grade to set the skill to", type=int)

@command("ap_unlock_skilltree", description="Unlock all tiers in the skilltree")
def cmd_ap_unlock_skilltree(args: Namespace) -> None:
    unlock_skilltree()

@command("ap_unlock_all_skills", description="Unlock all skills in the skilltree")
def cmd_ap_unlock_all_skills(args: Namespace) -> None:
    unlock_all_skills()

@command("ap_random_skill", description="Set random skill from tree")
def cmd_ap_random_skill(args: Namespace) -> None:
    random_skill()

@command("ap_reset_skilltree", description="Set skillpoints to x amount")
def cmd_ap_reset_skilltree(args: Namespace) -> None:
    reset_skilltree()

@command("ap_export_skills", description="Export skills to a JSON file")
def cmd_ap_export_skills(args: Namespace) -> None:
    export_skills()

@command("ap_give_skillpoints", description="Give x amount of skillpoints")
def cmd_ap_give_skillpoints(args: Namespace) -> None:
    add_skillpoints(args.amount)
cmd_ap_give_skillpoints.add_argument("amount", help="amount of skillpoints", type=int)

@command("ap_take_skillpoints", description="Take x amount of skillpoints")
def cmd_ap_take_skillpoints(args: Namespace) -> None:
    add_skillpoints(-args.amount)
cmd_ap_take_skillpoints.add_argument("amount", help="amount of skillpoints", type=int)

@command("ap_set_skillpoints", description="Set skillpoints to x amount")
def cmd_ap_set_skillpoints(args: Namespace) -> None:
    set_skillpoints(args.amount)
cmd_ap_set_skillpoints.add_argument("amount", help="amount of skillpoints", type=int)

@command("ap_get_skills", description="Get current skills")
def cmd_ap_get_skills(args: Namespace) -> None:
    get_skills()

commands = [
        cmd_ap_give_skillpoints,
        cmd_ap_take_skillpoints,
        cmd_ap_set_skillpoints,
        cmd_ap_get_skills,
        cmd_ap_reset_skilltree,
        cmd_ap_random_skill,
        cmd_ap_export_skills,
        cmd_ap_set_skill,
        cmd_ap_unlock_skilltree,
        cmd_ap_unlock_all_skills
    ]