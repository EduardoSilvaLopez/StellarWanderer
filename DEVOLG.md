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

### 2026-09-10 (6/7)

### 2026-09-13 (7/7)

Refactor "alterations" to include the datetime.
Saved and loaded the alterations. This works BUT applying afterwards, does not.
Stuck there in a circular import. And ugly code around it. World.ensure_surroundings.

### 2026-09-14 (1/8)

Laser essentials look finished :)

### 2026-09-15 (2/8)

Rocks more lively (orientation, buried). Star and planet name.

Laser cooling: new feature.
- Propagate the alterations_timestamp ? So that on re-create, it can be compared with Player's time.
- The caller must be give the time difference? time_passed? Makes sense as external callers know the player, add because of it. Is somehow counter-intuitive.

### 2026-09-16 (3/8)

Laser cooling. Thoughts.
- The moment of re-creation is clearly "add".
- There is no "unload" yet. Later a queue, and special events when joining the queue? A queue of events sorted by time. "Update" as concept. There is an "apply saved alterations" (in the constructor) but then again an "update" to new dates.

### 2026-09-17 (4/8)

Update queue works. Now we have not only to put new objects in, but take them out when they fall out of scope. Out of memory or out of update? Seems that out of update could be enough, out of memory means saving
silently, which looks like something we do only when we abandon the world. A memory of 800.000.000 Km or more is however daunting. We could keep only the altered ones! Yep, that's the trick.

Done. All altered Km2 are "immortal", keep being updated even if far away. In a next step, this should be changed... "saved alterations" becomes "last alterations" and is overwritten when dequeue? As for now, better move to other things and so test the current implementation a bit.
- Did not test if they are SAVED even if war away.

### 2026-09-18 (5/8), extra day, 11:00-12:45, 16:00-

Rocks have tilt, they are also more buried.

Unquere the Km2 far away but... no, do not take them from memory, this is unnecessary (they are only the altered ones).

## ToDo

- Laser cooling II: saved alterations > last alterations, so that it Km2 can be "dequeued" when far away.
- World map.
- https://github.com/obra/superpowers#how-it-works
- Set flagpoles: Proof of concept essentially finished.
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