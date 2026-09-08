import math


class Laser:
    LENGTH = 500  # metres
    POSITION_OFFSET = 5  # metres, offset from camera to avoid culling

    def __init__(self, ship):
        self.ship = ship  # Reference to the ship that owns this laser
        self.firing = False  # Laser firing
        self.length = Laser.LENGTH
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
        self.end_y = self.ship.owner.position.y
        self.end_z = self.ship.owner.position.z + self.ship.laser.length * forward_z

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

    def get_hit_rock(self, world):
        if (not self.firing or not world.rocks):
            return None
        if (self.ship.owner.position.current_world != world):
            return None  # not in the same world, can't hit rocks of another world
        if (self.ship.owner.position.y < 0):
            return None  # below ground, can't hit rocks
        