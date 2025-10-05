
# Copilot instructions — Borderlands 2 Archipelago mod

This file is a short, focused guide to help an AI coding agent become productive in this repository.

Keep edits concise and confirm changes by running the project's build/deploy task and updating submodules where needed.

## Big picture (what to read first)
- `shared/bl2_data/` — single source of truth for game data. Code in this package (especially `data_loader.py` and `constants.py`) is used by both the mod and APWorld.

Why this structure: game data has to be shared between separate projects (APWorld and the SDK mod). The codebase centralizes data and comms so pieces can be swapped independently.

## Data flow & integration
- Game data lives in `shared/bl2_data/bl2_data.json` and is loaded via `shared/bl2_data/data_loader.py`.
- All code should use loader functions (e.g. `get_all_locations()`, `get_region_connections()`) instead of parsing JSON directly.
- External integration with Archipelago happens over sockets/messages implemented in `common/`.

Example imports:

from shared.bl2_data.data_loader import get_all_locations, get_region_connections
locations = get_all_locations()
connections = get_region_connections()

## Developer workflows (discoverable from repo)
- Build & Deploy: there is a VS Code task named "Build & Deploy" (depends on "Build sdkmod" and "Deploy sdkmod"). Use the task for iterative dev and deployment.
- Submodule management: `shared/` is intended as a git submodule. When changing `bl2_data.json`, run `git submodule update --init --recursive` in dependent repos.
- Debugging: look at `debugpy/` and `server/attach_pid_injected.py` to understand how the mod attaches to a running game process.

## Project-specific conventions and patterns
- Never access raw JSON in other modules — always use `shared.bl2_data.data_loader` functions.
- Cross-component communication follows message formats in `common/messaging.py`; prefer reusing those utilities to maintain compatibility.
- Keep shared data backward compatible; consumer projects (APWorld and the mod) expect stable loader APIs.

## Key files to inspect for most tasks
- `shared/bl2_data/data_loader.py` — how data is exposed and shaped
- `shared/bl2_data/bl2_data.json` — canonical game data
- `common/messaging.py`, `common/sockets.py` — message formats and socket usage
- `adapter/`, `launcher/` — mod launch flow
- `debugpy/`, `server/attach_pid_injected.py` — debugging/attachment logic

## Editing guidance for agents
- If changing data formats: update `data_loader.py` first, add conversion helpers, and search for usages across the repo.
- If adding a feature that crosses components (e.g., new message type), update `common/messaging.py` and run a quick smoke test using the VS Code "Build & Deploy" task.
- Preserve public loader function names where feasible to avoid breaking consumers.

If anything here is unclear or missing (for example, specific build commands for "Build sdkmod"), tell me which part you'd like expanded and I'll iterate.
