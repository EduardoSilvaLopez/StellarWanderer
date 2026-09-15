import math


class Laser:
    MAX_LENGTH = 500  # metres
    POSITION_OFFSET = 5  # metres, offset from camera to avoid culling
    TEMP_RISE_RATE = 1000.0  # degrees per second, rate at which rock temperature rises when hit by laser, when the rock is 1 cubic meter.

    def __init__(self, ship):
        self.ship = ship  # Reference to the ship that owns this laser
        self.firing = False  # Laser firing
        self.hitting_rock = None
        self.length = Laser.MAX_LENGTH
        self.start_x = 0
        self.start_y = 0
        self.start_z = 0
        self.end_x = 0
        self.end_y = 0
        self.end_z = 0

    def fire(self):
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
        hit_rocks = self.get_hit_rocks(self.ship.owner.position.Km2.parent_world)

        # Adjust endpoint to the closest rock hit, if any
        if hit_rocks:
            # Store the rock that was hit
            self.hitting_rock = min(hit_rocks, key=lambda x: x[1])[0]

            # Find the closest hit rock and use its t-value to adjust the endpoint
            # hit_rocks is a list of (rock, t_value) tuples, where t_value ∈ [0, 1]
            closest_t = min(hit_rocks, key=lambda x: x[1])[1]

            # Adjust the endpoint to the intersection point using the t-value
            # The intersection point is: start + t * (end - start)
            self.end_x = self.start_x + closest_t * (self.end_x - self.start_x)
            self.end_z = self.start_z + closest_t * (self.end_z - self.start_z)
         
    def cease_fire(self):
        if (not self.firing):
            return  # Laser is already not firing

        """Cease firing the laser."""
        self.firing = False
        self.start_x = 0
        self.start_y = 0
        self.start_z = 0
        self.end_x = 0
        self.end_y = 0
        self.end_z = 0

    def get_hit_rocks(self, world):
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
        # Store tuples of (rock, t_value) for rocks that are hit.
        hit_rocks = []
        for rock in (rock for km2 in relevant_km2 for rock in km2.rocks):
            t_value = self.is_rock_hit(rock)
            if t_value is not None:
                hit_rocks.append((rock, t_value))
        return hit_rocks if hit_rocks else None

    def is_rock_hit(self, rock):
        """Determine if the laser hits a rock and return the t-value of the intersection.

        Rocks are cubes of size rock.size, and the laser is a line segment from
        (start_x, start_y, start_z) to (end_x, end_y, end_z).

        Returns the t-value (0 to 1) where the laser first enters the rock's bounding box,
        or None if no intersection occurs.
        """
        # Define the cube's bounding box in the rock's own local (unrotated) frame.
        # Note: rock.x, rock.y and rock.z are all at the CENTER of the rock.
        half = rock.size / 2.0
        box_min_x = -half
        box_max_x = half
        box_min_y = rock.y - half
        box_max_y = rock.y + half
        box_min_z = -half
        box_max_z = half

        # Rocks are rotated around their own vertical (Y) axis by rock.orientation
        # degrees, deviating from north (0 = unrotated, positive = clockwise) —
        # the same convention used for the ship's forward vector. Transform the
        # laser's start/end points into the rock's local frame before testing.
        orientation = math.radians(rock.orientation)
        cos_o = math.cos(orientation)
        sin_o = math.sin(orientation)

        def to_local_xz(world_x, world_z):
            local_x = world_x - rock.x
            local_z = world_z - rock.z
            return (local_x * cos_o - local_z * sin_o, local_x * sin_o + local_z * cos_o)

        start_x, start_z = to_local_xz(self.start_x, self.start_z)
        end_x, end_z = to_local_xz(self.end_x, self.end_z)

        # Laser direction vector (Y is unaffected by rotation around the Y axis)
        dx = end_x - start_x
        dy = self.end_y - self.start_y
        dz = end_z - start_z

        # Use a parametric line equation: P(t) = start + t * direction, where t ∈ [0, 1]
        # Check intersection with the axis-aligned bounding box using the slab method
        t_min = 0.0
        t_max = 1.0

        # Check X axis
        if abs(dx) > 1e-9:  # Avoid division by zero
            t1 = (box_min_x - start_x) / dx
            t2 = (box_max_x - start_x) / dx
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray is parallel to X axis; check if ray is within the box's X range
            if start_x < box_min_x or start_x > box_max_x:
                return None

        # Check Y axis
        if abs(dy) > 1e-9:  # Avoid division by zero
            t1 = (box_min_y - self.start_y) / dy
            t2 = (box_max_y - self.start_y) / dy
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray is parallel to Y axis; check if ray is within the box's Y range
            if self.start_y < box_min_y or self.start_y > box_max_y:
                return None

        # Check Z axis
        if abs(dz) > 1e-9:  # Avoid division by zero
            t1 = (box_min_z - start_z) / dz
            t2 = (box_max_z - start_z) / dz
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            # Ray is parallel to Z axis; check if ray is within the box's Z range
            if start_z < box_min_z or start_z > box_max_z:
                return None

        # If t_min <= t_max, the line segment intersects the box
        # Return t_min (the distance along the laser where it enters the box)
        if t_min <= t_max:
            return t_min
        return None
