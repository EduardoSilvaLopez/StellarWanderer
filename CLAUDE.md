# Stellar Wanderer - Coding Guide

## Project Summary

**Stellar Wanderer** is a proof-of-concept space exploration game with realistic scale. Procedurally generated worlds, time compression (1x to 1,000,000x), and persistence via alteration tracking (only player changes saved, world regenerated from seed on load).

See `DEVOLG.md` for architecture deep-dive and design rationale.

## Coding Standards

**Type Hints**: Every function and method must have type hints on all parameters and a return type annotation. Use `-> None` for procedures that don't return a value.

- **Scope**: Applies to new code and any function being edited.
- **Pattern**: Use `from __future__ import annotations` to support forward references (already in `Player.py`).

**Module names**: Use Python-style snake_case for module files (`stellar_system.py`, not `StellarSystem.py`). This is the standard for new files and for files with significant changes; existing files are not renamed in bulk.

Example:
```python
def generate_default(self) -> None:
    self.current_world = self.galaxy.add_stellar_system(26000, 0, 0)
```

## Core Architecture

**Hierarchy**: Galaxy → StellarSystem → Orbit → World → Km2 → Rock

**Persistence Pattern**: Objects track `is_altered` and return `get_alterations()` → dict. Saved to file, re-applied on load. Each object marks parent as altered if it changes.

**Seeding**: Every object has deterministic `seed = (coordinate + parent_seed) % SEEDS_SCALING`. Same seed = same generated object.

**Module Map**:
- `main.py`: Entry point, game loop, window setup
- `GameEnvironment.py`: Galaxy + current world (module-level `current_environment`)
- `Player.py`: Player state + movement (module-level `current_player`)
- `Galaxies/`: Procedural world structure (Galaxy, StellarSystem, Orbit, World, Km2, Rock)
- `Graphics/`: OpenGL rendering (Cockpit, DeepSpace, NearestWorld, Laser, Rocks)
- `Spaceships/`: Ship + Laser logic
- `Persistency/`: Save/load (Savefile)
- `Dialogs/`: Modal dialogs (`dialog.py` base class, `starting_dialog.py`)
- `GameLogging/`: Logging config (Constants, Setup)
- `Updating/`: Time-based updates (UpdateQueue, Updatable)

## Ship Attitude and Controls

Use these names consistently; do not introduce synonyms. Three rotation axes:

- **Yaw**: rotation about the ship's up axis (Numpad 4 left, 6 right). `Player.yaw` is the heading in degrees clockwise from north, derived from the forward axis. `Player.velocity.yaw` is the yaw rate in degrees per second.
- **Pitch**: rotation about the ship's right axis (Numpad 8 up, 2 down; only while unbound). `Player.pitch_angle(world, t)` is the nose-up angle above the local horizon. `Player.velocity.pitch` is the pitch rate.
- **Roll**: rotation about the ship's forward axis (Q left, E right). `Player.velocity.roll` is the roll rate in degrees per second.
- **Attitude**: the ship's right, up and forward axes, stored as `Player.right`, `Player.up` and `Player.forward` in the active frame (surface when bound, stellar when unbound). This is the source of truth; yaw, pitch and roll are derived from it or applied to it.
- Braking (S) decelerates linear velocity in all three axes and all rotation rates (yaw, pitch, roll) to zero. While unbound, linear braking is relative to the star, except within `BRAKING_RADIUS_MULTIPLE` world radii of the nearest world's centre, where it is relative to that world.
- Bind, unbind and braking thresholds are all distances from the world's centre in radii (1.0 = surface). The bound altitude bar spans 0 to (UNBIND_RADIUS_MULTIPLE - 1.0) × radius altitude; the unbound meter spans 1.0 to BRAKING_RADIUS_MULTIPLE radii distance from the centre.
- In the braking zone the "Speed" readout of the unbound meter turns red when `Player.collision_warning` holds: keeping its direction relative to the world, the ship reaches the surface even braking with only `Player.COLLISION_BRAKE_FRACTION` of `Ship.BRAKE_ACC` (straight-line check, sideways dodging not considered).
- Rotation accelerations and speed limits share `Ship.ANGULAR_ACC` and `Ship.MAX_ANGULAR_SPEED`.
- Location-info readouts show yaw, pitch and roll as angle plus rate (Δ, deg/s). `Player.pitch_angle` and `Player.roll_angle` are relative to the local horizon, positive nose up and right wing down.
- Rock and mine `orientation` and rock `tilt` are different concepts and keep their names.
- **`bind_to`/`unbind_from` asymmetry is intentional.** `Player.bind_to` snaps the ship level
  (yaw-only; pitch and roll are discarded) when binding to a world's surface — a ship always
  starts level on a surface. `Player.unbind_from` instead preserves the ship's full right/up/forward
  attitude, round-tripping all three axes through `World.surface_vector_to_stellar` — free flight
  keeps whatever attitude the ship had while bound. This asymmetry is correct; do not "fix" it to
  be symmetric.

## World Orbit

- A world's stellar position and velocity are pure functions of game time (`World.calculate_stellar_position(t)`, `calculate_stellar_velocity(t)`). Never cache them; always pass `gem.current_environment.date_time`.
- A moon's stellar position and velocity are its planet's plus its own offset and velocity around the planet (same orbital plane). Every orbital period follows Kepler's third law around the parent's mass: a moon around its planet (`World.mass`, from the radius and `World.EARTH_DENSITY`), a planet around its star (`StellarSystem.mass`, estimated from the star's radius). Every world starts `initial_degrees_in_orbit` from the reference direction at EPOCH. `World.local_day_fraction` is the solar day at longitude 0 (0 = noon), so that start angle sets the starting time of day; the game's date and time always start at EPOCH 00:00:00.
- The world is not put in `UpdateQueue`, because its state is derived, not stored. Use the queue only for work that mutates state at intervals.
- Do not add per-call logging to these functions; they run every frame while unbound.

## Dialogs

- Dialogs are modal and live in `Dialogs/`. A `Dialog` never runs its own loop: the host feeds it events and shows its surface, as an overlay above the frozen game (`Dialog.compose_overlay` through `OpenGLGui.draw(dialog_surface=...)`) or alone in the startup window (`run_in_window`).
- **Opening a dialog pauses game time.** While `main.open_starting_dialog` (or any future modal loop) runs, nothing that advances game time is called, and the frame timer is restarted afterwards so the next `dt` does not include the dialog's time.
- **Message dialogs** (`MessageDialog`): a textured panel (`Resources/textures/dialog_background.png`), Orbitron title and Exo 2 body (`Resources/fonts/`, SIL OFL, licence files next to them), one button; Esc, Enter, Space or the button close it. Their texts live in `Resources/dialogs/messages.toml` (one section per message: `title`, `text`, optional `button`; `{placeholders}` are filled from game data; re-read from disk every time a message opens, so editing the file needs no restart). Game code calls `show_message('key', name=value, ...)` and never opens a modal loop itself: `main` opens pending messages at the start of the next frame through `run_modal_dialog`. Currently only the `welcome` message, shown at the start of a *new* game.
- Esc opens the *starting dialog* (`StartingDialog`: new game, load a savefile, Exit game); Esc inside it resumes the game. Esc no longer quits; the Exit game button (or closing the window) does.

## Radar

- Shown only while unbound, in the centre console panel where the world map is drawn while bound (`Graphics/Instruments/radar.py`).
- It lists the star and every world of the system within 100 AU. The ellipse is the ship's forward/right plane (forward at the top). The foot of each bar is the object's projection on that plane, with in-plane distance on a log scale from 100 km (centre) to 100 AU (edge). The bar runs along the ship's up axis: white upwards when above the plane, gray downwards when below, with a log length on the same scale. The dot at its tip is the star's own colour or light brown for a world.

## Dependencies

- `pygame-ce`: Window, input, OpenGL context
- `PyOpenGL`: 3D graphics
- Python stdlib: datetime, logging, random, math, os, sys

## Key Notes

- Window size: always use `pygame.display.get_window_size()` for rendering size and mouse mapping, never `screen.get_size()`. For the OpenGL window pygame keeps returning a surface of the size first requested (1920×1080) while the real client area is smaller (window frame), which crops the frame and shifts mouse positions.
- Window position/size: `center_window_on_screen()` in `main.py` uses Windows API via ctypes to center the 1920×1080 main window
- Logging: `GameLogging.configure_logging()` called at app startup; logs to console + `Logs/stellar_wanderer.log` (ISO8601 timestamps)
- No external config files — all settings in module-level constants (e.g., `GameLogging/Constants.py`). Texts meant to be edited by hand are the exception: `Resources/dialogs/messages.toml`.
