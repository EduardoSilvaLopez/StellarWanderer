from enum import Enum
import random

from Rock import Rock

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
            self.seedUsages += 1
            while self.radius <= 0:
                self.radius = self.random.gauss(GalaxyChunk.EARTHLIKE_RADIUS_AVERAGE, GalaxyChunk.EARTHLIKE_RADIUS_SIGMA)
                self.seedUsages += 1
        elif size == GalaxyChunk.Size.Km2:
            rocksCount = self.random.gauss(100, 20)
            self.seedUsages += 1
            pendingRocks = rocksCount
            self.rocks = []
            while pendingRocks > 0:
                self.add_rock()
                pendingRocks -= 1

        print(f"Created {self.size.name} with seed {self.seed}.")

    def add_child(self):
        if self.size.value >= GalaxyChunk.Size.Km2.value:
            raise Exception(
                "Square Km chunks cannot have children."
            )
        newChild = GalaxyChunk(self.random.randint(1, GalaxyChunk.SEED_SCALING), GalaxyChunk.Size(self.size.value + 1), self)
        self.seedUsages += 1
        self.children.append(newChild)
        return newChild

    def add_rock(self):
        if self.size != GalaxyChunk.Size.Km2:
            raise Exception(
                "Only square Km chunks can have rocks."
            )
        newRock = Rock(self, self.random.random(), self.random.uniform(0, 500), 0, self.random.uniform(0, 500), self.random.uniform(0, 100))
        self.seedUsages += 4
        self.rocks.append(newRock)
        return newRock

    def get_child(self, idx):
        if idx < 0 or idx >= len(self.children):
            return Exception("Child index " + str(idx) + " out of range")
        return self.children[idx]