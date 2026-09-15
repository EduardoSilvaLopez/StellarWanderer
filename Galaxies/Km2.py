import random
import Galaxies.Constants
from Galaxies.Rock import Rock

class Km2:

    SIZE = 1000  # Size of a Km2 in meters (1 km x 1 km)

    def __init__(self, parent_world, longitude, latitude, saved_alterations):
        self.parent_world = parent_world
        self.longitude = longitude
        self.latitude = latitude
        self.seed = (self.longitude + self.latitude + self.parent_world.seed) % Galaxies.Constants.SEEDS_SCALING

        self.is_altered = False
        self.saved_alterations = None
        alteration_key = self.get_alterations_key()
        if saved_alterations is not None and alteration_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alteration_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        my_random = random.Random(self.seed)
        rocksCount = my_random.gauss(50, 10)
        self.rocks = []
        for i in range(int(rocksCount)):
            self.add_rock(longitude + my_random.randint(0, 1000), latitude + my_random.randint(0, 1000))

    def get_alterations_key(self):
        return str(self.longitude) + " " + str(self.latitude)

    def set_altered(self):
        self.is_altered = True
        self.parent_world.set_altered()

    def add_rock(self, longitude, latitude):
        newRock = Rock(self, longitude, latitude, self.saved_alterations)
        self.rocks.append(newRock)
        return newRock

    def get_alterations(self):
        alterations = dict()
        if self.is_altered:
            for rock in self.rocks:
                if rock.is_altered:
                    alterations[rock.get_alterations_key()] = rock.get_alterations()
        if alterations == {}:
            return None
        return alterations
