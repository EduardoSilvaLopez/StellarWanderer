import random

from GalaxyChunk import GalaxyChunk

class GameEnvironment:
    singleton = None

    def __init__(self, galacticSeed):
        self.galaxy = GalaxyChunk(galacticSeed)
        self.current_world = self.galaxy.add_child().add_child().add_child() # by default
        print("Initial planet's radius: " + str(self.current_world.radius))
        GameEnvironment.singleton = self
