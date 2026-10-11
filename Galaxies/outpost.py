import random
import math
import logging
from datetime import datetime

from Galaxies.People.person import Person
from Vector3 import Vector3

import Galaxies.constants
from Galaxies.world import World
from Galaxies.km2 import Km2

logger = logging.getLogger(__name__)

class Outpost:
    HEIGHT = 3.0
    WIDTH = 12.0
    DEPTH = 6.0

    def __init__(self, planet: World):
        self.planet = planet
        self.index = len(planet.outposts)
        self.seed: int = (planet.seed * (self.index + 1) + 1) % Galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.name: str = self.generate_name(my_random)
        self.longitude: int = \
            0 if self.index == 0 else \
            my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = my_random.randint(int(-self.planet.radius*math.pi/2), int(self.planet.radius*math.pi/2))
        self.longitude = int(self.longitude / Km2.SIZE) * Km2.SIZE
        self.latitude = int(self.latitude / Km2.SIZE) * Km2.SIZE

        self.orientation: float = my_random.random() * 360

        self.com_officer: Person = Person(self.seed)

        self.is_altered = False
        self.log_generation()

    def log_generation(self) -> Outpost:
        logger.info("OUTPOST created")
        logger.info(f"- Index {self.index}, Lon: {self.longitude}, Lat: {self.latitude}")
        return self

    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the outpost is, in the stellar frame, moving with its planet."""
        return self.planet.surface_point_stellar(self.longitude, self.latitude, current_datetime)

    def get_alteration_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def generate_name(self, my_random: random.Random) -> str:
        return self.planet.parent_orbit.parent_stellar_system.political_entity.generate_outpost_name(my_random)

    def communicate(self) -> Outpost:
        self.com_officer.communicate_from(self)
        return self