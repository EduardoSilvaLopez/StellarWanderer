import random
import Galaxies.Constants
from Galaxies.Km2 import Km2

class World:

    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000
    SURROUNDINGS_RADIUS = 2

    def __init__(self, parent_orbit, degrees_in_orbit, saved_alterations):
        self.parent_orbit = parent_orbit
        self.degrees_in_orbit = degrees_in_orbit
        self.seed = (self.degrees_in_orbit + self.parent_orbit.seed) % Galaxies.Constants.SEEDS_SCALING
        my_random = random.Random(self.seed)
        self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        while self.radius <= 0:
            self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        self.Km2s = []

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.name = self.generate_name(my_random)

    def get_alterations_key(self):
        return str(self.degrees_in_orbit)

    def set_altered(self):
        self.is_altered = True
        self.parent_orbit.set_altered()

    def get_alterations(self):
        alterations = dict()
        if self.is_altered:
            for km2 in self.Km2s:
                if km2.is_altered:
                    alterations[km2.get_alterations_key()] = km2.get_alterations()
        if alterations == {}:
            return None
        return alterations                    

    def add_Km2(self, longitude, latitude, game_date_time):
        new_Km2 = Km2(self, longitude, latitude, self.saved_alterations)
        self.Km2s.append(new_Km2)
        return new_Km2

    def generate_name(self, my_random):
        """Generate a random name for the world."""
        vocals = "aeiouaeio" # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for sylIdx in range(1, my_random.randint(3, 6)):
            if (my_random.random() < 0.5):
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if (my_random.random() < 0.5):
                name += my_random.choice(consonants)
        
        return name.capitalize()

    def ensure_surroundings(self, longitude, latitude, player_date_time):
        """Ensure the surroundings of the player are generated."""
        for lon_delta in range(-World.SURROUNDINGS_RADIUS, World.SURROUNDINGS_RADIUS):
            for lat_delta in range(-World.SURROUNDINGS_RADIUS, World.SURROUNDINGS_RADIUS):
                target_longitude = longitude + lon_delta * Km2.SIZE
                target_latitude = latitude + lat_delta * Km2.SIZE

                if not any(km2.longitude == target_longitude and km2.latitude == target_latitude for km2 in self.Km2s):
                    self.add_Km2(target_longitude, target_latitude, player_date_time)
