from cmath import pi
import datetime
import Galaxies

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

    def position_in(self, km2, x, y, z):
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

    def update_altitude(self, delta_time, time_scale):
        """
        Adjust player altitude based on time scale and delta time.
        
        At time_scale=1, altitude changes by 1 meter per second.
        At higher time scales, altitude changes proportionally faster.
        
        Args:
            delta_time: Time elapsed in real seconds
            time_scale: Current time compression scale (e.g., 1, 10, 100, 1000)
        """
        # Calculate altitude change: base_rate * time_scale * delta_time
        altitude_change = self.BASE_ALTITUDE_CHANGE_RATE * time_scale * delta_time
        
        # Update altitude and clamp between MIN and MAX
        self.position.y = max(
            self.MIN_ALTITUDE, 
            min(self.MAX_ALTITUDE, self.position.y + altitude_change)
        )

    def update_longitude(self, world, delta_time, time_scale):
        """
        Adjust player longitude based on time scale and delta time.
        
        At time_scale=1, longitude changes by 1 meter per second.
        At higher time scales, longitude changes proportionally faster.
        
        Args:
            delta_time: Time elapsed in real seconds
            time_scale: Current time compression scale (e.g., 1, 10, 100, 1000)
        """
        # Calculate longitude change: base_rate * time_scale * delta_time
        longitude_change = self.BASE_LONGITUDE_CHANGE_RATE * time_scale * delta_time
        
        # Update longitude (assuming x-axis represents longitude)
        self.position.x += longitude_change
        if self.position.x < -pi * world.radius:
            self.position.x += pi * world.radius * 2
        elif self.position.x > pi * world.radius:
            self.position.x -= pi * world.radius * 2

    def update_latitude(self, world, delta_time, time_scale):
        """
        Adjust player latitude based on time scale and delta time.
        
        At time_scale=1, latitude changes by 1 meter per second.
        At higher time scales, latitude changes proportionally faster.
        
        Args:
            delta_time: Time elapsed in real seconds
            time_scale: Current time compression scale (e.g., 1, 10, 100, 1000)
        """

        # No south of south pole or north of north pole
        if self.position.z <= -pi * world.radius / 2:
            self.position.z = -pi * world.radius / 2
        elif self.position.z >= pi * world.radius / 2:
            self.position.z = pi * world.radius / 2
        else:
            # Calculate latitude change: base_rate * time_scale * delta_time
            latitude_change = self.BASE_LATITUDE_CHANGE_RATE * time_scale * delta_time

            # Update latitude (assuming z-axis represents latitude)
            self.position.z += latitude_change
