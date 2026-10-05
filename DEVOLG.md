# DEVELOPMENT LOG

## Vision
Learn modern technologies by building a prototype of a game I always dreamed about.

## Mission
Learn Python, a modern IDE, GitHub and Claude Code (AI), creating a prototype for a solo space game with realistic dimensions (time included), which implies never saving the world itself but only the changes caused by the player. The setting is the “world after the disaster” of my sci-fi concept, in the year 700.

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
3) Transform the player coordinates and orientation into stellar coordinates.
4) Use this data to represent the sun in the right position.

On extra time:
5) Adjust distance from star to star type, to make the star more visible :) . Ok, it does not work bcs it is not realistic in all fucking games worldwide :D .
Rocks look strange in the north pole. Trying to correct this: Looks corrected, test still.

Extra time: +10h15'

### 2026-09-28 (2/9)

Oktoberfest. Remaining extra time +8h

### 2026-09-29 (3/9)

Oktoberfest. Remaining extra time +5h45'

### 2026-09-30 (4/9)

Oktoberfest. Remaining extra time +3h30'

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

### 2026-10-04

Big leap but it does not work right now as intended: the movements are not correct, "s" does not reduce pitch. q/r should change the orientation relative to ship current left-right-forward-backward plane (it does not). left-right-forward-backward should also be relative to the ships orientation and pitch.

### 2026-10-05

Extra time: 5h15'

- Alt bar, orientation and world map disappear when unbound - and back.
- Altitude, latitude and longitude are renamed to x/y/z when unbound - and back.
- Calculate and log the position and velocity of the planet on unbind and bind.
- x / y / z are recalculated on unbinding: the position is recalculated (cylinder-to-real-long-lat, then to x-y-z, then world to stellar), the velocity is recalculated (also what x / y / z means) to add the one of the planet at that instant.
- Altitude, latitude and longitude are recalculated on binding: the position is recalculated (stellar to world, then to real long-lat, then to cylinder long-lat), the velocity is recalculated to substract the one of the planet at that instant.
- New controls to roll, pitch and yawn when unbound.

- Move the world.
- Alt bar shows the current distance-to-nearest-planet, and its radius and binding altitude.
- ⁠Create more than one orbit, each with one world.
- Show the other planets in the sky.

BACKLOG
- PLANETS AND MOONS
- TRAVELLING TO ANOTHER MOON
- TRADE POSTS
- Create the other orbits, with planets (asteroids would require a radar, if realistic).
- Allow travel to the sun and other planets. Create the concept of forbidden area (too near the star).
- Make the real stars around the one we are.
- Allow travel to other stellar systems.
- https://github.com/obra/superpowers#how-it-works
- Create Jovian planets, with a forbidden area.
- Make the worlds real spheres.

### Learning Python:

https://docs.python.org/3.14/tutorial/modules.html