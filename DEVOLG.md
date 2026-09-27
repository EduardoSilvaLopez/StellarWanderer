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

### 2026-09-18 (5/8)

Rocks have tilt, they are also more buried.

Unquere the Km2 far away but... no, do not take them from memory, this is unnecessary (they are only the altered ones).

DAMN.

My whole strategy means unvisited altered rocks are not updated to the game time when saved.
I have to update anyway, there is no 'updating window' - or - I must save the 'last changed at' on every object.
... this prolly includes separating the children from the date_time in the alteration dictionaries anyway.

### 2026-09-21 (6/8)

Still stuck with the update problematic. I need a new strategy. A clear one, and a *SCALABLE* one. Keeping all altered objects in the world updating is, let us be honest, not scalable.

So... let us make saved alterations just this, saved alterations. One-use thing, not correctly typified, used for save and load and that was it.

Let us store next and last updates in memory, and queue and dequeue.

Extra time: 20:00 - 21:30

Stuck in the new singleton strategy, which creates lots of problems, damn it.

### 2026-09-22 (7/8)

New release! As the alterations are now saved and recovered.

### 2026-09-23 (8/8)

Stuck at: too rapid movement provokes no environment -> Resolved.
Starting to set mines. Plan:
1) Rocks get a "composition". It is only a [0.0, 1.0[ range.
2) A new composition ("ore rich") gives a reserved color palette (yellow-ish)
3) Rocks near and in front of the ship are presented in a scanner, together with "size" and "ore" %.
4) Heating the rock over 10,000° provokes that the floor is painted with the color of the rock and the rock disappears. This is two alterations: one in the world ("ore field") and another in the rock ("molten").

On extra time
5) The player gets an inventory: mines and ore.
6) Mines can be placed. It position and orientation come from the ship.
7) Once placed, mines start accumulating ore.
8) "Laser" the mine collects the ore.

### 2026-09-27 (1/9)
Here. The mine did not seem to update correctly after absent... corrected.

MAKE AND MOVE THE SUN
1) Create the size and color of the sun.
2) Create and update the position of the world - here. Created, but not updated during gameplay.

Extra time: +7h00' + 17:45-

My specs to the AI:
I want to show the star around which the world is orbiting, in the sky, for the player. This is a complex task. I have divided it in these packages:
1) Define and use a "stellar" system of coordinates for the local star. The origin of coordinates is the center of the star. The +x direction is towards the initial position of the world in its orbit (which is then at x = +world.parent_orbit.distance_from_star ), y perpendicular on the plane of the orbit and z towards the north pole of the planet.
2) Calculate the position of the planet in this system of coordinates, taking in consideration that it is now in a new position of its circular orbit, determined by world.current_orbital_position, which shows the degrees, the planet moving in clockwise direction as seen from the north.
3) Calculate the position of the player in this new system of coordinates, taking in account that "longitude" represents actually the meters moved *in the equator* of a spherical planet, and "latitude" the meters moved *from that point of the equator* north and south. Handling this allows to convert both numbers into a point in a sphere. I accept that this is not how the real longitude works.
4) Take in account that the world rotates along the north / south axis (which is the same as defined by the orbital plane - there is no tilt ) and that initially the  point of the surface represented locally by (0,0) was directly pointing towards the star, that is: in the EPOCH time, the star was directly over the player, and the player was in the equator.
5) Once the position of the player relative to the star is established, use this to find out the position of the star relative to the player, taking in account that he is over a sphere, with his own "z" representing the direction towards the center of the planet, and the "x" and "z" representing the existing (pseudo) longitude and latitude.
6) Once the position of the star relative to the player is established, draw the star in the right scale, using its "color" and "radius".

Evaluate this way to split the task, ask questions required to resolve it, and propose a place to write the logic (in contrast to "current player's view") in "Galaxies" instead of "Graphic", as these are "facts about the world" which belong in the model and not in the Graphic namespace.

3) Transform the player coordinates and orientation into stellar coordinates.
4) Use this data to represent the sun in the right position.

- Set mines: Proof of concept essentially finished. They allow to collect "ore" when you laser them.
- Make and show the sun.
- Move away from world. This includes the sphere-to-rectangle transformation and the disappearance of the "environment" for the player.
- Create and show the planet and all its moons, establishing the initial world as one of them.
- Create the concept of "attached" world, which determines how to interpret the coordinates of the ship. Make a manual detach / attack possible in a buffer zone.
- Move the moons around their orbit, moving the ship with the attached world only. If none, as the coordinates are relative to the sun, it is "left behind".
- Allow travel to another moon of the planet, or to it.
- Make and show "trade posts", where the ore can be sold.
- Create the other orbits, with planets (asteroids would require a radar, if realistic).
- Allow travel to the sun and other planets. Create the concept of forbidden area (too near the star).
- Make the real stars around the one we are.
- Allow travel to other stellar systems.
- https://github.com/obra/superpowers#how-it-works
- Create Jovian planets, with a forbidden area.
- Make the worlds real spheres.

### Learning Python:

https://docs.python.org/3.14/tutorial/modules.html