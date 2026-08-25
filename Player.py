class Player:
    singleton = None

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
        self.position.currentWorld = gameEnvironment.galaxy.add_child().add_child().add_child() # by default
        self.position.worldChunk = self.position.currentWorld.add_child()
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