import random
import Galaxies.Constants
from Galaxies.Orbit import Orbit

class StellarSystem:

    def __init__(self, parent_galaxy, x, y, z, saved_alterations):
        ''' Using galactic coordinates here. Whatever that may mean in the future (unit will prolly not meters).'''
        self.parent_galaxy = parent_galaxy
        self.x = x
        self.y = y
        self.z = z
        self.seed = (self.x + self.y + self.z + self.parent_galaxy.seed) % Galaxies.Constants.SEEDS_SCALING
        my_random = random.Random(self.seed)
        self.orbits = []

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)

        self.name = self.generate_name(my_random)

    def get_alterations_key(self):
        return str(self.x) + " " + str(self.y) + " " + str(self.z)

    def set_altered(self):
        self.is_altered = True
        self.parent_galaxy.set_altered()

    def get_alterations(self):
        alterations = dict()
        if self.is_altered:
            for orbit in self.orbits:
                if orbit.is_altered:
                    alterations[orbit.get_alterations_key()] = orbit.get_alterations()
        if alterations == {}:
            return None
        return alterations

    def generate_name(self, my_random):
        """Generate a random name for the world."""
        vocals = "aeiouaeio" # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for sylIdx in range(1, my_random.randint(3, 6)):
            if (my_random.random() < 0.4):
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if (my_random.random() < 0.4):
                name += my_random.choice(consonants)

        if (my_random.random() < 0.5):
            name += "eia"

        return name.capitalize()

    def add_orbit(self, distance_from_star):
        new_orbit = Orbit(self, distance_from_star, self.saved_alterations)
        self.orbits.append(new_orbit)
        return new_orbit
