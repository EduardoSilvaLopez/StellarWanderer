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

**Units**: SI only, in code, constants, logs and technical texts: metres, kilograms, seconds, watts, kelvin. No astronomical or Sun-based units (AU, solar masses or luminosities, parsecs, "Earth" years or days) and no figure expressed as a multiple of the Sun's or the Earth's: write the real value in SI, or derive it from the physics (a distance from a temperature and a luminosity, for example). The only exception in code is the light-year, for galactic coordinates. Print distances in logs with `common.units.format_compact_distance`.

- **The almanack texts are the exception, for good**: the markdown text of `StellarSystem.markdown()` (with the `markdown()` of its `Star`, `World` and planets), shown in the knowledge dialog, is gamer-friendly, so it keeps AU, Earth days and years and the like. Never convert it to SI, and write new lines of it in the same friendly units.
- **Scope**: Applies to new code and any code being edited. Old uses outside those texts remain until they are touched.

**Module names**: Use Python-style snake_case for module files (`stellar_system.py`, not `StellarSystem.py`). Every module file is snake_case, and so is every package directory (`galaxies`, `graphics`, `common/dialogs`, `common/game_logging`), as PEP 8 asks; keep it that way. Git on Windows does not record case-only renames (`core.ignorecase` is on), so a renamed module or directory can stay tracked under its old case, which breaks imports on case-sensitive systems: rename with `git mv a.py tmp.py` then `git mv tmp.py b.py` (the same for a directory), and check that `git ls-files` shows the new case.

Example:
```python
def generate_default(self) -> None:
    self.current_world = self.galaxy.add_stellar_system(26000, 0, 0)
```

## Core Architecture

**Hierarchy**: Galaxy → StellarSystem → Orbit → World → Km2 → Rock

**Persistence Pattern**: Objects track `is_altered` and return `get_alterations()` → dict. Saved to file, re-applied on load. Each object marks parent as altered if it changes. **Ore fields and mines are user-created, so they are alterations by definition**: their existence forces their Km2 (and so the world) to be altered, set once where they are created (e.g. `OreField.from_rock`), and they have no `set_altered` of their own; do not add one, nor calls to mark them on later changes. **Once altered, an object is never "de-altered"**: the flag is not reset, and an altered Km2 stays in memory and in the save. The one exception is forgetting (the pilot's "Forget" on a finished mission): when the last promoted asteroid of a belt is forgotten, `AsteroidBelt.forget` de-alters the belt.

**Seeding**: Every object has a deterministic `seed = seeds.derive(parent.seed, kind, *keys)` (`galaxies/seeds.py`, which documents the chain from the galaxy to the rocks). Same seed = same generated object. Seeds are ints, the galaxy seed (given by the user) included. Each object draws from its own `random.Random(seed)` in a fixed order, and a new draw goes last.

**Module Map**:
- `main.py`: entry point, game loop, window setup, starting and loading games
- `game_environment.py`: Galaxy + current world (module-level `current_environment`)
- `galaxies/missions/`: what the outposts ask of the pilot. `mission.py` is the base, one module per kind (`deliver_ore.py`), `mission_board.py` the board (the Missions option of the outpost screen, from the reputation it needs), shown there by `OutpostMissions` in `common/dialogs/mission_board_dialog.py`, which also has `PendingMissionsDialog`, the cockpit's missions window. The taken ones are in `Player.missions`
- `galaxies/people/knowledge.py`: the keys of the stellar bodies generated so far (module-level `current_knowledge`), saved at the root of the savefile
- `galaxies/people/player.py`: Player: the pilot (time scale, political status) and the ship they fly (module-level `current_player`)
- `galaxies/`: procedural world structure (Galaxy, StellarSystem, Orbit, World, Outpost, Km2, Rock). `body.py` (Body) is what navigation needs from a world or the star; `star.py` (Star) is the system's star as a body: at rest at the origin of the stellar frame, no surface, never bound to; `orbit_layout.py` (OrbitLayout) decides how many orbits a system has, of which kind (earthlike planet, asteroid belt, jovian planet) and how far from the star; `world_surface.py` gives a world its equilibrium temperature, surface type and colour (the colour is what `graphics/lit_worlds.py` lights); `seeds.py` derives each object's seed from its parent's (`derive`) and gives a seed for a text (`of_text`); `asteroid_belt.py` (AsteroidBelt, an orbit) generates the asteroids of a belt by sectors around the ship (`near`), with the size law and the six tiers in `asteroid_sizes.py`, the relevant ones (mission targets, saved as alterations) and the free-living ones (no belt; the system keeps and saves the seeds of the ones that matter) in `asteroid.py` (its `markdown()` is the knowledge base's entry; the classes are in `asteroid_class.py`), and the Kepler helpers in `kepler.py`. The mission to scan one is `missions/scan_asteroid.py` (the rock one is `scan_rock.py`)
- `graphics/`: OpenGL rendering and the instruments. `rock_batches.py` draws the rocks of each Km2 (one batch for ordinary rocks, one for rocks with an adjective), `special_rocks.py` gives each adjective its look (a mineral: agate, lapis, malachite, amethyst, gold in quartz; one fallback look), used by the batches and the scanner panel; `asteroids.py` draws the asteroids of the ongoing missions, and the near, slow cosmetic ones, as meshes in space while unbound (their shape is in `asteroid_shape.py`, their classes and colours in `asteroid_looks.py`)
- `spaceships/`: Ship, which holds where it is and how it moves: `kinematics.py` (Position, Velocity), `attitude.py` (Attitude), `navigation.py` (Navigation, everything relative to the fixed body: a world or the star); also `scanner.py` (aiming and targeting, and the scan of an asteroid: `Asteroid.scan_progress`, which also decides what its knowledge base entry shows), `laser.py` (firing and heating), `long_distance_advice.py` (the ACCELERATE / STAY / DECELERATE advice for a far target, shown by the proximity meter, with its lead marked by `graphics/lead_marker.py`; its algorithm is in its docstring; `shortage` also gives the missions their amber warning, `Mission.warning`)
- `common/`: shared code, used by every layer (it is not a strict layer: `savefile.py` and `dialogs/starting_dialog.py` know the game)
  - `dialogs/`: modal dialogs and their message texts; `knowledge_dialogs.py` shows the known systems and the people met (opened by the two buttons of `graphics/instruments/cockpit_buttons.py`)
  - `game_logging/`: logging
  - `savefile.py`: save and load (Savefile)
  - `updating.py`: time-based updates (UpdateQueue, Updatable)
  - `frame_watch.py`: logs the frames that hang (work over `HITCH_SECONDS`, with the time of each phase of `main`'s loop and of the rare operations, `timed`, in it), one line for each run of slow frames (over `SLOW_SECONDS`), and the slow garbage collections
  - `audio.py`: sound effects, `play(name)` (the sounds are in `resources/sounds`, made by `tools/generate_sounds.py`)
  - `paths.py`: the writable data folder (saves, logs) and `resource_path`
  - `units.py`: compact distance and speed formatting; `vector3.py`: Vector3
  - `resources/`: fonts, textures, portraits, people names (always reach them through `resource_path`)
- `tools/`: the build files (`StellarWanderer.spec`, `installer.iss`, `build_windows.ps1`) and the generators of the outpost texture, the sounds and the Milky Way panorama (`generate_milky_way.py`, drawn by `graphics/milky_way.py`)
- `data/`, `temp/`, `release/`: generated, not tracked. `data/Savefiles` is the player's progress: never delete or move it as a clean-up. `data/Logs` holds the logs. `temp/` holds `pycache`, `build` and `dist`, which can be deleted. `release/` holds the installer.

## Rules the code does not show

- **Attitude names**: use yaw, pitch, roll and attitude consistently, with the meanings given in the `Attitude` docstring. Do not introduce synonyms. `ship.attitude.right`, `up` and `forward` are the source of truth.
- **Rock and mine `orientation` and rock `tilt` are different concepts** and keep their names.
- **`_bind_to`/`_unbind_from` asymmetry is intentional.** Do not "fix" it to be symmetric (see the `Navigation` docstring).
- **World orbit is derived, not stored.** A world's stellar position and velocity are pure functions of game time (`calculate_stellar_position(t)`, `calculate_stellar_velocity(t)`). The only caching allowed is the one inside them: each world remembers the result for the date of its last call, so a frame evaluates each world once. Do not store them anywhere else, and always pass `gem.current_environment.date_time`. The world is not put in `UpdateQueue`; use the queue only for work that mutates state at intervals. Do not add per-call logging to these functions; they run every frame while unbound.
- **Cosmetic asteroids are never remembered.** They are regenerated by `AsteroidBelt.near` from the seed, so nothing about them is stored, saved or kept alive; only the ones promoted to relevant (`AsteroidBelt.promote`, mission targets) are alterations of the belt, and only by key. Their positions are pure functions of the date: do not add state to them. Ask `near` for the tiers and reaches that are needed (`DISPLAY_REACHES`, `SCANNER_REACHES`) and keep the result between queries, instead of asking every frame.
- **Opening a dialog pauses game time.** While a modal loop runs (`main.run_modal_dialog`), nothing that advances game time is called, and the frame timer is restarted afterwards.
- **Sound is for the vacuum.** Only what the pilot hears inside the ship (cockpit, dialogs, ship systems, radio, alarms) has a sound: never one from space itself. Game code asks `audio.play(name)` and never touches `pygame.mixer`.
- **Message texts live in the code**, next to the logic that shows them: build a `Message` (title, text, buttons) with f-strings and pass it to `show_message`, with an `on_result` callback that reads the pressed button's index.

## Key Notes

- Window size: always use `pygame.display.get_window_size()` for rendering size and mouse mapping, never `screen.get_size()`. For the OpenGL window pygame keeps returning a surface of the size first requested (1920×1080) while the real client area is smaller (window frame), which crops the frame and shifts mouse positions.
- No external config files: settings are module-level constants (e.g., `common/game_logging/constants.py`)..
- Saves and logs are written through `paths.data_path`: `data/` below the project folder when run from source (whatever the working directory), `%LOCALAPPDATA%\StellarWanderer` in the packaged build. Resources are read through `paths.resource_path`.

## Working Policies (for Claude)

- **Do not change code unless asked.** Analysis-only requests are answered in text; wait for an explicit go-ahead before editing.
- **In doubt, ask.** When a request leaves a real choice open, or I am unsure what is wanted, ask instead of changing code.
- **Ignore `DEVLOG.md`.** Do not read, analyse, quote or use it in any way, even when it is open in the IDE or the project summary points to it.
- **Keep labels and comments accurate.** When behaviour changes, update the docstring or comment that describes it in the same change.

## Testing Without a Window (for Claude)

- Set `PYTHONPYCACHEPREFIX` (to the session scratchpad) when running Python, so no `__pycache__` folders appear beside the sources. `main.py` sets `sys.pycache_prefix` to `temp/pycache` itself.
- Run headless with `SDL_VIDEODRIVER=dummy` (and `SDL_AUDIODRIVER=dummy` for sound), and `PYTHONIOENCODING=utf-8` when printing `Δ`, `°` or other non-ASCII text (the console is cp1252).
- Start a game with `main.start_game('new', seed)`; load a save read-only with `common.savefile.Savefile.load_from_file(path)`. Changing the ship's state in memory (`player.ship.position`, `velocity`, `attitude`) is fine for a test. A test may save, as long as it overwrites no existing file and deletes only what it created. **Never pick the file to delete as "the newest"**: `Savefile.save()` refuses to replace a save of the same name, and a test that has loaded a player's save gets that save's own name, so nothing is written and the newest file is the player's. In such a test, save with `save_as` under a name no save has (for example `zz test <something unique>`), and delete exactly that path afterwards. A new game's test save is named from the seed, so it is safe only when that name is new: list `data/Savefiles` before, and delete only the files that were not there.
- Render to a `pygame.Surface` and save the PNG to the session scratchpad, then view it with Read. Compare pixel colours with `get_at` for visibility checks.
- The GL pass (`Rocks.draw`, `OpenGLGui.draw`) needs a real window: say so when it is untested.
