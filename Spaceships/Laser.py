from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Tuple

import math
if TYPE_CHECKING:
    from Spaceships.Ship import Ship
    from Galaxies.World import World
    from Galaxies.Rock import Rock


class Laser:
    MAX_LENGTH = 500  # metres
    POSITION_OFFSET = 5  # metres, offset from camera to avoid culling
    TEMP_RISE_RATE = 1000.0  # degrees per second, rate at which rock temperature rises when hit by laser, when the rock is 1 cubic meter.

    def __init__(self, ship: Ship) -> None:
        self.ship = ship
        self.firing = False
        self.hitting_rock: Optional[Rock] = None
        self.length = Laser.MAX_LENGTH
        self.start_x = 0.0
        self.start_y = 0.0
        self.start_z = 0.0
        self.end_x = 0.0
        self.end_y = 0.0
        self.end_z = 0.0

    def fire(self) -> None:
        """Fire the laser, calculate where it starts and ends based on the ship's position and orientation."""
        self.firing = True

        # Compute laser endpoint: forward vector is (sin(θ), 0, cos(θ))
        orientation = math.radians(self.ship.owner.orientation)
        forward_x = math.sin(orientation)
        forward_z = math.cos(orientation)

        # Offset start point slightly ahead and below camera to avoid culling
        self.start_x = self.ship.owner.position.x + forward_x * 5.0
        self.start_y = self.ship.owner.position.y - Laser.POSITION_OFFSET
        self.start_z = self.ship.owner.position.z + forward_z * 5.0

        self.end_x = self.ship.owner.position.x + self.ship.laser.length * forward_x
        self.end_y = self.ship.owner.position.y - Laser.POSITION_OFFSET
        self.end_z = self.ship.owner.position.z + self.ship.laser.length * forward_z

        # Find out rocks hit by the laser and adjust the endpoint if necessary
        hit_rock_tuple = self.get_hit_rock(self.ship.owner.position.Km2.parent_world)

        # Adjust endpoint to the closest rock hit, if any
        if hit_rock_tuple:
            self.hitting_rock = hit_rock_tuple[0]
            closest_t = hit_rock_tuple[1]

            # Adjust the endpoint to the intersection point using the t-value
            # The intersection point is: start + t * (end - start)
            self.end_x = self.start_x + closest_t * (self.end_x - self.start_x)
            self.end_z = self.start_z + closest_t * (self.end_z - self.start_z)
         
    def cease_fire(self) -> None:
        if (not self.firing):
            return
        self.firing = False
        self.start_x = 0
        self.start_y = 0
        self.start_z = 0
        self.end_x = 0
        self.end_y = 0
        self.end_z = 0

    def get_hit_rock(self, world: World) -> Optional[Tuple[Rock, float]]:
        ''' Returns not only the rock but its t_value'''
        if (not self.firing):
            return None
        if (self.ship.owner.position.Km2.parent_world != world):
            raise ValueError("Laser's ship is not in the provided world.")
        if (self.ship.owner.position.y < 0):
            raise ValueError("Laser's ship is below the surface of the world.")
        if self.ship.owner.position.y - self.ship.laser.length > 100:
            return None

        # First, exclude fully irrelevant Km2s based on the player's position and the laser's length. This is a rough filter to avoid unnecessary checks.
        relevant_km2 = []
        for km2 in world.Km2s:
            if km2.longitude <= self.ship.owner.position.x - self.ship.laser.length - km2.SIZE or km2.longitude >= self.ship.owner.position.x + self.ship.laser.length:
                continue  # km2 is too far in longitude
            if km2.latitude <= self.ship.owner.position.z - self.ship.laser.length - km2.SIZE or km2.latitude >= self.ship.owner.position.z + self.ship.laser.length:
                continue  # km2 is too far in latitude
            relevant_km2.append(km2)

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
            dx = world_x - rock.x
            dy = world_y - rock.y
            dz = world_z - rock.z
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
