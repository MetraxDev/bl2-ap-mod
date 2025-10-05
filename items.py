from typing import Optional, Sequence, Tuple
from ui_utils.hud_message import show_hud_message
from unrealsdk.unreal import UObject, UStructProperty, WrappedStruct, UScriptStruct
from mods_base import (
    ENGINE,
    command, 
    get_pc,
)
import unrealsdk
from unrealsdk import find_object, logging, construct_object, make_struct, find_class
try:
    from unrealsdk.hooks import add_hook, remove_hook, Type  # modern sdk
except Exception:
    add_hook = None
    remove_hook = None
    Type = None

# Compatibility wrapper: prefer unrealsdk.hooks.add_hook/remove_hook, fall back to
# legacy RegisterHook/RemoveHook or RunHook/RemoveHook if available in the environment.
def _register_hook(func_name: str, hook_type, hook_id: str, hook_fn):
    # Try modern API
    if add_hook is not None and Type is not None:
        try:
            add_hook(func_name, hook_type, hook_id, hook_fn)
            return True
        except Exception:
            pass

    # Try legacy wrappers if present
    try:
        if hasattr(unrealsdk, "RegisterHook"):
            unrealsdk.RegisterHook(func_name, hook_id, hook_fn)
            return True
    except Exception:
        pass

    try:
        if hasattr(unrealsdk, "RunHook"):
            unrealsdk.RunHook(func_name, hook_id, hook_fn)
            return True
    except Exception:
        pass

    return False

def _remove_hook(func_name: str, hook_type, hook_id: str):
    # Try modern API
    if remove_hook is not None and Type is not None:
        try:
            remove_hook(func_name, hook_type, hook_id)
            return True
        except Exception:
            pass

    # Try legacy wrappers
    try:
        if hasattr(unrealsdk, "RemoveHook"):
            unrealsdk.RemoveHook(func_name, hook_id)
            return True
    except Exception:
        pass

    try:
        if hasattr(unrealsdk, "RemoveHook"):
            unrealsdk.RemoveHook(func_name, hook_id)
            return True
    except Exception:
        pass

    return False

def _try_set_custom_location(spawner, pc) -> bool:
    """Try several ways to set CustomLocation and log types/exceptions.

    Returns True if assignment succeeded.
    """
    # 1) Try engine-provided struct
    try:
        val = (pc.Location, None, "")
        logging.info(f"[Archipelago] Trying CustomLocation assignment using pc.Location: {type(pc.Location)}")
        spawner.CustomLocation = val
        return True
    except Exception as e:
        logging.info(f"[Archipelago] pc.Location assign failed: {e}")

    # 2) Try building a Vector WrappedStruct
    try:
        location_struct = make_struct("Vector", X=pc.Location.X, Y=pc.Location.Y, Z=pc.Location.Z)
        logging.info(f"[Archipelago] Trying CustomLocation assignment using make_struct Vector: {type(location_struct)}")
        spawner.CustomLocation = (location_struct, None, "")
        return True
    except Exception as e:
        logging.info(f"[Archipelago] make_struct assign failed: {e}")

    # 3) Try raw tuple
    try:
        val = ((pc.Location.X, pc.Location.Y, pc.Location.Z), None, "")
        logging.info(f"[Archipelago] Trying CustomLocation assignment using raw tuple: {type(val[0])}")
        spawner.CustomLocation = val
        return True
    except Exception as e:
        logging.info(f"[Archipelago] tuple assign failed: {e}")

    # 4) Give up and use sentinel location
    try:
        sentinel = ((float('inf'), float('inf'), float('inf')), None, "")
        logging.info("[Archipelago] Falling back to sentinel CustomLocation")
        spawner.CustomLocation = sentinel
        return True
    except Exception as e:
        logging.info(f"[Archipelago] sentinel assign failed: {e}")
        return False


def _convert_struct_to_tuple(fstruct):
    """Convert an unrealsdk WrappedStruct / FStruct-like object into a nested python tuple.

    Mirrors the convert_struct function used in other mods but kept minimal and local.
    """
    # If it's already a tuple/list, convert elements
    try:
        # exclude bytes/str
        if isinstance(fstruct, (list, tuple)):
            return tuple(_convert_struct_to_tuple(v) for v in fstruct)
    except Exception:
        pass

    struct_type = getattr(fstruct, "structType", None)
    if struct_type is None:
        # Not a struct - return raw value
        return fstruct

    values = []
    while struct_type:
        attribute = struct_type.Children
        while attribute:
            try:
                value = getattr(fstruct, attribute.GetName())
            except Exception:
                value = None
            values.append(_convert_struct_to_tuple(value))
            attribute = attribute.Next
        struct_type = struct_type.SuperField

    return tuple(values)


def _tuple_to_wrapped_struct(template_struct, tup):
    """Convert a python tuple (tup) into a WrappedStruct using template_struct to infer field names/types.

    template_struct should be an example WrappedStruct (e.g., current.DefinitionData) whose
    structType.Children provide the field ordering and nested struct shapes.
    """
    struct_type = getattr(template_struct, "structType", None)
    if struct_type is None:
        raise ValueError("template_struct has no structType")

    # determine struct name
    struct_name = getattr(struct_type, "Name", None)
    if not struct_name:
        try:
            struct_name = struct_type.GetName()
        except Exception:
            struct_name = None

    kwargs = {}
    attr = struct_type.Children
    i = 0
    while attr:
        name = attr.GetName()
        val = tup[i] if i < len(tup) else None

        sample = None
        try:
            sample = getattr(template_struct, name)
        except Exception:
            sample = None

        # If the sample field is a nested struct and val is iterable, recurse
        if getattr(sample, "structType", None) and isinstance(val, (list, tuple)):
            kwargs[name] = _tuple_to_wrapped_struct(sample, val)
        else:
            # Direct assignment (UObject, primitive, None, etc.)
            kwargs[name] = val

        i += 1
        attr = attr.Next

    # Build the struct
    try:
        return make_struct(struct_name, **kwargs)
    except Exception:
        # Last-resort: try to build with no struct name if make_struct supports template object
        try:
            return make_struct(template_struct)
        except Exception:
            # If we cannot build, raise to surface the failure
            raise


def _clone_wrapped_struct(src):
    """Create a new WrappedStruct instance with the same fields/values as src.

    This builds a fresh WrappedStruct via make_struct and copies nested structs recursively.
    """
    st = getattr(src, "structType", None)
    if st is None:
        return src

    struct_name = getattr(st, "Name", None)
    if not struct_name:
        try:
            struct_name = st.GetName()
        except Exception:
            struct_name = None

    kwargs = {}
    attr = st.Children
    while attr:
        name = attr.GetName()
        try:
            value = getattr(src, name)
        except Exception:
            value = None

        if getattr(value, "structType", None):
            kwargs[name] = _clone_wrapped_struct(value)
        else:
            kwargs[name] = value

        attr = attr.Next

    try:
        return make_struct(struct_name, **kwargs)
    except Exception:
        # fallback - return the original as last resort
        return src

def spawn_item():
    # Spawn a loot drop at the player's feet.
    pc = get_pc()
    if not pc:
        logging.info("[Archipelago] No player controller available for spawn_item()")
        return

    # Give the spawner a unique name so repeated spawns don't collide
    spawner_name = f"LootSpawner_{int(time.time()*1000)}"
    spawner = construct_object(cls="Behavior_SpawnLootAroundPoint", outer=pc, name=spawner_name)

    # set CustomLocation using helper which logs attempts and exceptions
    if not _try_set_custom_location(spawner, pc):
        logging.info("[Archipelago] Failed to set CustomLocation on spawner")

    spawner.ItemPools = (find_object("ItemPoolDefinition", "GD_Itempools.EnemyDropPools.Pool_GunsAndGear_06_Legendary"),)
    spawner.SpawnVelocityRelativeTo = 1
    spawner.ApplyBehaviorToContext(pc, (), None, None, None, ())


def spawn_and_give_item(pool_path: str = "GD_Itempools.WeaponPools.Pool_Weapons_All_06_Legendary"):
    """Spawn an item from the given pool at the player and immediately add it to the player's backpack.

    This hooks the Behavior_SpawnLootAroundPoint.PlaceSpawnedItems event for the spawner
    and removes the hook after the first spawn.
    """
    pc = get_pc()
    if not pc:
        logging.info("[Archipelago] No player controller available for spawn_and_give_item()")
        return

    pool = find_object("ItemPoolDefinition", pool_path)
    if not pool:
        logging.info(f"[Archipelago] Could not find item pool: {pool_path}")
        return

    spawner_name = f"LootSpawner_{int(time.time()*1000)}"
    spawner = construct_object(cls="Behavior_SpawnLootAroundPoint", outer=pc, name=spawner_name)
    spawner.ItemPools = (pool,)
    spawner.SpawnVelocityRelativeTo = 1

    # set CustomLocation using helper which logs attempts and exceptions
    if not _try_set_custom_location(spawner, pc):
        logging.info("[Archipelago] Failed to set CustomLocation on spawner")

    # Hook that will run once when the spawner places items
    def _hook(caller, function, params, method):
        try:
            if caller is spawner:
                spawned = tuple(getattr(params, "SpawnedLoot", ()))
                if len(spawned):
                    # The spawned entry has an .Inv inventory object
                    item = spawned[0].Inv
                    owner = pc.Pawn
                    # Add to player's backpack and set the owner
                    try:
                        owner.InvManager.AddInventoryToBackpack(item)
                        item.Owner = owner
                        logging.info("[Archipelago] Spawned item added to player's backpack")
                    except Exception:
                        logging.info("[Archipelago] Failed to add spawned item to backpack")
                # remove the hook so it only runs once
                try:
                    _remove_hook("WillowGame.Behavior_SpawnLootAroundPoint.PlaceSpawnedItems", Type.PRE, f"Archipelago.{id(spawner)}")
                except Exception:
                    pass
        finally:
            return True

    # Register the hook and start the spawner
    try:
        _register_hook("WillowGame.Behavior_SpawnLootAroundPoint.PlaceSpawnedItems", Type.PRE, f"Archipelago.{id(spawner)}", _hook)
    except Exception:
        logging.info("[Archipelago] Could not register PlaceSpawnedItems hook")

    spawner.ApplyBehaviorToContext(pc, (), None, None, None, ())


def _get_items_from_pool(pool_obj, game_stage: int, game_stage_variance_def=None):
    """Spawn inventory directly from an ItemPoolDefinition and return created item objects.

    This avoids creating a Behavior_SpawnLootAroundPoint spawner by invoking the engine's
    ItemPool.SpawnBalancedInventoryFromPool and catching created items via OnCreate hooks.
    """
    pc = get_pc()
    if not pc:
        logging.info("[Archipelago] No player controller available for _get_items_from_pool()")
        return []

    default_item_pool = find_object('ItemPool', 'WillowGame.Default__ItemPool')
    logging.info(f"[Archipelago] _get_items_from_pool default_item_pool {default_item_pool}")

    if not default_item_pool:
        logging.info('[Archipelago] Could not find default ItemPool object')
        return []

    spawned_items = []

    def _append_inv(obj, params, ret, func):
        try:
            spawned_items.append(obj)
        except Exception:
            pass
        return True

    # Register hooks to capture created items. Use unique ids so they can be removed safely.
    hook_id_item = f"Archipelago.get_items_from_pool.item.{id(pool_obj)}"
    hook_id_weapon = f"Archipelago.get_items_from_pool.weapon.{id(pool_obj)}"
    logging.info(f"[Archipelago] _get_items_from_pool hooks {hook_id_item}, {hook_id_weapon}")

    try:
        _register_hook("WillowGame.WillowItem:OnCreate", Type.PRE, hook_id_item, _append_inv)
        _register_hook("WillowGame.WillowWeapon:OnCreate", Type.PRE, hook_id_weapon, _append_inv)
    except Exception:
        logging.info('[Archipelago] Could not register OnCreate hooks for pool extraction')

    try:
        # SpawnBalancedInventoryFromPool(pool, minLevel, maxLevel, instigator, extraArray, varianceDef)
        default_item_pool.SpawnBalancedInventoryFromPool(pool_obj, game_stage, game_stage, pc, [], game_stage_variance_def)
        logging.info(f"[Archipelago] _get_items_from_pool SpawnBalancedInventoryFromPool")

    except Exception as e:
        logging.info(f"[Archipelago] SpawnBalancedInventoryFromPool failed: {e}")

    # Cleanup hooks
    try:
        _remove_hook("WillowGame.WillowItem:OnCreate", Type.PRE, hook_id_item)
    except Exception:
        pass
    try:
        _remove_hook("WillowGame.WillowWeapon:OnCreate", Type.PRE, hook_id_weapon)
    except Exception:
        pass

    return spawned_items


def get_definition_data_from_pool(pool_path: str, game_stage: int = None, variance_path: str = None):
    """Get the DefinitionData (WrappedStruct) for the first item spawned from the given pool.

    Returns the raw DefinitionData object (not converted) or None if nothing was produced.
    """
    pool = find_object("ItemPoolDefinition", pool_path)
    logging.info(f"[Archipelago] get_definition_data_from_pool pool {pool}")

    if not pool:
        logging.info(f"[Archipelago] Could not find item pool: {pool_path}")
        return None

    if game_stage is None:
        try:
            pc = get_pc()
            game_stage = pc.PlayerReplicationInfo.ExpLevel
            logging.info(f"[Archipelago] get_definition_data_from_pool game_stage {game_stage}")

        except Exception:
            game_stage = 1

    variance_def = None
    if variance_path:
        logging.info(f"[Archipelago] get_definition_data_from_pool variance_def {variance_def}")
        variance_def = find_object('AttributeInitializationDefinition', variance_path)

    items = _get_items_from_pool(pool, game_stage, variance_def)
    logging.info(f"[Archipelago] get_definition_data_from_pool items {items}")

    if not items:
        return None

    first = items[0]
    try:
        return first.DefinitionData
    except Exception:
        return None

@command("spawn_loot", description="Spawn loot from specified pools around a point with given parameters")
def cmd_spawn_loot(args: str):
    """Spawn loot from specified pools around a point with given parameters.

    This function is not directly exposed as a command but can be called from other functions.
    """
    pc = get_pc()
    if not pc:
        logging.info("[Archipelago] No player controller available for spawn_loot()")
        return

    # Example usage: spawn one legendary weapon around the player
    pool = find_object("ItemPoolDefinition", "GD_Itempools.WeaponPools.Pool_Weapons_All_06_Legendary")
    # pool = find_object("ItemPool", "WillowGame.Default__ItemPool")
    if not pool:
        logging.info("[Archipelago] Could not find item pool for spawn_loot()")
        return

    spawn_loot(
        pools=(pool,),
        context=pc,
        location=None,
        velocity=(0.0, 0.0, 0.0),
        radius=100
    )

def spawn_loot(
    pools: Sequence[UObject],
    context: UObject,
    location: Optional[Tuple[float, float, float]] = None,
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    radius: int = 0,
) -> None:
    spawner = construct_object("Behavior_SpawnLootAroundPoint", context, f"LootSpawner_{int(time.time()*1000)}")
    if location is not None:
        spawner.CircularScatterRadius = radius
        spawner.CustomLocation = (location, None, "")
        spawner.SpawnVelocity = velocity
        spawner.SpawnVelocityRelativeTo = 1

    spawner.ItemPools = pools

    # spawner.ApplyBehaviorToContext(context, WrappedStruct(UStructProperty), None, None, None, None)
    spawner.ApplyBehaviorToContext(context, (), None, None, None, ())

@command("ap_get_def_from_pool", description="Get DefinitionData (struct) for first item from pool")
def cmd_ap_get_def_from_pool(args: str) -> None:
    """Console command: ap_get_def_from_pool [pool_path]

    If pool_path is omitted a common legendary weapons pool is used.
    The command logs the converted tuple form of DefinitionData and notifies the HUD.
    """
    pool_path = "GD_Itempools.WeaponPools.Pool_Weapons_All_06_Legendary"
    defdata = get_definition_data_from_pool(pool_path)
    if defdata is None:
        logging.info(f"[Archipelago] No definition data returned from pool: {pool_path}")
        show_hud_message("Archipelago", f"No item found in pool: {pool_path}")
        return

    # Try to convert to tuple for easier inspection
    try:
        tup = _convert_struct_to_tuple(defdata)
        logging.info(f"[Archipelago] DefinitionData from pool {pool_path}: {tup}")
        show_hud_message("Archipelago", f"Got definition data from pool: check logs")
    except Exception:
        logging.info("[Archipelago] Retrieved DefinitionData but failed to convert to tuple")
        show_hud_message("Archipelago", "Got definition data from pool (raw) - see logs")


@command("ap_spawn_weapon", description="Spawn a weapon drop at the player")
def cmd_ap_spawn_weapon(args: str) -> None:
    """Console command to spawn a weapon drop at the player's feet."""
    spawn_item()
    show_hud_message("Archipelago", "Spawned weapon drop at player.")


def _spawn_and_give_clone_of_current_weapon() -> None:
    """Spawn a WillowWeapon initialized from the player's current weapon definition and add it to their backpack.

    This bypasses Behavior_SpawnLootAroundPoint and CustomLocation problems by directly creating the
    weapon actor, initializing it from existing DefinitionData, and adding it to the player's inventory.
    """
    pc = get_pc()
    if not pc:
        logging.info("[Archipelago] No player controller available for give-weapon command")
        return

    pawn_inv_manager = pc.GetPawnInventoryManager()
    if not pawn_inv_manager:
        logging.info("[Archipelago] Could not get player's inventory manager")
        return

    current = pawn_inv_manager.GetWeaponInSlot(1)
    if not current:
        logging.info("[Archipelago] No weapon in primary slot to clone")
        show_hud_message("Archipelago", "No weapon in primary slot to clone")
        return

    try:
        # Try to clone the existing WrappedStruct definition directly
        definition_wrapped = _clone_wrapped_struct(current.DefinitionData)
        logging.info("[Archipelago] Cloned DefinitionData into new WrappedStruct")
    except Exception as e:
        logging.info(f"[Archipelago] Failed to clone current DefinitionData: {e}")
        # Fall back to converting to tuple
        try:
            definition_tuple = _convert_struct_to_tuple(current.DefinitionData)
            definition_wrapped = None
            logging.info("[Archipelago] Converted DefinitionData to tuple as fallback")
        except Exception as e2:
            logging.info(f"[Archipelago] Failed to read current weapon DefinitionData: {e2}")
            return

    try:
        willow_weapon = ENGINE.GetCurrentWorldInfo().Spawn(find_class("WillowWeapon"))
    except Exception as e:
        logging.info(f"[Archipelago] Failed to spawn WillowWeapon actor: {e}")
        return

    try:
        # Prefer passing a WrappedStruct if we have one; InitializeFromDefinitionData may accept either.
        try:
            if definition_wrapped is not None:
                willow_weapon.InitializeFromDefinitionData(definition_wrapped, pawn_inv_manager.Instigator, True)
                logging.info("[Archipelago] InitializeFromDefinitionData called with WrappedStruct")
            else:
                willow_weapon.InitializeFromDefinitionData(definition_tuple, pawn_inv_manager.Instigator, True)
                logging.info("[Archipelago] InitializeFromDefinitionData called with tuple fallback")
        except Exception as e:
            # Last resort: if wrapped attempt failed, try tuple conversion
            logging.info(f"[Archipelago] InitializeFromDefinitionData failed with error: {e}, trying tuple fallback")
            try:
                if definition_wrapped is not None:
                    definition_tuple = _convert_struct_to_tuple(definition_wrapped)
                willow_weapon.InitializeFromDefinitionData(definition_tuple, pawn_inv_manager.Instigator, True)
            except Exception as e2:
                logging.info(f"[Archipelago] All InitializeFromDefinitionData attempts failed: {e2}")
                return
        willow_weapon.AdjustWeaponForBeingInBackpack()
        # Give ammo if possible (some definition_data shapes may not have AmmoResource)
        try:
            ammo_res = None
            ammo_count = None
            if 'definition_tuple' in locals():
                try:
                    ammo_res = definition_tuple[0].AmmoResource
                    ammo_count = definition_tuple[0].StartingAmmoCount
                except Exception:
                    ammo_res = None
            elif 'definition_wrapped' in locals() and definition_wrapped is not None:
                try:
                    ammo_res = definition_wrapped.WeaponTypeDefinition.AmmoResource
                    ammo_count = definition_wrapped.WeaponTypeDefinition.StartingAmmoCount
                except Exception:
                    try:
                        # Try index-based access if wrapped struct behaves like sequence
                        ammo_res = definition_wrapped[0].AmmoResource
                        ammo_count = definition_wrapped[0].StartingAmmoCount
                    except Exception:
                        ammo_res = None

            if ammo_res is not None and ammo_count is not None:
                pawn_inv_manager.GiveStoredAmmoBeforeGoingToBackpack(ammo_res, ammo_count)
        except Exception:
            pass

        pawn_inv_manager.AddInventoryToBackpack(willow_weapon)
        # Ready/equip into slot 1
        try:
            pawn_inv_manager.ReadyBackpackInventory(willow_weapon, 1)
        except Exception:
            pass

        logging.info("[Archipelago] Spawned and gave cloned weapon to player")
        show_hud_message("Archipelago", "Gave cloned weapon to player")
    except Exception as e:
        logging.info(f"[Archipelago] Failed to initialize or give weapon: {e}")

@command("ap_give_weapon", description="Spawn a copy of your current weapon and add it to inventory")
def cmd_ap_give_weapon(args: str) -> None:
    _spawn_and_give_clone_of_current_weapon()

@command("ap_give_weapon_from_pool", description="Spawn a weapon from a pool (e.g. legendary) and add it to inventory")
def cmd_ap_give_weapon_from_pool(args: str) -> None:
    """Spawn one item from the configured pool and add the spawned inventory to the player's backpack.

    Usage: ap_give_weapon_from_pool [pool_path]
    If pool_path is omitted a common legendary weapons pool will be used.
    """
    pc = get_pc()
    if not pc:
        logging.info("[Archipelago] No player controller available for give-from-pool command")
        return

    pool_path = "GD_Itempools.WeaponPools.Pool_Weapons_All_06_Legendary"
    pool = find_object("ItemPoolDefinition", pool_path)
    if not pool:
        logging.info(f"[Archipelago] Could not find pool: {pool_path}")
        show_hud_message("Archipelago", f"Pool not found: {pool_path}")
        return

    # Create spawner object and use sentinel location so engine picks a spawn point
    spawner_name = f"LootSpawner_{int(time.time()*1000)}"
    spawner = construct_object(cls="Behavior_SpawnLootAroundPoint", outer=pc, name=spawner_name)
    spawner.ItemPools = (pool,)
    spawner.SpawnVelocityRelativeTo = 1
    spawner.CustomLocation = ((float('inf'), float('inf'), float('inf')), None, "")

    def one_shot(caller, function, params, method):
        try:
            if caller is spawner:
                spawned = tuple(getattr(params, "SpawnedLoot", ()))
                if len(spawned):
                    item = spawned[0].Inv
                    try:
                        owner = pc.Pawn
                        owner.InvManager.AddInventoryToBackpack(item)
                        item.Owner = owner
                        logging.info("[Archipelago] Spawned pool item added to player's backpack")
                        show_hud_message("Archipelago", "Gave item from pool to player")
                    except Exception:
                        logging.info("[Archipelago] Failed to add spawned pool item to backpack")
                # remove hook
                try:
                    _remove_hook("WillowGame.Behavior_SpawnLootAroundPoint.PlaceSpawnedItems", Type.PRE, f"Archipelago.{id(spawner)}")
                except Exception:
                    pass
        finally:
            return True

    try:
        _register_hook("WillowGame.Behavior_SpawnLootAroundPoint.PlaceSpawnedItems", Type.PRE, f"Archipelago.{id(spawner)}", one_shot)
    except Exception:
        logging.info("[Archipelago] Could not register PlaceSpawnedItems hook for pool spawn")

    spawner.ApplyBehaviorToContext(pc, (), None, None, None, ())

commands = [
    cmd_ap_give_weapon,
    cmd_ap_give_weapon_from_pool,
    cmd_ap_get_def_from_pool,
    cmd_ap_spawn_weapon,
    cmd_spawn_loot
    ]