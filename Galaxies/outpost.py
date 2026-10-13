import copy
import random
import math
import logging
from datetime import datetime
from typing import Optional

from vector3 import Vector3

import Galaxies.constants
from Galaxies.world import World
from Galaxies.km2 import Km2
from Galaxies.People.person import Person

logger = logging.getLogger(__name__)

class Outpost:
    """A two-level building on a planet's surface (24 m x 12 m x 6 m, two levels of 3 m).

    Outposts belong to planets (`World.outposts`, keyed by "lon lat"; the initial planet always has at least one).
    `surface_point_stellar` on the planet gives their surface position, and `stellar_position(t)` moves them with
    the planet. Rocks are not generated within CLEARED_RADIUS of an outpost's centre (Km2).

    Labels, the sky dot and the world map show outposts (see ObjectLabels, OutpostMarkers, WorldMap). The scanner
    can target them (`Scanner.is_outpost_targeted`, the building box with the door on local +z, so `orientation`
    is the heading the door faces), but the beam does nothing to them yet, and neither the laser nor the ground
    affects them yet.
    """

    HEIGHT = 6.0
    WIDTH = 24.0
    DEPTH = 12.0
    CLEARED_RADIUS = max(HEIGHT, WIDTH, DEPTH)

    STAFF_AGE_MIN = 25
    STAFF_AGE_MAX = 60

    def __init__(self, planet: World, saved_alterations: dict):
        self.planet = planet
        self.index = len(planet.outposts)
        self.seed: float = (planet.seed + self.index + 1) % Galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.name: str = self.generate_name(my_random)
        self.longitude: int = \
            0 if self.index == 0 else \
            my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = my_random.randint(int(-self.planet.radius*math.pi/2), int(self.planet.radius*math.pi/2))

        self.orientation: float = my_random.random() * 360

        self.com_officer: Optional[Person] = None
        self.last_visited: Optional[datetime] = None

        self.is_altered = False
        self.saved_alterations: Optional[dict] = None
        if saved_alterations:
            my_alterations = saved_alterations.get(self.get_alteration_key())
            if my_alterations:
                self.saved_alterations = copy.deepcopy(my_alterations)
                self.set_altered()
        self.log_generation()

    def log_generation(self) -> Outpost:
        logger.info("OUTPOST created")
        logger.info(f"- Index {self.index}, Lon: {self.longitude}, Lat: {self.latitude}")
        logger.info(f"- Seed {self.seed}")
        return self

    def prepare(self) -> Outpost:
        ''' Prepare for visit, that is, apply the alterations.'''
        if self.saved_alterations and 'last_visited' in self.saved_alterations:
            self.last_visited = datetime.strptime(self.saved_alterations['last_visited'], '%Y-%m-%d %H:%M:%S.%f')

        if self.saved_alterations and 'com_officer_seed' in self.saved_alterations:
            self.com_officer = Person(self.saved_alterations['com_officer_seed'], self, self.STAFF_AGE_MIN, self.STAFF_AGE_MAX)
        else:
            self.com_officer = Person(self.seed + 1, self, self.STAFF_AGE_MIN, self.STAFF_AGE_MAX)
        return self

    def get_alteration_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations: dict = {}
        if self.last_visited is not None:
            alterations['last_visited'] = self.last_visited.strftime('%Y-%m-%d %H:%M:%S.%f')
            alterations['com_officer_seed'] = self.com_officer.seed
        if not len(alterations):
            return None
        return alterations

    def set_altered(self) -> Outpost:
        if not self.is_altered:
            self.is_altered = True
            self.planet.set_altered()
        return self

    def set_last_visited(self, new_value: datetime) -> Outpost:
        self.last_visited = new_value
        self.set_altered()
        return self

    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the outpost is, in the stellar frame, moving with its planet."""
        return self.planet.surface_point_stellar(self.longitude, self.latitude, current_datetime)

    def generate_name(self, my_random: random.Random) -> str:
        return self.planet.parent_orbit.parent_stellar_system.political_entity.generate_outpost_name(my_random)

    def communicate(self) -> Outpost:
        import game_environment as gem
        self.com_officer.communicate_from(self)
        self.set_last_visited(gem.current_environment.date_time)
        return self