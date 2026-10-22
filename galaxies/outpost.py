from __future__ import annotations
import copy
import random
import math
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from common.updating import Updatable, update_queue
from common.vector3 import Vector3

import game_environment as gem
from galaxies import seeds
if TYPE_CHECKING:
    from galaxies.missions.mission_board import MissionBoard
from galaxies.world import World
from galaxies.people.person import Person
from galaxies.people.role import COM_OFFICER, DOCKMASTER, ROLES, STAFF_AGE_MAX, STAFF_AGE_MIN, Role

SUBSTITUTE_AGE_DROP = 2  # the substitute's age range starts this much lower
SUBSTITUTE_SOCIAL_FACTOR = 4
STAFF_SOCIAL_FACTOR = 5

logger = logging.getLogger(__name__)


class Outpost(Updatable):
    """A two-level building on a planet's surface (24 m x 12 m x 6 m, two levels of 3 m).

    Outposts belong to planets (`World.outposts`, keyed by "lon lat"; the initial planet always has at least one).
    `surface_point_stellar` on the planet gives their surface position, and `stellar_position(t)` moves them with
    the planet. Rocks are not generated within CLEARED_RADIUS of an outpost's centre (Km2).

    Labels, the sky dot and the world map show outposts (see ObjectLabels, OutpostMarkers, WorldMap). The scanner
    can target them (`Scanner._outpost_entry`, the building box with the door on local +z, so `orientation`
    is the heading the door faces), but the beam does nothing to them yet, and neither the laser nor the ground
    affects them yet.
    """

    HEIGHT = 6.0
    WIDTH = 24.0
    DEPTH = 12.0
    CLEARED_RADIUS = max(HEIGHT, WIDTH, DEPTH)

    TIME_TO_ENTER = 30 * 60  # seconds of game time that going into the outpost takes (half an hour)
    TIME_TO_LEAVE = 30 * 60  # seconds of game time that leaving it takes (half an hour)

    def __init__(self, planet: World, saved_alterations: dict) -> None:
        self.planet = planet
        self.index = len(planet.outposts)
        self.seed: int = seeds.derive(planet.seed, 'outpost', self.index)
        self.my_random: random.Random = random.Random(self.seed)

        entity = self.planet.parent_orbit.parent_stellar_system.political_entity
        self.name: str = entity.generate_outpost_name(self.my_random)
        self.longitude: int = \
            0 if self.index == 0 else \
            self.my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = self.my_random.randint(int(-self.planet.radius*math.pi/2),
                                                    int(self.planet.radius*math.pi/2))

        self.orientation: float = self.my_random.random() * 360

        self.staff: List[Person] = []  # every member of every role, in the order of ROLES
        self.on_duty: Dict[Role, Person] = {}  # the member on duty of each role that has one, see _pick_on_duty
        self.last_visited: Optional[datetime] = None
        # local: the board needs the player, which needs missions
        from galaxies.missions.mission_board import MissionBoard
        self.mission_board: MissionBoard = MissionBoard(self)  # its offers live as long as this outpost is in memory

        self.is_altered = False
        self.saved_alterations: Optional[dict] = None
        if saved_alterations:
            my_alterations = saved_alterations.get(self.get_alterations_key())
            if my_alterations:
                self.saved_alterations = copy.deepcopy(my_alterations)
                # Read here, not in prepare: a save made before the ship goes near the outpost must keep it, and prepare
                # runs again each time ground near the outpost is made, which would put the old value back.
                if 'last_visited' in self.saved_alterations:
                    self.last_visited = datetime.strptime(self.saved_alterations['last_visited'],
                                                          '%Y-%m-%d %H:%M:%S.%f')
                self.set_altered()
        self._log_generation()

    def _log_generation(self) -> Outpost:
        logger.info("OUTPOST created")
        logger.info(f"- Index {self.index}, Lon: {self.longitude}, Lat: {self.latitude}")
        logger.info(f"- Seed {self.seed}")
        return self

    # region Staff
    def generate_staff(self) -> Outpost:
        """Creates the staff, once: later calls change nothing, so the same people are always returned."""
        if not self.staff:
            self.staff = [self._generate_member(role, index) for role in ROLES for index in range(role.headcount)]
        return self

    def roster(self, role: Role) -> List[Person]:
        """The members of `role` here: the shift members first, the substitute (if any) last."""
        self.generate_staff()
        return [person for person in self.staff if person.role is role]

    @property
    def com_officer(self) -> Optional[Person]:
        return self.on_duty.get(COM_OFFICER)

    @property
    def dockmaster(self) -> Optional[Person]:
        return self.on_duty.get(DOCKMASTER)

    def person_with_seed(self, seed: int) -> Optional[Person]:
        """The staff member of this outpost with that seed, or None if the seed is not one of its staff."""
        self.generate_staff()
        return next((person for person in self.staff if person.seed == seed), None)

    def _generate_member(self, role: Role, index: int) -> Person:
        """Member `index` of `role`. The one after the shifts is the substitute, if the role has any vacation."""
        substitute = index == role.shifts and role.vacation > 0
        age_min = STAFF_AGE_MIN + role.age_raise - (SUBSTITUTE_AGE_DROP if substitute else 0)
        return Person(seeds.derive(self.seed, role.seed_kind, index), self,
                      SUBSTITUTE_SOCIAL_FACTOR if substitute else STAFF_SOCIAL_FACTOR, role,
                      age_min, STAFF_AGE_MAX + role.age_raise)

    def _pick_on_duty(self, role: Role, shift: int) -> None:
        """The member of `role` on duty in the 8-hour `shift`: its shift member, or the substitute on a vacation day."""
        members = self.roster(role)
        if self.my_random.random() < role.vacation:
            self.on_duty[role] = members[role.shifts]
        else:
            self.on_duty[role] = members[shift % role.shifts]

    def _pick_all_on_duty(self, shift: int) -> None:
        for role in ROLES:
            self._pick_on_duty(role, shift)
    # endregion

    # region Visits
    def prepare(self) -> Outpost:
        ''' Prepare for visit.'''
        self.generate_staff()
        shift = gem.current_environment.date_time.hour // 8
        self._pick_all_on_duty(shift)
        self.next_update_at: datetime = gem.current_environment.date_time
        self.next_update_at = self.next_update_at.replace(hour=8 * shift, minute=0, second=0, microsecond=0)
        self.next_update_at += timedelta(hours=8)
        if self not in update_queue:  # prepare runs each time ground near the outpost is made: one entry only
            update_queue.add(self)

        return self

    def open_mission_board(self) -> MissionBoard:
        """The player opens the message board (see mission_board.py): a visit, not a conversation. Returns the board, to
        show."""
        now = gem.current_environment.date_time
        self.mission_board.update_missions(now)
        self._set_last_visited(now)
        return self.mission_board

    def communicate(self) -> Outpost:
        from galaxies.people.conversation import Conversation
        Conversation.generate(self.com_officer)
        self._set_last_visited(gem.current_environment.date_time)
        return self

    def _set_last_visited(self, new_value: datetime) -> Outpost:
        self.last_visited = new_value
        self.set_altered()
        return self
    # endregion

    # region Updating
    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        ''' Next employee...'''
        self._pick_all_on_duty(game_date_time.hour // 8)
        self.next_update_at += timedelta(hours=8)
        update_queue.add(self)
    # endregion

    # region Alterations
    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations: dict = {}
        if self.last_visited is not None:
            alterations['last_visited'] = self.last_visited.strftime('%Y-%m-%d %H:%M:%S.%f')
            # Nobody on duty yet when the ship has not been near since the load: the saved one is kept.
            for role in ROLES:
                if role.save_key is None:
                    continue
                person = self.on_duty.get(role)
                seed = person.seed if person is not None else (self.saved_alterations or {}).get(role.save_key)
                if seed is not None:
                    alterations[role.save_key] = seed
        if not alterations:
            return None
        return alterations

    def set_altered(self) -> Outpost:
        if not self.is_altered:
            self.is_altered = True
            self.planet.set_altered()
        return self
    # endregion

    # region Place
    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the outpost is, in the stellar frame, moving with its planet."""
        return self.planet.surface_point_stellar(self.longitude, self.latitude, current_datetime)

    def full_keys(self) -> str:
        """The keys that find this outpost from the galaxy: system, orbit, planet and its own, joined by '|'."""
        orbit = self.planet.parent_orbit
        return '|'.join((orbit.parent_stellar_system.get_alterations_key(), orbit.get_alterations_key(),
                         self.planet.get_alterations_key(), self.get_alterations_key()))

    def address(self) -> str:
        """User-friendly address of the outpost."""
        world = self.planet
        place: str = f"{self.name}, "
        if world.parent_planet:
            place += f"moon {world.name}, planet {world.parent_planet.name}"
        else:
            place += f"planet {world.name}"
        return f"{place}, {world.parent_orbit.parent_stellar_system.name}"
    # endregion
