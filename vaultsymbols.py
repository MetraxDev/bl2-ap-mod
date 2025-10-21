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

@hook("WillowGame.Behavior_DiscoverLevelChallengeObject:ApplyBehaviorToContext")
def DiscoverLevelChallengeObject(obj: UObject, args: WrappedStruct, ret: Any, func: BoundFunction) -> Any:
    logging.info(f"[Archipelago] Discover Level Challenge Object: {args.SelfObject.AssociatedChallenge.ChallengeName}\n{args.SelfObject.AssociatedChallenge.AssociatedMap}\n{args.SelfObject.AssociatedChallenge.ChallengeType}\n{args.SelfObject.AssociatedChallenge.Levels}")

hooks = [
    DiscoverLevelChallengeObject,
]