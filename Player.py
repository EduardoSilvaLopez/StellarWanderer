from cmath import pi


class Player:
    singleton = None
    
    # Altitude boundaries (in meters)
    MIN_ALTITUDE = 10
    MAX_ALTITUDE = 20000
    # Base altitude change rate: 1 meter per second at time scale 1
    BASE_ALTITUDE_CHANGE_RATE = 1  # meters per second
    BASE_LONGITUDE_CHANGE_RATE = 10  # meters per second
    BASE_LATITUDE_CHANGE_RATE = 10  # meters per second

    def __init__(self):
        self.environment = None
        self.position = type('Position', (object,), {})()  # Create a simple object to hold position attributes
        self.position.currentWorld = None
        self.position.worldChunk = None
        self.position.x = 0
        self.position.y = 0
        self.position.z = 0
        Player.singleton = self        

    def __str__(self):
        return f"Player in a world with radius {self.position.currentWorld.radius}, altitude {self.position.y}, coordinates ({self.position.x}, {self.position.z})"

    def set_in_environment(self, gameEnvironment):
        self.environment = gameEnvironment
        self.position.currentWorld = gameEnvironment.galaxy.children[0].children[0].children[0] # by default
        self.position.worldChunk = self.position.currentWorld.children[0] # by default
        self.position.x = 500
        self.position.y = 10
        self.position.z = 500
        print(self)
        return self  # Return self to allow method chaining

    def position_in(self, world_seed, world_chunk_seed, x, y, z):
        if self.environment is None:
            raise ValueError("Player is not in any environment. Please set the environment first.")
               
        # Implementation for setting position in the environment
        world_found = False
        for stellar_system in self.environment.galaxy.children:
            for orbit in stellar_system.children:
                for world in orbit.children:
                    if world.seed == world_seed:
                        self.position.currentWorld = world
                        world_found = True
                        break
                if world_found: 
                    break
            if world_found: 
                break

        if not world_found:
            raise ValueError(f"World with seed {world_seed} not found in the galaxy.")

        chunk_found = False
        for chunk in self.position.currentWorld.children:
            if chunk.seed == world_chunk_seed:
                self.position.worldChunk = chunk
                chunk_found = True
                break

        if not chunk_found:
            raise ValueError(f"World chunk with seed {world_chunk_seed} not found in the world.")

        self.position.x = x
        self.position.y = y
        self.position.z = z
        return self  # Return self to allow method chaining

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
