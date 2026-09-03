import random
import Galaxies.Constants
from Galaxies.Km2 import Km2

class World:

    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000

    def __init__(self, parent_orbit, degrees_in_orbit):
        self.parent_orbit = parent_orbit
        self.degrees_in_orbit = degrees_in_orbit
        self.seed = (self.degrees_in_orbit + self.parent_orbit.seed) % Galaxies.Constants.SEEDS_SCALING
        my_random = random.Random(self.seed)
        self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        while self.radius <= 0:
            self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        self.Km2s = []

    def add_Km2(self, longitude, latitude):
        new_Km2 = Km2(self, longitude, latitude)
        self.Km2s.append(new_Km2)
        return new_Km2

    def ensure_surroundings(self, longitude, latitude):
        """Ensure the surroundings of the player are generated."""

        for lon_delta in range(-2, 2):
            for lat_delta in range(-2, 2):
                target_longitude = longitude + lon_delta * Km2.SIZE
                target_latitude = latitude + lat_delta * Km2.SIZE

                if not any(km2.longitude == target_longitude and km2.latitude == target_latitude for km2 in self.Km2s):
                    self.add_Km2(target_longitude, target_latitude)
