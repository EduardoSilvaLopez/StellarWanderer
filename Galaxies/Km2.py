import random
import Galaxies.Constants
from Galaxies.Rock import Rock

class Km2:

    SIZE = 1000  # Size of a Km2 in meters (1 km x 1 km)

    def __init__(self, parent_world, longitude, latitude):
        self.parent_world = parent_world
        self.longitude = longitude
        self.latitude = latitude
        self.seed = (self.longitude + self.latitude + self.parent_world.seed) % Galaxies.Constants.SEEDS_SCALING

        my_random = random.Random(self.seed)
        rocksCount = my_random.gauss(100, 20)
        self.rocks = []
        for i in range(int(rocksCount)):
            self.add_rock(longitude + my_random.randint(0, 1000), latitude + my_random.randint(0, 1000))

    def add_rock(self, longitude, latitude):
        newRock = Rock(self, longitude, latitude)
        self.rocks.append(newRock)
        return newRock
