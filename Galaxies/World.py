from __future__ import annotations

import logging; logger = logging.getLogger(__name__)

import random
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import Galaxies.Constants

if TYPE_CHECKING:
    from Galaxies.Orbit import Orbit
from Galaxies.Km2 import Km2

class World:

    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000
    SURROUNDINGS_RADIUS = 2

    def __init__(self, parent_orbit: int, degrees_in_orbit: float, saved_alterations: dict) -> None:
        self.parent_orbit: Orbit = parent_orbit
        self.degrees_in_orbit: int = degrees_in_orbit
        self.seed: int = (self.degrees_in_orbit + self.parent_orbit.seed) % Galaxies.Constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)
        self.radius: float = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        while self.radius <= 0:
            self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        self.km2s: List[Km2] = []

        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.name: str = self.generate_name(my_random)

    def set_altered(self) -> World:
        self.is_altered = True
        if not self.parent_orbit.is_altered:
            self.parent_orbit.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.degrees_in_orbit)

    def get_alterations(self) -> Optional[dict]:
        alterations: Optional[dict] = dict()
        if self.is_altered:
            for km2 in self.km2s:
                if km2.is_altered:
                    alterations[km2.get_alterations_key()] = km2.get_alterations()
        if alterations == {}:
            return None
        return alterations                    

    def generate_name(self, my_random: random.Random) -> str:
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

    def get_km2_at(self, longitude: float, latitude: float) -> Optional[Km2]:
        """Find the right Km2 for a given point... if it exists."""
        new_longitude = (longitude // Km2.SIZE) * Km2.SIZE
        new_latitude = (latitude // Km2.SIZE) * Km2.SIZE
        return next(
            (km2 for km2 in self.km2s if km2.longitude == new_longitude and km2.latitude == new_latitude),
            None
            )

    def update_surroundings(self, center_lon: float, center_lat: float, game_date_time: datetime) -> None:
        """
        1. Ensure the surroundings of a point exist and are updated.
        2. Ensure everything else loaded is *not longer* updated.
        """
        longitude: int = int((center_lon // Km2.SIZE) * Km2.SIZE)
        latitude: int = int((center_lat // Km2.SIZE) * Km2.SIZE)

        to_stop_updating: List[Km2] = self.km2s.copy()

        for lon_delta in range(-World.SURROUNDINGS_RADIUS, World.SURROUNDINGS_RADIUS + 1):
            for lat_delta in range(-World.SURROUNDINGS_RADIUS, World.SURROUNDINGS_RADIUS + 1):
                target_longitude = longitude + lon_delta * Km2.SIZE
                target_latitude = latitude + lat_delta * Km2.SIZE
                tgt_Km2 = next(
                    (km2 for km2 in self.km2s if km2.longitude == target_longitude and km2.latitude == target_latitude),
                    None
                    )
                if tgt_Km2 is None:
                    new_Km2 = Km2(self, target_longitude, target_latitude, self.saved_alterations)
                    self.km2s.append(new_Km2)
                    continue
                else:
                    to_stop_updating.remove(tgt_Km2)
                if not tgt_Km2.is_altered: continue
                tgt_Km2.start_updating(game_date_time)

        for tgt_Km2 in to_stop_updating:
            if tgt_Km2.is_altered:
                tgt_Km2.stop_updating()
            else:
                self.km2s.remove(tgt_Km2)

        logger.debug(f"The world has now {len(self.km2s)} Km2 loaded.")
