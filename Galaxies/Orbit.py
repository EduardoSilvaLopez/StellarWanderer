import Galaxies.Constants
from Galaxies.World import World

class Orbit:

    def __init__(self, parent_stellar_system, distance_from_star, saved_alterations):
        self.parent_stellar_system = parent_stellar_system
        self.distance_from_star = distance_from_star
        self.seed = (self.distance_from_star + self.parent_stellar_system.seed) % Galaxies.Constants.SEEDS_SCALING
        self.worlds = []

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)

    def get_alterations_key(self):
        return str(self.distance_from_star)

    def set_altered(self):
        self.is_altered = True
        self.parent_stellar_system.set_altered()

    def get_alterations(self):
        alterations = dict()
        if self.is_altered:
            for world in self.worlds:
                if world.is_altered:
                    alterations[world.get_alterations_key()] = world.get_alterations()
        if alterations == {}:
            return None
        return alterations

    def add_world(self, degrees_in_orbit):
        new_world = World(self, degrees_in_orbit, self.saved_alterations)
        self.worlds.append(new_world)
        return new_world
