import random

from GalaxyChunk import GalaxyChunk

class GameEnvironment:
    singleton = None

    def __init__(self, galacticSeed):
        self.galaxy = GalaxyChunk(galacticSeed)
        self.current_world = self.galaxy.add_child().add_child().add_child() # by default
        print("Initial planet's radius: " + str(self.current_world.radius))
        self.current_world.add_child() # Add a default world chunk
        GameEnvironment.singleton = self
