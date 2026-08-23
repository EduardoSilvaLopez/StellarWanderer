from enum import Enum
import random

class GalaxyChunk:
    """A part of a galaxy self, which can be a galaxy, stellar system, orbit, world, or square kilometer chunk."""
    SEED_SCALING = 1000000000
    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000

    class Size(Enum):
        Galaxy = 1
        StellarSystem = 2
        Orbit = 3
        World = 4
        Km2 = 5

    def __init__(self, seed, size=Size.Galaxy, parent=None):
        self.seed = seed
        self.random = random.Random(seed)
        self.seedUsages = 0
        self.size = size
        self.children = []
        self.parent = None

        if size == GalaxyChunk.Size.World:
            self.radius = self.random.gauss(GalaxyChunk.EARTHLIKE_RADIUS_AVERAGE, GalaxyChunk.EARTHLIKE_RADIUS_SIGMA)
            while self.radius <= 0:
                self.radius = self.random.gauss(GalaxyChunk.EARTHLIKE_RADIUS_AVERAGE, GalaxyChunk.EARTHLIKE_RADIUS_SIGMA)

    def add_child(self):
        if self.size.value >= GalaxyChunk.Size.Km2.value:
            raise Exception(
                "Square Km chunks cannot have children."
            )
        newChild = GalaxyChunk(self.random.randint(1, GalaxyChunk.SEED_SCALING), GalaxyChunk.Size(self.size.value + 1), self)
        self.children.append(newChild)
        return newChild

    def get_child(self, idx):
        if idx < 0 or idx >= len(self.children):
            return Exception("Child index " + str(idx) + " out of range")
        return self.children[idx]