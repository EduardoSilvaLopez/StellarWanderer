# DEVELOPMENT LOG

## Vision
Learn modern technologies by building a prototype of a game I always dreamed about.

## Mission
Learn Python, a modern IDE, GitHub and Claude Code (AI), creating a prototype for a solo space game with realistic dimensions (time included), which implies never saving the world itself but only the changes caused by the player. The setting is the “world after the disaster” of my sci-fi concept, in the year 700.

## Log (after last release, see Git for history)

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

* MISSIONS
  * In-game almanacks (saving systems known even if unchanged)
  * Eliminate file almanacks.
  * When next level: offer in show_message to check new button (missions)
  * 0x Speed
  * Implement generate_missions better, depending on time passed.

### 2026-10-18 (7/10)

  * Offers can disappear bcs somebody took them, regardless of deadline.
  * Temperature by rock melting increased.
  * Angular brake corrected.
  * Made the start somehow harder, only 2 mines, cost more, get only enough not to bring rep < 0, ore gives less reputation.
  * Some sounds implemented (document in "ideas")
  * DeliverPackage mission.
  * Extra: Scroll bars can be dragged.
  * Log reputation changes better. Missions.
  * Extra: More realistic world colors.
  * Altitude brake made independent per axis.
  * Extra: Galaxy
  * Show the orbit of targeted (or fixed).

### 2026-10-19 (8/10)

  * Extra: Improved realism of the astronomical layout of stellar systems.
  * Extra: Use INITIAL_ORE_MAX, limit how much ore can be brought in.
  
Extra time: 72h45' + 7:45 - 10:00

  * Extra: New game - force yellow initial star.
  * Extra: If ore is ore max, pale yellow in cargo hold.
  * Esc: close - eliminate, but also, right-mouse brings you back from one dialog to another.
  * Extra: Reorganise instruments to give more space to the bar.
  * reward_text depends on player
  * Extra: heat radius depend now on Ships temp reduction, which must also be saved.
  * Scan object mission (finish testing)
  * Package missions - who benefits? Improve. Give sympathy, for example, say who sent and who received.
  * Rest of sounds

# BACKLOG
* ASTEROIDS (II)
  * Asteroid belt similar to fixed stars, for a star. Only shown where near enough (radar, label).
  * Place one in initial system, not too far away.
  * Outpost gives coordinates as prize?
  * Extra: Better structure in all (files which have the same problem player and ship had). Method sorting.
  * Extra: Download more faces of the main races.
  * Extra: Latinos.
* OROGRAPHY
  * Craters
  * Terrain elevation / sinkage.
  * Mountains.
  * Extra: Arabs.
* JOVIAN PLANETS (with forbidden area)
  * Extra: Indians incl. Sikh. Put a Sikh also on each race and gender, only one. Dialog - what is that on your head?
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

### Edition tricks

Fold Level 2 (Ctrl+K Ctrl+2) collapses every method body, so the class turns into a list of signatures.
Fold All Regions (Ctrl+K Ctrl+8)
Go to Symbol in File (Ctrl+Shift+O) lists the methods, and typing : groups them by kind.