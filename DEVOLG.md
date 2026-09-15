# DEVELOPMENT LOG

## Vision
Learn modern technologies by building a prototype of a game I always dreamed about.

## Mission
Learn Python, a modern IDE, GitHub and Claude Code (AI), creating a prototype for a solo space game with realistic dimensions (time included), which implies never saving the world itself but only the changes caused by the player. The setting is the “world after the disaster” of my sci-fi concept, in the year 500.

## Log

### 2026-09-07 (3/7)

Introducing this log, previous version is the OpenOffice Write document "Vission, Mission, Log.odt"

### 2026-09-08 (4/7)

Laser logic moved to its own object.

### 2026-09-09 (5/7)

Calculate real end of the laser, so lasers hit rocks.
The rock is hit and its temperature has risen... but it does not show. Also, not saving the increased temp yet.

### 2026-09-10 (6/7) 10:00 - 11:45

### 2026-09-13 (7/7) 15:30 - 17:15

Refactor "alterations" to include the datetime.
Saved and loaded the alterations. This works BUT applying afterwards, does not.
Stuck there in a circular import. And ugly code around it. World.ensure_surroundings.

### 2026-09-14 (1/8) 13:00 - 14:45

Laser essentials look finished :)

## ToDo

- Show z coordinate, generate planet name.
- Laser cooling.
- Prompt for loading a file.
- Set flagpoles: Proof of concept essentially finished.
- Stones have different orientations and altitudes.
- Show orientation in the instruments.
- https://github.com/obra/superpowers#how-it-works
- Make and show the sun.
- Move away from world.
- Create and show the planet and all its moons, establishing the initial world as one of them.
- Create the concept of "attached" world, which determines how to interpret the coordinates of the ship. Make a manual detach / attack possible in a buffer zone.
- Move the moons around their orbit, moving the ship with the attached world only. If none, as the coordinates are relative to the sun, it is "left behind".
- Allow travel to another moon of the planet, or to it.
- Create the other orbits, with planets (asteroids would require a radar, if realistic).
- Allow travel to the sun and other planets. Create the concept of forbidden area (too near the star).
- Make the real stars around the one we are.
- Allow travel to other stellar systems.
- Create Jovian planets, with a forbidden area.

### Learning Python:

https://docs.python.org/3.14/tutorial/modules.html