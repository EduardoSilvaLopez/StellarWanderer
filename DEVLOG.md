# DEVELOPMENT LOG

## Vision
Learn modern technologies by building a prototype of a game I always dreamed about.

## Mission
Learn Python, a modern IDE, GitHub and Claude Code (AI), creating a prototype for a solo space game with realistic dimensions (time included), which implies never saving the world itself but only the changes caused by the player. The setting is the “world after the disaster” of my sci-fi concept, in the year 700.

## Log (after 2026-10-01, see Git for history)

### 2026-10-01 (5/9)

Oktoberfest. Remaining extra time +1h15'

INERTIAL MOVEMENT:
- WASD inertial movement.
- (extra) Give % of year and day in the world map.
- Show the velocity in WASX.
- Substitude D with X.
- D brings the ship to stop.
- Include angular movement.
- Include altitude (avoiding crash).

ABANDON THE WORLD:
Move away from world. This includes the sphere-to-rectangle transformation and the disappearance of the "environment" for the player when they are too high. Also to tilt the ship.
- Change altitude meter to make it relative to radius, the max on radius. 
- On altitude over radial distance, stop generating Km2's (check they are generated again if back down).
- Trigger "unbind" when alt = radius. Just log it.
- Trigger "bind" when alt = radius / 2. Just log it.

### 2026-10-04 (6/9)

Big leap but it does not work right now as intended: the movements are not correct, "s" does not reduce pitch. q/r should change the orientation relative to ship current left-right-forward-backward plane (it does not). left-right-forward-backward should also be relative to the ships orientation and pitch.

### 2026-10-05 (7/9)

- Alt bar, orientation and world map disappear when unbound - and back.
- Altitude, latitude and longitude are renamed to x/y/z when unbound - and back.
- Calculate and log the position and velocity of the planet on unbind and bind.
- x / y / z are recalculated on unbinding: the position is recalculated (cylinder-to-real-long-lat, then to x-y-z, then world to stellar), the velocity is recalculated (also what x / y / z means) to add the one of the planet at that instant.
- Altitude, latitude and longitude are recalculated on binding: the position is recalculated (stellar to world, then to real long-lat, then to cylinder long-lat), the velocity is recalculated to substract the one of the planet at that instant.
- New controls to roll, pitch and yawn when unbound.
- Move the world. Make approximation playable (break relative to planet).
- Binding bar shows the current distance-to-nearest-planet, velocity, radius and binding altitude.

### 2026-10-06 (8/9)
- Many GUI improvements including radar and distance to objects in the window.
- Create more than one orbit.

### 2026-10-07 (9/9)
- Create automatically at least one world per orbit. Load and save correctly, no more "add".
- Show the other worlds in the sky.
- Hide / eliminate the current "stars".
- Wasted a lot of time with the political thing... but ok, title now available, icon.

### 2026-10-08 (1/10)

- Update "nearest_world" (plan already made)
... ok, we need more help. Show speed relative to nearest world? -> Resolved!

PLANETS AND MOONS started.
- Rename "World" to "Planet" at this point. Make then Planet and Moon derive from World.

- Make the model, load / save.

... here, load and save. Have to think about it with a fresh mind.
... no, all this is wrong. Go back and start again.
... done.

- Refresh nearest world
- Refresh radar
- Heavily use Claude for drawing
- Indication of rock temperature.
- Indication when approaching the planet in a dangerous speed (must start breaking)

DIALOGS:
- Improving the way worlds are seen, first.
- Ore prevalence for planets, affects the composition of rocks.
- Test the drawing of planets in outbound...

OUTPOSTS:
- Generate outposts in planets only.
- Mark the outposts in the world map.
- Mark the outposts in the unbound view of the planet.
- Remove rocks too near an outpost.
- Draw the outposts.

### 2026-10-11 (2/10)
- Refactor laser, creating scanner and eliminating duplicate logic.
- Scan the outposts (just a symbol for now... later, faces?)
- "Laser hit" when outposts in scan, now opens dialog.

- Outpost has an alteration, "last visited".
- Less rich ore in planet.
- Depending on reply, more reputation is lost when no ore, or "what now?" dialog appears.
- Reputation is lost anyway on any new visit, just not so much if increased by the ore.

### 2026-10-12 (3/10)
- Mark mines in the world map with "x".
- Initial daylight illumination.
- New font for almost everything.
- Change the seeds to make them more variated.
- Ore field remaining ore is shown.
- Augmentation for the world wmap.
- Make a realistic run... it may be the definitive one...
- People are identified by seed, and save their own data.
- People have also alterations, including the personal history with the player.

### 2026-10-13 (4/10)
- Bigger outposts.
- Yaw / pitch / roll go to 0 when time scale > 1. This never made sense.
- How to approach the planet better ("Approaching")
- More realistic rocks.

* De-capitalise *.py file names (small task)

CONVERSATIONS
- Installation package (tested locally - to be distributed)
- Almanack
- show_message directly
- Conversations architecture.

### 2026-10-14 (5/10)
- Fill up the conversations concept with current data.
- Introduce conversation report in the person, save and load it.
- Recalculate the loss of reputation with resources provison.
- Expend energy, air, water and food during flight / passing of time / laser usage.
- Fill up the person with the communication record.
- Title depends on *relative* sympathy, and is mentioned.

### 2026-10-15 (6/10)
- Better structure of the ships whereabouts (big refactoring)
- Bigger rocks
- Finish the normal dialogs.
- Reintroduce the cash question.
- Text in buttons smaller.
- Person almanack.

RELEASE "The Three Powers" created, with installer.

* MAINTENANCE
  * Extra: Real orbits
  * Energy expense by move and laser. And show it.
  * Maintenance bar, show it.
  * Extra: Move the zommed map on left-click + drag.
  * Death by resource expenditure.
  * Extra: Spherification: Cancelled, study made.

* BETTER STARTING DIALOG:
  * More beautiful.
  * Save games with a name.
  * Overwrite saves.
  * "Instructions" screen.
  * Delete saves.
  * Extra: Directories revamp, including snake_case.

* ICARUS: Travel to the sun.
  * Vertical bars for the warning in maintenance (later temperature)
  * Credits bar (hidden)
  * Better-looking instruments on the left side.
  * Temperature: Bar, death conditions.
  * Sun can be nearest.
  * Temperature: Changes
  * Approaching replenishes energy.
  * Halo of the star changes when near enough (but not too near...)
  * Make the star cooler: flares, areas, effects on ship, temperature effects on vision.
  * Approaching replenishes energy.
  * Halo of the star changes when near enough (but not too near...)
  * Make the star cooler: flares, areas, effects on ship, temperature effects on vision.
  * Ruff installed... we're getting better with Python!

* FULL OF STARS (work with chunks of the galaxy)
  * Phase 1: Left-handedness (was not necessary)
  * Phase 2: Isolate the star constructor
  * Phase 3: Fixed stars in memory
  * Phase 4: The system receives the fixed star
  * Phase 5: Show the fixed stars in the sky
  * Extra: Bug search in all

* ASTEROIDS (I)
  * Targeted body, not nearest body.
  * Small reogranisation of data subdirectory.
  * Mines cannot be placed too far near from each other.
  * "Target" control created to match "in no fixed zone" (no body is near enough to trigger coordinate change)
  * Less ore in the initial super-moon.
  * Rock colors a bit brighter.

Extra time: 58h30' + 13:30 - 15:15

* MISSIONS
  * 

# BACKLOG
* ASTEROIDS (II)
  * Asteroid belt similar to fixed stars, for a star. Only shown where near enough (radar, label).
  * Place one in initial system, not too far away.
  * Outpost gives coordinates as prize?
  * Extra: Better structure in all (files which have the same problem player and ship had). Method sorting.
  * Open: Ages of people still too similar?

In-Game almanack... must be saved, part of the save file.

* OROGRAPHY
  * Craters
  * Terrain elevation / sinkage.
  * Mountains.
* JOVIAN PLANETS (with forbidden area)
* INTERSTELLAR TRAVEL (now 3 coordinate systems, 'unbind' from the stellar system)
  * Extra: Ȼ are marked as illegal cargo in Those-Who-Share, as cargo in Shining Throne and as essential resource in UniDiv.
* AI PERSONALITY?
* ATMOSPHERE
  * Even suggestions of life?
* CIVILISATION:
  * Bigger outposts.
  * Cities in unterraformed planets.
  * Inhabited asteroids.
* SPHERIC WORLD MAP FOR TERRESTRIAL PLANETS
* SMALL TASKS
  * Getting energy from the star when near enough.
* ON QUOTA OR HALLUCIONATION PROBLEMS:
  * https://github.com/obra/superpowers#how-it-works

### Learning Python:

https://docs.python.org/3.14/tutorial/modules.html

# EDITION TRICKS

Fold All Regions (Ctrl+K Ctrl+8)
Go to Symbol in File (Ctrl+Shift+O) lists the methods, and typing : groups them by kind.
Fold Level 2 (Ctrl+K Ctrl+2) collapses every method body, so the class turns into a list of signatures.