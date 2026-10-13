# Stellar Wanderer - Coding Guide

## Project Summary

**Stellar Wanderer** is a proof-of-concept space exploration game with realistic scale. Procedurally generated worlds, time compression (1x to 1,000,000x), and persistence via alteration tracking (only player changes saved, world regenerated from seed on load).

See `DEVLOG.md` for architecture deep-dive and design rationale.

## Where the details live

How each feature works is documented in the docstring of the module that owns it, next to the code. This file holds only the rules and conventions that the code does not show. When behaviour changes, update the docstring (and comments) that describe it in the same change.

## Coding Standards

**Type Hints**: Every function and method must have type hints on all parameters and a return type annotation. Use `-> None` for procedures that don't return a value.

- **Scope**: Applies to new code and any function being edited.
- **Pattern**: Use `from __future__ import annotations` to support forward references (already in `player.py`).

**Module names**: Use Python-style snake_case for module files (`stellar_system.py`, not `StellarSystem.py`). Every module file is snake_case; keep it that way (the package directories, such as `Galaxies` and `Graphics`, keep their names). Git on Windows does not record case-only renames (`core.ignorecase` is on), so a renamed module can stay tracked under its old case, which breaks imports on case-sensitive systems: rename with `git mv a.py tmp.py` then `git mv tmp.py b.py`, and check that `git ls-files` shows the new case.

Example:
```python
def generate_default(self) -> None:
    self.current_world = self.galaxy.add_stellar_system(26000, 0, 0)
```

## Core Architecture

**Hierarchy**: Galaxy → StellarSystem → Orbit → World → Km2 → Rock

**Persistence Pattern**: Objects track `is_altered` and return `get_alterations()` → dict. Saved to file, re-applied on load. Each object marks parent as altered if it changes. **Ore fields and mines are user-created, so they are alterations by definition**: their existence forces their Km2 (and so the world) to be altered, set once where they are created (e.g. `OreField.generate_new`), and they have no `set_altered` of their own; do not add one, nor calls to mark them on later changes. **Once altered, an object is never "de-altered"**: the flag is not reset, and an altered Km2 stays in memory and in the save.

**Seeding**: Every object has deterministic `seed = (coordinate + parent_seed) % SEEDS_SCALING`. Same seed = same generated object.

**Module Map**:
- `main.py`: entry point, game loop, window setup, starting and loading games
- `game_environment.py`: Galaxy + current world (module-level `current_environment`)
- `Galaxies/People/player.py`: Player: attitude, motion and binding (module-level `current_player`)
- `Galaxies/`: procedural world structure (Galaxy, StellarSystem, Orbit, World, Outpost, Km2, Rock)
- `Graphics/`: OpenGL rendering and the instruments
- `Spaceships/`: Ship, `scanner.py` (aiming and targeting), `laser.py` (firing and heating)
- `Persistency/`: save and load (Savefile)
- `Dialogs/`: modal dialogs and their message texts
- `GameLogging/`: logging and the galaxy almanack
- `Updating/`: time-based updates (UpdateQueue, Updatable)
- `paths.py`: the writable data folder (saves, logs)
- `units.py`: compact distance and speed formatting, for any module

## Rules the code does not show

- **Attitude names**: use yaw, pitch, roll and attitude consistently, with the meanings given in the `Player` docstring. Do not introduce synonyms. `Player.right`, `up` and `forward` are the source of truth.
- **Rock and mine `orientation` and rock `tilt` are different concepts** and keep their names.
- **`bind_to`/`unbind_from` asymmetry is intentional.** Do not "fix" it to be symmetric (see the `Player` docstring).
- **World orbit is derived, not stored.** A world's stellar position and velocity are pure functions of game time (`calculate_stellar_position(t)`, `calculate_stellar_velocity(t)`). Never cache them; always pass `gem.current_environment.date_time`. The world is not put in `UpdateQueue`; use the queue only for work that mutates state at intervals. Do not add per-call logging to these functions; they run every frame while unbound.
- **Opening a dialog pauses game time.** While a modal loop runs (`main.run_modal_dialog`), nothing that advances game time is called, and the frame timer is restarted afterwards.
- **Message texts live in the code**, next to the logic that shows them: build a `Message` (title, text, buttons) with f-strings and pass it to `show_message`, with an `on_result` callback that reads the pressed button's index.
- **Galaxy almanack**: `main` writes it on each new game and each load, overwriting the previous file. Its structure is in `Galaxy.almanack()`: each object writes its own part and calls its children.

## Key Notes

- Window size: always use `pygame.display.get_window_size()` for rendering size and mouse mapping, never `screen.get_size()`. For the OpenGL window pygame keeps returning a surface of the size first requested (1920×1080) while the real client area is smaller (window frame), which crops the frame and shifts mouse positions.
- No external config files: settings are module-level constants (e.g., `GameLogging/constants.py`)..
- Saves and logs are written under the data folder (`paths.data_path`): the working directory when run from source, `%LOCALAPPDATA%\StellarWanderer` in the packaged build.

## Working Policies (for Claude)

- **Save compatibility is required.** Saves made by older code must still load. Add fallbacks (defaults for missing fields, conversion of changed fields) in the load path only; always write the current format. Tell the user about each fallback added.
- **Do not change code unless asked.** Analysis-only requests are answered in text; wait for an explicit go-ahead before editing.
- **Ignore `DEVLOG.md`.** Do not read, analyse, quote or use it in any way, even when it is open in the IDE or the project summary points to it.
- **Keep labels and comments accurate.** When behaviour changes, update the docstring or comment that describes it in the same change.

## Testing Without a Window (for Claude)

- Run headless with `SDL_VIDEODRIVER=dummy`, and `PYTHONIOENCODING=utf-8` when printing `Δ`, `°` or other non-ASCII text (the console is cp1252).
- Start a game with `main.start_game('new', seed)`; load a save read-only with `Persistency.Savefile.Savefile.load_from_file(path)`. Changing `Player` state in memory is fine for a test; never call `Savefile.save()` in a test.
- Render to a `pygame.Surface` and save the PNG to the session scratchpad, then view it with Read. Compare pixel colours with `get_at` for visibility checks.
- The GL pass (`Rocks.draw`, `OpenGLGui.draw`) needs a real window: say so when it is untested.
