import copy
import random
import math
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional

from common.updating import update_queue
from common.updating import Updatable
from common.vector3 import Vector3

import game_environment as gem
import galaxies.constants
from galaxies.world import World
from galaxies.people.person import Person

if TYPE_CHECKING:
    from galaxies.missions import Mission

logger = logging.getLogger(__name__)


class Outpost(Updatable):
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
    STAFF_SIZE = 4  # three shifts and a substitute

    def __init__(self, planet: World, saved_alterations: dict) -> None:
        self.planet = planet
        self.index = len(planet.outposts)
        self.seed: float = (planet.seed + self.index + 1) % galaxies.constants.SEEDS_SCALING
        self.my_random: random.Random = random.Random(self.seed)

        self.name: str = self._generate_name(self.my_random)
        self.longitude: int = \
            0 if self.index == 0 else \
            self.my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = self.my_random.randint(int(-self.planet.radius*math.pi/2), int(self.planet.radius*math.pi/2))

        self.orientation: float = self.my_random.random() * 360

        self.staff: List[Person] = []
        self.work_shift: int = 4
        self.free_days: float = 0.33
        self.com_officer: Optional[Person] = None
        self.last_visited: Optional[datetime] = None

        self.is_altered = False
        self.saved_alterations: Optional[dict] = None
        if saved_alterations:
            my_alterations = saved_alterations.get(self.get_alteration_key())
            if my_alterations:
                self.saved_alterations = copy.deepcopy(my_alterations)
                self.set_altered()
        self._log_generation()

    def _log_generation(self) -> Outpost:
        logger.info("OUTPOST created")
        logger.info(f"- Index {self.index}, Lon: {self.longitude}, Lat: {self.latitude}")
        logger.info(f"- Seed {self.seed}")
        return self

    def staff_member(self, index: int) -> Person:
        """The staff member `index` (0 to STAFF_SIZE - 1): the last one is the free-day substitute. His or her seed is the
        outpost's plus the index."""
        last = index == self.STAFF_SIZE - 1
        return Person(self.seed + index, self, 4 if last else 5,
                      self.STAFF_AGE_MIN - 2 if last else self.STAFF_AGE_MIN, self.STAFF_AGE_MAX)

    def person_with_seed(self, seed: float) -> Optional[Person]:
        """The staff member of this outpost with that seed, or None if the seed is not one of its staff. Created again
        when the staff has not been prepared (nobody has visited the outpost in this session)."""
        for index in range(self.STAFF_SIZE):
            if self.seed + index == seed:
                return self.staff[index] if self.staff else self.staff_member(index)
        return None

    def prepare(self) -> Outpost:
        ''' Prepare for visit.'''
        if self.saved_alterations and 'last_visited' in self.saved_alterations:
            self.last_visited = datetime.strptime(self.saved_alterations['last_visited'], '%Y-%m-%d %H:%M:%S.%f')

        if not self.staff:
            self.staff = [self.staff_member(index) for index in range(self.STAFF_SIZE)]
        shift = gem.current_environment.date_time.hour // 8
        if self.my_random.random() < self.free_days:
            self.com_officer = self.staff[3]
        else:
            self.com_officer = self.staff[shift]
        self.next_update_at: datetime = gem.current_environment.date_time
        self.next_update_at = self.next_update_at.replace(hour=8 * shift, minute=0, second=0, microsecond=0)
        self.next_update_at += timedelta(hours=8)
        update_queue.add(self)

        return self

    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        ''' Next employee...'''
        shift = game_date_time.hour // 8
        if self.my_random.random() < self.free_days:
            self.com_officer = self.staff[3]
        else:
            self.com_officer = self.staff[shift]
        self.next_update_at += timedelta(hours=8)
        update_queue.add(self)
        pass

    def get_alteration_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations: dict = {}
        if self.last_visited is not None:
            alterations['last_visited'] = self.last_visited.strftime('%Y-%m-%d %H:%M:%S.%f')
            alterations['com_officer_seed'] = self.com_officer.seed
        if not alterations:
            return None
        return alterations

    def set_altered(self) -> Outpost:
        if not self.is_altered:
            self.is_altered = True
            self.planet.set_altered()
        return self

    def _set_last_visited(self, new_value: datetime) -> Outpost:
        self.last_visited = new_value
        self.set_altered()
        return self

    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the outpost is, in the stellar frame, moving with its planet."""
        return self.planet.surface_point_stellar(self.longitude, self.latitude, current_datetime)

    def _generate_name(self, my_random: random.Random) -> str:
        return self.planet.parent_orbit.parent_stellar_system.political_entity.generate_outpost_name(my_random)

    def reference(self) -> str:
        """A text that identifies this outpost in the whole galaxy: its system, orbit, planet and own key."""
        orbit = self.planet.parent_orbit
        return '|'.join((orbit.parent_stellar_system.get_alterations_key(), orbit.get_alterations_key(),
                         self.planet.get_alterations_key(), self.get_alteration_key()))

    def place(self) -> str:
        """Where this outpost is, for the player: its name, its world (a planet, or a moon with its planet) and its
        stellar system, e.g. "Consequential Task, planet Iuief, Aqakhaceia System"."""
        world = self.planet
        place: str = f"{self.name}, "
        if world.parent_planet:
            place += f"moon {world.name}, planet {world.parent_planet.name}"
        else:
            place += f"planet {world.name}"
        return f"{place}, {world.parent_orbit.parent_stellar_system.name}"

    def generate_missions(self, now: datetime) -> List[Mission]:
        """The missions this outpost offers when its board is opened at `now`: none is saved, and they do not depend on
        what the player has taken, done or failed. How many, and of which kinds, depends on the time since `last_visited`
        (None before the first visit) and `now`. The draws are made from a seed of the outpost and `now`."""
        from galaxies.missions import DeliverOre
        my_random = random.Random(f"missions {self.seed} {now.isoformat()}")
        return [DeliverOre.generate(self, my_random)]  # placeholder: to be decided

    def open_mission_board(self) -> Outpost:
        """The player opens the message board (see mission_board.py): a visit, not a conversation."""
        from galaxies.mission_board import MissionBoard
        now = gem.current_environment.date_time
        missions = self.generate_missions(now)  # first: it needs the previous visit
        self._set_last_visited(now)
        MissionBoard(self, missions).open()
        return self

    def communicate(self) -> Outpost:
        import game_environment as gem
        self.com_officer.communicate_from(self)
        self._set_last_visited(gem.current_environment.date_time)
        return self
