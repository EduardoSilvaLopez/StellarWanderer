import random
import Galaxies.Constants
from Galaxies.Rock import Rock

class Km2:

    def __init__(self, parent_world, longitude, latitude):
        self.parent_world = parent_world
        self.longitude = longitude
        self.latitude = latitude
        self.seed = (self.longitude + self.latitude + self.parent_world.seed) % Galaxies.Constants.SEEDS_SCALING

        my_random = random.Random(self.seed)
        rocksCount = my_random.gauss(100, 20)
        self.rocks = []
        for i in range(int(rocksCount)):
            self.add_rock(my_random.randint(0, 1000), my_random.randint(0, 1000))

    def add_rock(self, x, z):
        newRock = Rock(self, x, z)
        self.rocks.append(newRock)
        return newRock
