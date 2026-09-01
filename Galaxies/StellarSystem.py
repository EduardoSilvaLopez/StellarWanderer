import Galaxies.Constants
from Galaxies.Orbit import Orbit

class StellarSystem:

    def __init__(self, parent_galaxy, x, y, z):
        ''' Using galactic coordinates here. Whatever that may mean in the future (unit will prolly not meters).'''
        self.parent_galaxy = parent_galaxy
        self.x = x
        self.y = y
        self.z = z
        self.seed = (self.x + self.y + self.z + self.parent_galaxy.seed) % Galaxies.Constants.SEEDS_SCALING
        self.orbits = []

    def add_orbit(self, distance_from_star):
        new_orbit = Orbit(self, distance_from_star)
        self.orbits.append(new_orbit)
        return new_orbit
