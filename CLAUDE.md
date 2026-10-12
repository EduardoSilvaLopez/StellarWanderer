# Stellar Wanderer - Coding Guide

## Project Summary

**Stellar Wanderer** is a proof-of-concept space exploration game with realistic scale. Procedurally generated worlds, time compression (1x to 1,000,000x), and persistence via alteration tracking (only player changes saved, world regenerated from seed on load).

See `DEVLOG.md` for architecture deep-dive and design rationale.

## Coding Standards

**Type Hints**: Every function and method must have type hints on all parameters and a return type annotation. Use `-> None` for procedures that don't return a value.

- **Scope**: Applies to new code and any function being edited.
- **Pattern**: Use `from __future__ import annotations` to support forward references (already in `Player.py`).

**Module names**: Use Python-style snake_case for module files (`stellar_system.py`, not `StellarSystem.py`). This is the standard for new files and for files with significant changes; existing files are not renamed in bulk. Git on Windows does not record case-only renames (`core.ignorecase` is on), so a renamed module can stay tracked under its old case, which breaks imports on case-sensitive systems: rename with `git mv a.py tmp.py` then `git mv tmp.py b.py`, and check that `git ls-files` shows the new case.

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
- `Galaxies/People/player.py`: Player state + movement (module-level `current_player`; imported as `Galaxies.People.player`)
- `Galaxies/`: Procedural world structure (Galaxy, StellarSystem, Orbit, World, Km2, Rock)
- `Graphics/`: OpenGL rendering (Cockpit, DeepSpace, NearestWorld, Rocks, and `Laser.py`, which only draws the beam)
- `Spaceships/`: Ship, `scanner.py` (`Scanner`, reached as `ship.scanner`: aiming, targeting of rocks and ore mines, ore collection via `activate`) and `laser.py` (`Laser`, reached as `ship.laser`: the firing state and heating the targeted rock, via `fire`/`cease_fire`). The scanner decides what is targeted; the laser only fires at it.
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
- The ship's eye height above the ground while bound is `Ship.HEIGHT` (4 m). Its altitude never goes below it, and the spawn height and the descent limit use it too.
- The scanner's beam (`Scanner.update_target`, drawn by `Graphics/Laser.py` while `Laser.firing` is set, i.e. SPACE held on a rock or on nothing), while bound, is a shallow slope from the emitter (`Scanner.emitter_offset()`, half of `Ship.HEIGHT`, below the camera) down to the ground at `Scanner.MAX_LENGTH` metres ahead, so it hits the ground at full range. Rocks closer than the slope's height at their distance pass over the beam. The target it finds (`targeted_rock`, `targeted_mine`) is what the scanner panel (`Graphics/Instruments/scanner.py`, a different class with the same name) shows, and what `Scanner.activate` heats or collects from.
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

## Worlds in the sky

- Every world drawn in the sky (planets and moons) is a sphere lit by its star: `Graphics/lit_worlds.py` intersects each pixel's view ray with the sphere, so the silhouette is exact and the shade is the cosine between the surface normal and the direction to the star (colour = `WORLD_ALBEDO` tinted by the star's colour, plus `WORLD_AMBIENT_LIGHT`). Worlds too small to see are drawn as a small lit disc (`WORLD_MIN_RADIUS_PX`).
- While unbound, all worlds are lit this way, including the nearest one (`LitWorlds.draw_nearest`). While bound, every world except the nearest is lit; the nearest is the disc below the horizon, lit by the sun like the ground (`NearestWorld.draw_surface`, given `SurfaceLight.ground_colour()`), see Surface light.
- Draw order in `OpenGLGui.draw`: worlds farther than the star, the star, worlds nearer than the star, then the nearest world.

## Outposts

- Outposts belong to planets (`World.outposts`, a dict keyed by `"lon lat"`; the initial planet always has at least one). Their surface position is `World.surface_point_stellar`, and `Outpost.stellar_position(t)` moves them with the planet.
- Outposts of planets within `Player.BRAKING_RADIUS_MULTIPLE` radii of the ship get a label with name and distance (`ObjectLabels`), bound and unbound, always. Their tiny dot (`Graphics/outpost_markers.py`, drawn after the worlds) is shown only while unbound, when they face the ship. A dot is hidden when the outpost is on the far side of its planet, the label is not.
- The world map (`Graphics/Instruments/world_map.py`, bound only) shows the outposts of a planet as white dots with their names. The name goes towards the middle of the map (left of the dot in its right half, below it in its upper half) and is kept inside the map. It also shows the ore mines of the world (`World.registered_mines`) as small yellow crosses, and the player as a bright dot; rocks are not shown.
- **Map zoom** (`WorldMap`): while the mouse is over the map, the header shows the scale (`1 px = ...`) instead of the world's name, and the mouse wheel zooms in logarithmic steps, always centred on the ship (the ship's dot stays at the middle of the map). The levels are fixed scales in metres per pixel (1, 2, 5, 10, ... down to `MIN_SCALE`, 1 m/px), after the whole-world map, which is level 0 (`WorldMap._scale_levels`); one step means the same on every world. A zoomed map uses the same scale on both axes and the flat offsets from the ship (as the 3D view does), wraps longitude around the world, and draws the world's boundary where it falls. When the mouse leaves the map, it goes back to the whole world and the name returns. The map shows outposts, mines and the ship, nothing else (no rocks). `main` polls the mouse once per frame (`WorldMap.set_mouse`) and routes `MOUSEWHEEL` to `WorldMap.zoom` while bound.
- An outpost is a flat building, 12 m x 6 m x 3 m (`Outpost.WIDTH/DEPTH/HEIGHT`), drawn by `Graphics/outposts.py` with `Resources/textures/outpost.png` (lit windows painted on the walls, a sealed airlock door, the entity emblem beside the door, no openings). The door is in the middle of a long wall and faces `Outpost.orientation` (degrees clockwise from north). The atlas is generated by `Tools/generate_outpost_texture.py`; replace the PNG by hand, keeping the layout.
- While bound, the 3D view draws the ground flat from the surface offsets (`longitude - player.x`, `latitude - player.z`), so the outpost label uses those offsets too. Longitude metres are not ground metres away from the equator (the sphere geometry scales them by cos(latitude)); the flat view is the one the player sees, so anything drawn in the 3D view must use the flat offsets.
- Rocks are not generated within 11.7 m (the building's half-diagonal + 5 m) of an outpost (`Km2`).
- Outposts are targetable by the scanner (`Scanner.is_outpost_targeted`, the building box with the door on local +z, so `orientation` is the heading the door faces), but the beam does nothing to them yet. They are not saved yet and not yet affected by the laser or the ground.

## Surface light

- While bound, the ground, ore fields, mines, outposts and rocks are lit by the sun, with no shadows. `Graphics/surface_light.py` (`SurfaceLight`) is built once per frame in `OpenGLGui.draw` from `Player.direction_to_star` (already in the surface frame: x east, y up, z north, the axes every object uses) and is passed down to the renderers.
- Brightness of a surface = `SURFACE_STARLIGHT` + (1 - starlight) × max(0, normal · sun). `SURFACE_STARLIGHT` is a floor from the stars, the same from every direction, so the night stays readable. The ground's colour is `LitWorlds.light_tint` (`WORLD_ALBEDO` tinted by the star), so the dark side is the starlight share of it.
- Each face is shaded from its own normal, computed on the CPU into vertex colours (no GL lighting state). Rocks add their heat glow (`rock.color` above `initial_color`) after shading, so a hot rock still glows on the dark side.
- Outposts no longer use fixed face shades; the window and band paint in the textures dim with the rest at night.

## Dialogs

- Dialogs are modal and live in `Dialogs/`. A `Dialog` never runs its own loop: the host feeds it events and shows its surface, as an overlay above the frozen game (`Dialog.compose_overlay` through `OpenGLGui.draw(dialog_surface=...)`) or alone in the startup window (`run_in_window`).
- **Opening a dialog pauses game time.** While `main.open_starting_dialog` (or any future modal loop) runs, nothing that advances game time is called, and the frame timer is restarted afterwards so the next `dt` does not include the dialog's time.
- **Message dialogs** (`MessageDialog`): a textured panel (`Resources/textures/dialog_background.png`), Orbitron title and Oxanium body at size 20 (`Resources/fonts/`, SIL OFL, licence files next to them; the body font is `FONT_FILE` in `Graphics/Constants.py`, also used by the instruments through `Graphics/FontCache.py`; characters the font lacks, such as Δ, are drawn with the system monospace font by `Graphics/fallback_font.py` (`FallbackFont`), so every label that uses these fonts must go through `FontCache` or `dialog_fonts`, not `pygame.font` directly), one or more buttons (side by side when they fit, otherwise stacked). A button press closes the dialog with the result `('close', index)`, `index` being the button's position in the message (0 first); Esc gives `('close', None)`. Enter and Space press the focused button (the first at the start; Tab, Left, Right and the mouse move the focus). Their texts live in `Resources/dialogs/messages.toml` (one section per message: `title`, `text`, and `button` or a list `buttons`; `{placeholders}` are filled from game data; re-read from disk every time a message opens, so editing the file needs no restart). Game code calls `show_message('key', on_result=callback, name=value, ...)` and never opens a modal loop itself: `main` opens pending messages at the start of the next frame through `run_modal_dialog`, and then calls `callback(index)` (`None` for Esc) if one was given, since the message cannot return its answer to the caller that asked for it. Used by the `welcome` message, shown at the start of a *new* game, and the outpost messages.
- Esc opens the *starting dialog* (`StartingDialog`: new game, load a savefile, Exit game); Esc inside it resumes the game. Esc no longer quits; the Exit game button (or closing the window) does.

## Radar

- Shown only while unbound, in the centre console panel where the world map is drawn while bound (`Graphics/Instruments/radar.py`).
- It lists the star and every world of the system within 100 AU. The ellipse is the ship's forward/right plane (forward at the top). The foot of each bar is the object's projection on that plane, with in-plane distance on a log scale from 100 km (centre) to 100 AU (edge). The bar runs along the ship's up axis: white upwards when above the plane, gray downwards when below, with a log length on the same scale. The dot at its tip is the star's own colour or light brown for a world.

## Dependencies

- `pygame-ce`: Window, input, OpenGL context
- `PyOpenGL`: 3D graphics
- `numpy`: shading of lit worlds (`Graphics/lit_worlds.py`, with `pygame.surfarray`)
- Python stdlib: datetime, logging, random, math, os, sys

## Key Notes

- Frame cost: software surfaces are uploaded to OpenGL as BGRA straight from `surface.get_buffer()` (`OpenGLGui._upload_texture`; 32-bit BGRA surfaces only, other formats fall back to `image.tostring`), and the console background is scaled once and cached as a per-pixel-alpha surface (`get_console_background`). Both were measured at about 14 ms per frame each; avoid per-frame `pygame.transform.scale` of full-window surfaces and per-frame `image.tostring`.
- Window size: always use `pygame.display.get_window_size()` for rendering size and mouse mapping, never `screen.get_size()`. For the OpenGL window pygame keeps returning a surface of the size first requested (1920×1080) while the real client area is smaller (window frame), which crops the frame and shifts mouse positions.
- Window position/size: `center_window_on_screen()` in `main.py` uses Windows API via ctypes to center the 1920×1080 main window
- Logging: `GameLogging.configure_logging()` called at app startup; logs to console + `Logs/stellar_wanderer.log` (ISO8601 timestamps)
- No external config files — all settings in module-level constants (e.g., `GameLogging/Constants.py`). Texts meant to be edited by hand are the exception: `Resources/dialogs/messages.toml`.
