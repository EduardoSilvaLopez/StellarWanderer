# Stellar Wanderer - Codebase Documentation

## Project Overview

**Stellar Wanderer** is a proof-of-concept space exploration game demonstrating that a game with realistic scale is technically feasible. It features procedural generation at an astronomical scale—imagine landing on every square meter of a planet's millions of square kilometers of surface, or flying through every cubic meter of a Jovian atmosphere.

**Core Vision**: Create an experience that truly conveys the vastness of the universe.

### Key Constraints Addressed

1. **Procedural Generation**: The world must be procedurally generated—no manual creation of planetary surfaces
2. **Solo Gameplay**: Time compression is essential; otherwise travel would take hours or years in real-time
3. **Smart Persistence**: Save files cannot store the vast amount of generated world data (e.g., 500 trillion square meters per planet). Instead, only changes are saved and re-applied when the player returns

## Technical Architecture

### Hierarchical World Structure

The game uses a nested hierarchy for organizing space:

```
Galaxy
├── StellarSystem (x, y, z coordinates)
│   ├── Orbit (distance_from_star)
│   │   └── World (radius, planet/moon)
│   │       └── Km2 (1km × 1km grid cell, 1000m × 1000m in game units)
│   │           └── Rock (individual terrain features)
└── Player (position + ship)
```

**Key Classes**:

- **Galaxy**: Container for stellar systems, holds the seed for procedural generation
- **StellarSystem**: A star with orbital paths; uses galactic coordinates (x, y, z)
- **Orbit**: A circular path around a star; identified by distance
- **World**: A planet or moon with procedurally generated terrain; radius varies
- **Km2**: 1 km × 1 km grid cell containing rocks; uniquely identified by (longitude, latitude)
- **Rock**: Individual terrain features with physical properties (size, position, temperature)

### Core Game Loop

Located in `main.py`, the loop:

1. Handles input (time scale changes, movement, laser firing, save/load)
2. Updates game time based on time_scale multiplier
3. Updates player orientation (Q/E for rotation)
4. Updates player position with velocity relative to ship orientation
5. Processes laser firing and collision detection
6. Updates the update queue (time-based object updates)
7. Renders the scene via OpenGLGui

### Player and Interaction

**Player** (`Player.py`):
- Controls time scale (Keypad +/- to compress/decompress time, 1x to 1,000,000x)
- Position in 3D space: (x, y=altitude, z) within the current Km2
- Orientation: heading in degrees
- Max altitude: 20,000 meters

**Ship** (`Spaceships/Ship.py`):
- Movement speeds for different axes
- Laser weapon
- Rotation speed

**Laser** (`Spaceships/Laser.py`):
- Fires when SPACE is held
- Can hit rocks and increase their temperature
- Hits detected via ray-casting

### Persistence System

The persistence model is critical to the game's design:

**Save Structure** (`Persistency/Savefile.py`):
- The save file does NOT store the entire world
- It stores only **alterations**: changes made by the player to the procedurally generated world
- Each alteration is tracked with:
  - The object it affects (identified by its coordinates/key)
  - The change (e.g., rock temperature)
  - The timestamp of when it was saved

**Loading Process**:
- When loading a saved game, the world is regenerated using the same seed
- Alterations are re-applied on top of the generated world
- Critical: Alterations include the `date_time` they were saved at; this must be considered when applying them to handle time discrepancies

**Data Flow**:
```
Rock/Km2/World.get_alterations() → dict of changes
↓
Savefile.save() → serialize alterations to file
↓
Load new game → regenerate world from seed
↓
Apply saved_alterations to newly generated objects
```

### Procedural Generation

**Seeding Strategy**:
- Every object (Galaxy, StellarSystem, Orbit, World, Km2, Rock) has a deterministic seed
- Seeds are calculated from parent object's seed + object's position/identifier
- Same seed → same generated object (terrain, rocks, names)
- Used with Python's `random.Random(seed)` for consistency

**Generated Properties**:
- **World**: radius (normal distribution around 5 million meters with 1 million meter sigma)
- **Km2**: number of rocks (~50 ± 10)
- **Rock**: size, position within Km2, orientation, tilt, initial color
- **Names**: Randomly generated for stars, planets, moons

### Update Queue System

The **UpdateQueue** (`Updating/UpdateQueue.py`) manages time-based updates for objects that need periodic processing:

**Problem Solved**: Rocks cool down over time after being heated by the laser. We need to:
- Update only rocks that are hot (temperature > 0)
- Update only rocks that are loaded (within render distance)
- Handle rocks entering/leaving scope without losing their state

**Solution**:
- Each updatable object (`Updating/Updatable.py`) implements `update(game_date_time)` and `get_next_update()`
- The update queue processes objects by their next_update timestamp
- Altered rocks (those with non-zero temperature) are "immortal"—they stay in memory and update when nearby.

**Rock Update Logic** (`Galaxies/Rock.py`):
- Temperature rises when hit by laser (proportional to laser power / rock volume)
- Temperature cools exponentially: `temp *= 0.999` every 60 seconds
- Once temperature drops below 1.0°, goes to zero and stops updating
- State is saved via `get_alterations()` so temperature persists

### Graphics System

Uses **PyOpenGL** for 3D rendering via `Graphics/OpenGLGui.py`:

- **DeepSpace**: Renders the star field and distant worlds
- **NearestWorld**: Renders the closest planet/moon
- **Cockpit**: First-person view of the ship's instruments
- **Laser**: Laser beam visualization
- **Rocks**: 3D terrain rendering (`Graphics/Rocks.py`)
- **Stars**: Star field generation

### Memory and Performance Considerations

**Km2 Loading Strategy** (`Galaxies/World.py`):
- `update_surroundings()` maintains a 7×7 grid of Km2s around the player (3 Km2s in each direction)
- New Km2s are created on demand when needed
- Km2s fall out of scope (outer ring) and stop updating their rocks (if any)

**Issue Being Addressed** (per DEVOLG.md):
- The current strategy of keeping all altered rocks in memory forever is not scalable.
- Future improvement: Implement a "last updated" timestamp per object to properly handle dequeuing

## Module Breakdown

### Top-Level Modules

- **main.py**: Game entry point; main loop; input handling; rendering coordination
- **Player.py**: Player state, position, orientation, input mapping
- **GameEnvironment.py**: Game state singleton; manages Galaxy, current World, date_time
- **FontCache.py**: Caches rendered fonts for UI

### Galaxies/ — Procedural World Structure

- **Galaxy.py**: Container of stellar systems
- **StellarSystem.py**: A star with orbits; generates procedurally
- **Orbit.py**: Circular orbit around a star; contains worlds
- **World.py**: A planet/moon; manages Km2 grid; updates surroundings based on player position
- **Km2.py**: 1km × 1km grid cell; contains rocks; manages their updates
- **Rock.py**: Individual terrain feature; temperature tracking; laser interactions
- **Constants.py**: Shared constants (e.g., seed scaling factor)

### Graphics/ — Rendering

- **OpenGLGui.py**: Main rendering coordinator
- **DeepSpace.py**: Distant space rendering
- **NearestWorld.py**: Close planet/moon rendering
- **Cockpit.py**: First-person instrument panel
- **Laser.py**: Laser beam visualization
- **Rocks.py**: Terrain geometry
- **Stars.py**: Starfield

### Spaceships/ — Vehicle System

- **Ship.py**: Ship definition with movement/rotation speeds
- **Laser.py**: Laser logic and collision detection

### Persistency/ — Save/Load System

- **Savefile.py**: Serialization and deserialization of game state
- **StartDialog.py**: UI for load/new game selection

### Updating/ — Time-Based Updates

- **UpdateQueue.py**: Priority queue of updatable objects sorted by next update time
- **Updatable.py**: Base interface for objects with timed updates

### tests/ — Testing

- **test_nearest_world.py**: Tests for world rendering logic

## Important Patterns

### Alteration Tracking

Objects track whether they're altered via `is_altered` boolean and `saved_alterations` dict:
- Called in constructors to check if loaded alterations exist
- Used in `get_alterations()` to serialize state
- Cascades up the hierarchy: if a child is altered, parent marks itself as altered

### Seed-Based Identity

Objects use deterministic seeds for identity and to inform child generation:
```python
seed = (coordinate + parent_seed) % SEEDS_SCALING
```

This ensures:
- Same coordinates → same object properties
- Deterministic procedural generation
- Consistent world regeneration on load

## Current Development Status

### Completed Features

- ✅ Procedural world generation (galaxy → systems → planets → terrain)
- ✅ Player movement in 3D space with time compression
- ✅ Laser firing and rock heating
- ✅ Laser cooling simulation
- ✅ Save/load system with alteration persistence
- ✅ Update queue for time-based events
- ✅ Rock orientation and tilt
- ✅ Basic graphics rendering

### In Progress

- 🔄 Update queue scalability (issue: keeping all altered rocks in memory forever)
- 🔄 Proper timestamp handling for re-created objects

### Planned Features (from DEVOLG.md)

- World map UI
- Sun rendering and orbital mechanics
- Multi-moon system support
- Jovian planets with atmospheres
- Travel to other stellar systems
- Forbidden zones near stars
- Radar for asteroid detection
- Proper orbital mechanics for moving worlds

## Key Design Decisions

1. **Procedural-First**: All world data is regenerated from seed; only player changes are saved
2. **Time as First-Class Citizen**: Time compression (up to 1M×) is core to the design to make space traversal feasible
3. **Lazy Loading**: Km2s and rocks are only created when needed, not pre-generated
4. **Alteration-Based Persistence**: Only tracks what changed, not the entire world state
5. **Update Queue**: Separates rendering from game logic updates using a time-sorted queue

## Debugging Notes

Common debug output to watch:
- "The surroundings have now X Km2" — World loading
- "Altered rock loaded at X°. Queue size: Y" — Persistence working
- "Temperature reduced: X°. Queue size: Y" — Update queue processing
- Rock coordinate messages when stopping/starting updates

## Dependencies

- **pygame**: Window management, input handling, OpenGL context
- **PyOpenGL**: 3D graphics
- **numpy**: Not directly used in core logic, available in venv
- Python 3.x standard library (datetime, random, math, etc.)
