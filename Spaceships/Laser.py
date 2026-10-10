from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple

import math
if TYPE_CHECKING:
    from Spaceships.Ship import Ship
    from Galaxies.world import World
    from Galaxies.km2 import Km2
    from Galaxies.Rock import Rock
    from Galaxies.ore_mine import OreMine


class Laser:
    MAX_LENGTH = 500  # metres
    POSITION_OFFSET = 5  # metres, offset from camera to avoid culling
    TEMP_RISE_RATE = 2000.0  # degrees per second, rate at which rock temperature rises when hit by laser, when the rock is 1 cubic meter.

    def __init__(self, ship: Ship) -> None:
        self.ship = ship
        self.firing = False
        self.hitting_rock: Optional[Rock] = None
        self.targeted_rock: Optional[Rock] = None
        self.targeted_mine: Optional[OreMine] = None
        self.length = Laser.MAX_LENGTH
        self.start_x = 0.0
        self.start_y = 0.0
        self.start_z = 0.0
        self.end_x = 0.0
        self.end_y = 0.0
        self.end_z = 0.0

    def update_aim(self) -> None:
        """Recompute the beam's start/end points and the currently targeted rock
        from the ship's current position and yaw. Called once per frame
        regardless of whether the laser is actually firing, so UI elements (like
        the scanner) can show what's in the crosshair at all times."""
        owner = self.ship.owner
        if not owner.is_bound:
            # Nothing can be in range while unbound. The beam is stored relative to
            # the ship, along its attitude axes (below the camera, like when bound).
            self.targeted_rock = None
            self.targeted_mine = None
            self.start_x, self.start_y, self.start_z = (
                f * 5.0 - u * Laser.POSITION_OFFSET for f, u in zip(owner.forward, owner.up)
            )
            self.end_x, self.end_y, self.end_z = (
                f * self.length - u * Laser.POSITION_OFFSET for f, u in zip(owner.forward, owner.up)
            )
            return

        # No Km2 while bound means too high, means no aim.
        if owner.position.km2 is None:
            self.targeted_rock = None
            self.targeted_mine = None
            return

        # Forward vector is (sin(θ), 0, cos(θ)). The beam starts just below and ahead of the camera and
        # ends on the ground (altitude 0, the surface) at MAX_LENGTH metres ahead, so it is a shallow
        # slope from the emitter down to the ground at full range.
        yaw = math.radians(self.ship.owner.yaw)
        forward_x = math.sin(yaw)
        forward_z = math.cos(yaw)

        # Offset start point slightly ahead and below camera to avoid culling
        self.start_x = self.ship.owner.position.x + forward_x * 5.0
        self.start_y = self.ship.owner.position.y - Laser.POSITION_OFFSET
        self.start_z = self.ship.owner.position.z + forward_z * 5.0

        self.end_x = self.ship.owner.position.x + self.length * forward_x
        self.end_y = 0.0
        self.end_z = self.ship.owner.position.z + self.length * forward_z

        # Find out which rock and which mine, if any, are currently in the
        # beam's path, then keep only whichever is closest — the nearer one
        # occludes the other.
        import GameEnvironment as gem
        world = gem.current_environment.nearest_world
        hit_rock_tuple = self.get_hit_rock(world)
        hit_mine_tuple = self.get_hit_mine(world)

        candidates = []
        if hit_rock_tuple:
            candidates.append(('rock', hit_rock_tuple[0], hit_rock_tuple[1]))
        if hit_mine_tuple:
            candidates.append(('mine', hit_mine_tuple[0], hit_mine_tuple[1]))

        if candidates:
            kind, target, closest_t = min(candidates, key=lambda candidate: candidate[2])
            self.targeted_rock = target if kind == 'rock' else None
            self.targeted_mine = target if kind == 'mine' else None

            # Adjust the endpoint to the intersection point using the t-value
            # The intersection point is: start + t * (end - start)
            # The beam slopes down to the ground, so the height moves with it too, or the drawn
            # end would sit below the point the beam really hits.
            self.end_x = self.start_x + closest_t * (self.end_x - self.start_x)
            self.end_y = self.start_y + closest_t * (self.end_y - self.start_y)
            self.end_z = self.start_z + closest_t * (self.end_z - self.start_z)
        else:
            self.targeted_rock = None
            self.targeted_mine = None

    def fire(self) -> None:
        from Spaceships.CargoHold import CargoHold
        import GameEnvironment as gem

        """Start firing the laser; damage applies to whatever is currently targeted."""
        self.hitting_rock = self.targeted_rock

        '''If no rock but a mine, transfer the ore to the ship.'''
        if not self.hitting_rock and self.targeted_mine:
            world: World = gem.current_environment.nearest_world
            tgt_mine: OreMine = self.get_hit_mine(world)
            if tgt_mine is not None and tgt_mine[0].content > 0:
                self.ship.cargo_hold.content[CargoHold.CargoElement.ORE] += tgt_mine[0].content
                tgt_mine[0].content = 0

        self.firing = not self.targeted_mine

    def cease_fire(self) -> None:
        if (not self.firing):
            return
        self.firing = False
        self.hitting_rock = None

    def _relevant_km2(self, world: World) -> List[Km2]:
        '''Exclude fully irrelevant km2s based on the player's position and the laser's length. This is a rough filter to avoid unnecessary checks.'''
        if (self.ship.owner.position.y < 0):
            raise ValueError("Laser's ship is below the surface of the world.")
        if self.ship.owner.position.y - self.length > 100:
            return []

        relevant_km2 = []
        for km2 in world.km2s:
            if km2.longitude <= self.ship.owner.position.x - self.length - km2.SIZE or km2.longitude >= self.ship.owner.position.x + self.length:
                continue  # km2 is too far in longitude
            if km2.latitude <= self.ship.owner.position.z - self.length - km2.SIZE or km2.latitude >= self.ship.owner.position.z + self.length:
                continue  # km2 is too far in latitude
            relevant_km2.append(km2)
        return relevant_km2

    def get_hit_rock(self, world: World) -> Optional[Tuple[Rock, float]]:
        ''' Returns the closest rock currently in the beam's path, and its t_value, regardless of firing state.'''
        relevant_km2 = self._relevant_km2(world)

        # Analyse each rock to see if it is hit by the laser. This is a more precise check.
        # Return the one with the minimum t_value.
        hit_rock = None
        hit_at_t_value = self.MAX_LENGTH
        for rock in (rock for km2 in relevant_km2 for rock in km2.rocks):
            t_value = self.is_rock_hit(rock)
            if t_value is not None and t_value < hit_at_t_value:
                hit_rock = rock
                hit_at_t_value = t_value
        return (hit_rock, hit_at_t_value) if hit_rock else None

    def get_hit_mine(self, world: World) -> Optional[Tuple[OreMine, float]]:
        ''' Returns the closest ore mine currently in the beam's path, and its t_value, regardless of firing state.'''
        relevant_km2 = self._relevant_km2(world)

        hit_mine = None
        hit_at_t_value = self.MAX_LENGTH
        for mine in (mine for km2 in relevant_km2 for field in km2.ore_fields for mine in field.mines):
            t_value = self.is_mine_hit(mine)
            if t_value is not None and t_value < hit_at_t_value:
                hit_mine = mine
                hit_at_t_value = t_value
        return (hit_mine, hit_at_t_value) if hit_mine else None

    def is_rock_hit(self, rock: Rock) -> Optional[float]:
        """Determine if the laser hits a rock and return the t-value of the intersection.

        Rocks are cubes of size rock.size, and the laser is a line segment from
        (start_x, start_y, start_z) to (end_x, end_y, end_z).

        Returns the t-value (0 to 1) where the laser first enters the rock's bounding box,
        or None if no intersection occurs.
        """
        # The cube's bounding box in the rock's fully local (untilted, unrotated) frame,
        # centered on the origin.
        half = rock.size / 2.0
        box_min = -half
        box_max = half

        # Rocks are tilted around their own local Z axis by rock.tilt degrees,
        # THEN rotated around their vertical (Y) axis by rock.orientation degrees,
        # deviating from north (0 = unrotated, positive = clockwise) — the same
        # convention used for the ship's forward vector. Undo both transforms, in
        # reverse order, to bring the laser's endpoints into the rock's local frame.
        tilt = math.radians(rock.tilt)
        cos_t = math.cos(tilt)
        sin_t = math.sin(tilt)
        orientation = math.radians(rock.orientation)
        cos_o = math.cos(orientation)
        sin_o = math.sin(orientation)

        def to_local(world_x: float, world_y: float, world_z: float) -> Tuple[float, float, float]:
            dx = world_x - rock.longitude
            dy = world_y - rock.altitude
            dz = world_z - rock.latitude
            x1 = dx * cos_o - dz * sin_o
            z1 = dx * sin_o + dz * cos_o
            y1 = dy
            x2 = x1 * cos_t + y1 * sin_t
            y2 = -x1 * sin_t + y1 * cos_t
            return x2, y2, z1

        start_x, start_y, start_z = to_local(self.start_x, self.start_y, self.start_z)
        end_x, end_y, end_z = to_local(self.end_x, self.end_y, self.end_z)

        # Laser direction vector, now expressed in the rock's local frame.
        dx = end_x - start_x
        dy = end_y - start_y
        dz = end_z - start_z

        # Use a parametric line equation: P(t) = start + t * direction, where t ∈ [0, 1]
        # Check intersection with the axis-aligned bounding box using the slab method
        t_min = 0.0
        t_max = 1.0

        # Check X axis
        if abs(dx) > 1e-9:  # Avoid division by zero
            t1 = (box_min - start_x) / dx
            t2 = (box_max - start_x) / dx
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray is parallel to X axis; check if ray is within the box's X range
            if start_x < box_min or start_x > box_max:
                return None

        # Check Y axis
        if abs(dy) > 1e-9:  # Avoid division by zero
            t1 = (box_min - start_y) / dy
            t2 = (box_max - start_y) / dy
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray is parallel to Y axis; check if ray is within the box's Y range
            if start_y < box_min or start_y > box_max:
                return None

        # Check Z axis
        if abs(dz) > 1e-9:  # Avoid division by zero
            t1 = (box_min - start_z) / dz
            t2 = (box_max - start_z) / dz
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray is parallel to Z axis; check if ray is within the box's Z range
            if start_z < box_min or start_z > box_max:
                return None

        # If t_min <= t_max, the line segment intersects the box
        # Return t_min (the distance along the laser where it enters the box)
        if t_min <= t_max:
            return t_min
        return None

    def is_mine_hit(self, mine: OreMine) -> Optional[float]:
        """Determine if the laser hits an ore mine and return the t-value of the intersection.

        Mines are vertical cylinders of radius mine.MINE_RADIUS and height mine.MINE_HEIGHT,
        standing on the ground (y in [0, MINE_HEIGHT]) at (mine.longitude, mine.latitude).
        Being rotationally symmetric, no un-rotation is needed, unlike rocks.
        """
        start_x = self.start_x - mine.longitude
        start_z = self.start_z - mine.latitude
        dx = (self.end_x - mine.longitude) - start_x
        dz = (self.end_z - mine.latitude) - start_z
        dy = self.end_y - self.start_y

        t_min = 0.0
        t_max = 1.0

        # Circular cross-section (XZ plane): solve |start + t*d|^2 = radius^2.
        a = dx * dx + dz * dz
        b = 2.0 * (start_x * dx + start_z * dz)
        c = start_x * start_x + start_z * start_z - mine.MINE_RADIUS ** 2
        if abs(a) > 1e-9:
            discriminant = b * b - 4.0 * a * c
            if discriminant < 0:
                return None
            sqrt_discriminant = math.sqrt(discriminant)
            t1 = (-b - sqrt_discriminant) / (2.0 * a)
            t2 = (-b + sqrt_discriminant) / (2.0 * a)
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray doesn't move across the circle; check if its (fixed) position is within radius.
            if c > 0:
                return None

        # Height bounds (Y axis).
        if abs(dy) > 1e-9:
            t1 = (0.0 - self.start_y) / dy
            t2 = (mine.MINE_HEIGHT - self.start_y) / dy
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            if self.start_y < 0.0 or self.start_y > mine.MINE_HEIGHT:
                return None

        if t_min <= t_max:
            return t_min
        return None
