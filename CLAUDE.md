# Stellar Wanderer - Coding Guide

## Project Summary

**Stellar Wanderer** is a proof-of-concept space exploration game with realistic scale. Procedurally generated worlds, time compression (1x to 1,000,000x), and persistence via alteration tracking (only player changes saved, world regenerated from seed on load).

See `DEVOLG.md` for architecture deep-dive and design rationale.

## Coding Standards

**Type Hints**: Every function and method must have type hints on all parameters and a return type annotation. Use `-> None` for procedures that don't return a value.

- **Scope**: Applies to new code and any function being edited.
- **Pattern**: Use `from __future__ import annotations` to support forward references (already in `Player.py`).

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
- `Persistency/`: Save/load (Savefile, StartDialog)
- `GameLogging/`: Logging config (Constants, Setup)
- `Updating/`: Time-based updates (UpdateQueue, Updatable)

## Ship Attitude and Controls

Use these names consistently; do not introduce synonyms.

- **Yaw**: rotation about the ship's up axis (Q/E). `Player.yaw` is the heading in degrees clockwise from north, derived from the forward axis. `Player.velocity.yaw` is the yaw rate in degrees per second.
- **Pitch**: rotation about the ship's right axis (K9 nose up, K3 nose down, only while unbound). `Player.pitch_angle(world, t)` is the nose-up angle above the local horizon. `Player.velocity.pitch` is the pitch rate.
- **Attitude**: the ship's right, up and forward axes, stored as `Player.right`, `Player.up` and `Player.forward` in the active frame (surface when bound, stellar when unbound). This is the source of truth; yaw and pitch are derived from it or applied to it.
- Rotation accelerations and speed limits share `Ship.ANGULAR_ACC` and `Ship.MAX_ANGULAR_SPEED`.
- Rock and mine `orientation` and rock `tilt` are different concepts and keep their names.

## Dependencies

- `pygame-ce`: Window, input, OpenGL context
- `PyOpenGL`: 3D graphics
- Python stdlib: datetime, logging, random, math, os, sys

## Key Notes

- Window position/size: `center_window_on_screen()` in `main.py` uses Windows API via ctypes to center the 1920×1080 main window
- Logging: `GameLogging.configure_logging()` called at app startup; logs to console + `Logs/stellar_wanderer.log` (ISO8601 timestamps)
- No external config files — all settings in module-level constants (e.g., `GameLogging/Constants.py`)
