from __future__ import annotations
from typing import TYPE_CHECKING

import random
import Galaxies.Constants
from Galaxies.Orbit import Orbit
if TYPE_CHECKING:
    from Galaxies.Galaxy import Galaxy

class StellarSystem:

    def __init__(self, parent_galaxy: Galaxy, x: int, y: int, z: int, saved_alterations: dict):
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
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.name = self.generate_name(my_random)

    def set_altered(self) -> StellarSystem:
        self.is_altered = True
        self.parent_galaxy.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.x) + " " + str(self.y) + " " + str(self.z)

    def get_alterations(self) -> dict:
        alterations = dict()
        if self.is_altered:
            for orbit in self.orbits:
                if orbit.is_altered:
                    alterations[orbit.get_alterations_key()] = orbit.get_alterations()
        if alterations == {}:
            return None
        return alterations

    def generate_name(self, my_random: random.Random):
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

    def add_orbit(self, distance_from_star: int):
        new_orbit = Orbit(self, distance_from_star, self.saved_alterations)
        self.orbits.append(new_orbit)
        return new_orbit
