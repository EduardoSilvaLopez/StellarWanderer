from __future__ import annotations

import random
from datetime import datetime
from typing import List

import Galaxies.Constants
from Galaxies.Km2 import Km2

class World:

    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000
    SURROUNDINGS_RADIUS = 3

    def __init__(self, parent_orbit: int, degrees_in_orbit: float, saved_alterations: dict):
        self.parent_orbit = parent_orbit
        self.degrees_in_orbit = degrees_in_orbit
        self.seed = (self.degrees_in_orbit + self.parent_orbit.seed) % Galaxies.Constants.SEEDS_SCALING
        my_random = random.Random(self.seed)
        self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        while self.radius <= 0:
            self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        self.Km2s: List[Km2] = []

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.name = self.generate_name(my_random)

    def set_altered(self) -> World:
        self.is_altered = True
        self.parent_orbit.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.degrees_in_orbit)

    def get_alterations(self) -> dict:
        alterations = dict()
        if self.is_altered:
            for km2 in self.Km2s:
                if km2.is_altered:
                    alterations[km2.get_alterations_key()] = km2.get_alterations()
        if alterations == {}:
            return None
        return alterations                    

    def add_Km2(self, longitude: int, latitude: int):
        new_Km2 = Km2(self, longitude, latitude, self.saved_alterations)
        self.Km2s.append(new_Km2)
        return new_Km2

    def generate_name(self, my_random: random.Random):
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

    def load_altered(self) -> None:
        """Load all altered children in memory."""
        for world_key in self.saved_alterations:
            if world_key == 'date_time': continue
            self.add_Km2(int(world_key.split(" ")[0]), int(world_key.split(" ")[1]))

    def update_surroundings(self, longitude: int, latitude: int) -> None:
        """Ensure the surroundings of the player exist and are updated."""
        for lon_delta in range(-World.SURROUNDINGS_RADIUS, World.SURROUNDINGS_RADIUS + 1):
            for lat_delta in range(-World.SURROUNDINGS_RADIUS, World.SURROUNDINGS_RADIUS + 1):
                target_longitude = longitude + lon_delta * Km2.SIZE
                target_latitude = latitude + lat_delta * Km2.SIZE
                tgt_Km2 = next(
                    (km2 for km2 in self.Km2s if km2.longitude == target_longitude and km2.latitude == target_latitude),
                    None
                    )

                if (lon_delta == -World.SURROUNDINGS_RADIUS
                    or lon_delta == World.SURROUNDINGS_RADIUS
                    or lat_delta == -World.SURROUNDINGS_RADIUS
                    or lat_delta == World.SURROUNDINGS_RADIUS
                    ):
                    # "Destruction" ring
                    if tgt_Km2 is None: continue

                    if not tgt_Km2.is_altered:
                        tgt_Km2.parent_world = None
                        self.Km2s.remove(tgt_Km2)
                        continue

                    tgt_Km2.stop_updating()
                else:
                    if tgt_Km2 is None:
                        self.add_Km2(target_longitude, target_latitude)
                        continue
                    if not tgt_Km2.is_altered: continue
                    tgt_Km2.restart_updating()

        print("The surroundings have now ", len(self.Km2s), " Km2")
