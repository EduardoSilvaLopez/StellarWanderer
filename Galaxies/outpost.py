import random
import math
import logging

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

        self.name: str = "Outpost " + str(self.index)
        self.longitude: int = \
            0 if self.index == 0 else \
            my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = my_random.randint(int(-self.planet.radius*math.pi/2), int(self.planet.radius*math.pi/2))
        self.longitude = int(self.longitude / Km2.SIZE) * Km2.SIZE
        self.latitude = int(self.latitude / Km2.SIZE) * Km2.SIZE

        self.is_altered = False
        self.log_generation()

    def log_generation(self) -> Outpost:
        logger.info("OUTPOST created")
        logger.info(f"- Index {self.index}, Lon: {self.longitude}, Lat: {self.latitude}")
        return self

    def get_alteration_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)