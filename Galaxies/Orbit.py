import Galaxies.Constants
from Galaxies.World import World

class Orbit:

    def __init__(self, parent_stellar_system, distance_from_star):
        self.parent_stellar_system = parent_stellar_system
        self.distance_from_star = distance_from_star
        self.seed = (self.distance_from_star + self.parent_stellar_system.seed) % Galaxies.Constants.SEEDS_SCALING
        self.worlds = []

    def add_world(self, degrees_in_orbit):
        new_world = World(self, degrees_in_orbit)
        self.worlds.append(new_world)
        return new_world
