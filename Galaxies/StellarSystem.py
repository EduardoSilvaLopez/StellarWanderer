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
        self.orbits = []

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)

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

    def add_orbit(self, distance_from_star):
        new_orbit = Orbit(self, distance_from_star, self.saved_alterations)
        self.orbits.append(new_orbit)
        return new_orbit
