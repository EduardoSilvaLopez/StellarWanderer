from cmath import pi
import datetime
from Galaxies.Km2 import Km2

class Player:
    singleton = None
    
    # Altitude boundaries (in meters)
    MIN_ALTITUDE = 10
    MAX_ALTITUDE = 20000
    # Base altitude change rate: 1 meter per second at time scale 1
    BASE_ALTITUDE_CHANGE_RATE = 1  # meters per second
    BASE_LONGITUDE_CHANGE_RATE = 10  # meters per second
    BASE_LATITUDE_CHANGE_RATE = 10  # meters per second

    # Time compression, in ship-seconds per real second. Keypad +/- steps by 10x.
    EPOCH = datetime.datetime(500, 1, 1)
    TIME_SCALE_MIN = 1
    TIME_SCALE_MAX = 1_000_000
    TIME_SCALE_STEP = 10

    def __init__(self):
        self.date_time = datetime.datetime(500, 1, 1)  # Default starting date and time
        self.time_scale = 1  # Default time scale
        self.position = type('Position', (object,), {})()  # Create a simple object to hold position attributes
        self.position.Km2 = None
        self.position.x = 0
        self.position.y = 0
        self.position.z = 0
        Player.singleton = self        

    def __str__(self):
        return f"Player in a world with radius {self.position.Km2.parent.radius}, altitude {self.position.y}, coordinates ({self.position.x}, {self.position.z})"

    def spawn_in_environment(self, environment):
        ''' Spawn the player in the given environment, just using the first place we find.'''
        self.position.Km2 = environment.galaxy.stellar_systems[0].orbits[0].worlds[0].Km2s[0]
        self.position.x = self.position.Km2.longitude + 500
        self.position.y = 10
        self.position.z = self.position.Km2.latitude + 500
        return self  # Return self to allow method chaining

    def position_in_km2(self, km2, x, y, z):
        ''' Set the player in a specific Km2 and coordinates.'''
        self.position.Km2 = km2
        self.position.x = x
        self.position.y = y
        self.position.z = z
        return self  # Return self to allow method chaining

    def increase_time_scale(self):
        self.time_scale = min(self.time_scale * self.TIME_SCALE_STEP, self.TIME_SCALE_MAX)

    def decrease_time_scale(self):
        self.time_scale = max(self.time_scale // self.TIME_SCALE_STEP, self.TIME_SCALE_MIN)

    def update_position(self, delta_time, longitude_change, altitude_change, latitude_change):
        self.update_coordinates(delta_time, longitude_change, altitude_change, latitude_change)
        self.ensure_surroundings()

    def update_coordinates(self, delta_time, longitude_change, altitude_change, latitude_change):
        """
        Update the player's position based on time scale and delta time.
        
        Args:
            delta_time: Time elapsed in game seconds
            altitude_change: Change in altitude (1 for increase, -1 for decrease, 0 for no change)
            longitude_change: Change in longitude (1 for increase, -1 for decrease, 0 for no change)
            latitude_change: Change in latitude (1 for increase, -1 for decrease, 0 for no change)
        """
        # Update longitude, east to west of viceversa crossing the anti-meridian.
        if longitude_change != 0:
            change_in_mts = longitude_change * self.BASE_LONGITUDE_CHANGE_RATE * delta_time
            self.position.x += change_in_mts

            if self.position.x < -pi * self.position.Km2.parent_world.radius:
                self.position.x += pi * self.position.Km2.parent_world.radius * 2
            elif self.position.x > pi * self.position.Km2.parent_world.radius:
                self.position.x -= pi * self.position.Km2.parent_world.radius * 2

        # Update altitude, clamp between MIN and MAX
        if altitude_change != 0:
            change_in_mts = altitude_change * self.BASE_ALTITUDE_CHANGE_RATE * delta_time
            
            self.position.y = max(
                self.MIN_ALTITUDE, 
                min(self.MAX_ALTITUDE, self.position.y + change_in_mts)
            )

        # Update latitude, clamping between the north and south poles.
        if latitude_change != 0:
            change_in_mts = latitude_change * self.BASE_LATITUDE_CHANGE_RATE * delta_time
            self.position.z += change_in_mts

            self.position.z = max(
                -pi * self.position.Km2.parent_world.radius / 2,
                min(pi * self.position.Km2.parent_world.radius / 2, self.position.z)
            )

    def ensure_surroundings(self):
        """
        Ensure the player is within the bounds of the current Km2 and its world.
        If the player is outside, find the correct Km2 or generate it, and update the player's position accordingly.
        """
        if (self.position.Km2.longitude <= self.position.x < self.position.Km2.longitude + Km2.SIZE and
            self.position.Km2.latitude <= self.position.z < self.position.Km2.latitude + Km2.SIZE):
            return  # Player is within the current Km2

        # Player is outside the current Km2, find the correct Km2
        new_longitude = (self.position.x // Km2.SIZE) * Km2.SIZE
        new_latitude = (self.position.z // Km2.SIZE) * Km2.SIZE
        world = self.position.Km2.parent_world
        new_km2 = next((km2 for km2 in world.Km2s if km2.longitude == new_longitude and km2.latitude == new_latitude), None)
        if new_km2:
            self.position.Km2 = new_km2
            return

        # If the Km2 does not exist, create it
        self.position.Km2 = world.add_Km2(new_longitude, new_latitude)
        return
