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
import galaxies.people.player as gpp
from galaxies import seeds
if TYPE_CHECKING:
    from spaceships.ship import Ship
from galaxies.world import World
from galaxies.people.person import Person
from galaxies.people.role import COM_OFFICER, COORDINATOR, DOCKMASTER, ROLES, STAFF_AGE_MAX, STAFF_AGE_MIN, Role

DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'  # the dates the outpost saves
SUBSTITUTE_AGE_DROP = 2  # the substitute's age range starts this much lower
SUBSTITUTE_SOCIAL_FACTOR = 4
STAFF_SOCIAL_FACTOR = 5
SHIFT_HOURS = 8  # a shift of the staff, from the start of the day: shift 0 at 00:00, shift 1 at 08:00, shift 2 at 16:00
FREE_HOURS_AFTER_SHIFT = 6  # after a shift, free for this long, then resting for REST_HOURS (see _is_free)
REST_HOURS = 8

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
    CHARGE_PER_SECOND = 5e7 # Wh.
    MAINTENANCE_PER_SECOND = 0.00001 # maintenance per second doable here.
    UNLOAD_ORE_PER_SECOND = 0.5 # 20Kg box unloaded in 40 seconds.
    MAX_MAINTENANCE = 0.8 # maximum maintenance this place can offer
    READY_MARGIN = 0.01 # a ship this close to full needs no handling here (see is_ready)

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
        self.player_reputation_on_entering: Optional[float] = None
        # While the outpost works on the pilot's ship: when it will be ready, last checked and if it includes ore
        # unloading. It gets saved / loaded to restart on load if needed.
        self.handling_due_at: Optional[datetime] = None
        self.handling_checked_at: Optional[datetime] = None
        self.handling_includes_ore: bool = False
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
                if 'player_reputation_on_entering' in self.saved_alterations:
                    self.player_reputation_on_entering = self.saved_alterations['player_reputation_on_entering']
                if 'last_visited' in self.saved_alterations:
                    self.last_visited = datetime.strptime(self.saved_alterations['last_visited'], DATE_FORMAT)
                if 'handling_due_at' in self.saved_alterations:
                    self.handling_due_at = datetime.strptime(self.saved_alterations['handling_due_at'], DATE_FORMAT)
                    self.handling_checked_at = \
                        datetime.strptime(self.saved_alterations['handling_checked_at'], DATE_FORMAT)
                    self.handling_includes_ore = self.saved_alterations['handling_includes_ore']
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

    @property
    def coordinator(self) -> Optional[Person]:
        return self.on_duty.get(COORDINATOR)

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

    # endregion

    # region Rota
    @staticmethod
    def _shift_start(now: datetime, shift: int) -> datetime:
        """The latest start, at or before `now`, of the 8-hour `shift` of the day (0, 1 or 2)."""
        start = now.replace(hour=SHIFT_HOURS * shift, minute=0, second=0, microsecond=0)
        return start if start <= now else start - timedelta(days=1)

    def _substitute_covers(self, role: Role, shift_start: datetime) -> bool:
        """Whether the substitute of `role` is on duty in the shift that starts at `shift_start`. It is a draw from the
        outpost's seed and that start, so a shift always has the same answer, whatever the visits."""
        if role.vacation <= 0:
            return False
        draw = random.Random(seeds.derive(self.seed, 'vacation', role.seed_kind, shift_start.isoformat()))
        return draw.random() < role.vacation

    def _pick_on_duty(self, role: Role, shift_start: datetime) -> None:
        """The member of `role` on duty in the shift that starts at `shift_start`: its shift member, or the substitute
        when the substitute covers that shift (see _substitute_covers)."""
        members = self.roster(role)
        if self._substitute_covers(role, shift_start):
            self.on_duty[role] = members[role.shifts]
        else:
            self.on_duty[role] = members[shift_start.hour // SHIFT_HOURS % role.shifts]

    def _pick_all_on_duty(self, now: datetime) -> None:
        shift_start = self._shift_start(now, now.hour // SHIFT_HOURS)
        for role in ROLES:
            self._pick_on_duty(role, shift_start)

    @staticmethod
    def _is_free(elapsed: timedelta) -> bool:
        """Whether someone is free `elapsed` after the start of their last shift: not working in its 8 hours, and not
        resting in the REST_HOURS after the FREE_HOURS_AFTER_SHIFT that follow it. Free again after that."""
        hours = elapsed.total_seconds() / 3600
        rest_start = SHIFT_HOURS + FREE_HOURS_AFTER_SHIFT
        return hours >= SHIFT_HOURS and not rest_start <= hours < rest_start + REST_HOURS

    def _substitute_available(self, role: Role, now: datetime) -> bool:
        """The substitute is not listed while covering the current shift; otherwise the rest after the latest shift he
        covered among the last three (none: he is free)."""
        current = self._shift_start(now, now.hour // SHIFT_HOURS)
        if self._substitute_covers(role, current):
            return False
        for back in range(1, 4):
            start = current - timedelta(hours=SHIFT_HOURS * back)
            if self._substitute_covers(role, start):
                return self._is_free(now - start)
        return True

    def is_available(self, person: Person, now: datetime) -> bool:
        """Whether `person` is listed for a chat at `now`: not on vacation (the substitute covers their shift), not
        working, and not resting (see _is_free). The one-shift role, on duty all the time, is always listed."""
        role = person.role
        if role.shifts == 1 and role.vacation == 0:
            return True
        index = self.roster(role).index(person)
        if index == role.shifts:
            return self._substitute_available(role, now)
        start = self._shift_start(now, index)
        if self._substitute_covers(role, start):
            return False
        return self._is_free(now - start)

    def available_staff(self, now: datetime) -> List[Person]:
        """The staff listed for a chat at `now`, in the order of `staff`."""
        self.generate_staff()
        return [person for person in self.staff if self.is_available(person, now)]
    # endregion

    # region Visits
    def prepare(self) -> Outpost:
        ''' Prepare for visit.'''
        self.generate_staff()
        shift = gem.current_environment.date_time.hour // 8
        self._pick_all_on_duty(gem.current_environment.date_time)
        self.next_update_at: datetime = gem.current_environment.date_time
        self.next_update_at = self.next_update_at.replace(hour=8 * shift, minute=0, second=0, microsecond=0)
        self.next_update_at += timedelta(hours=8)
        if self not in update_queue:  # prepare runs each time ground near the outpost is made: one entry only
            update_queue.add(self)

        return self

    def _set_last_visited(self, new_value: datetime) -> Outpost:
        self.last_visited = new_value
        self.set_altered()
        return self

    def get_time_to_handle(self, ship: Ship) -> int:
        time_to_charge = (ship.energy_max - ship.energy) / Outpost.CHARGE_PER_SECOND
        time_to_repair = (Outpost.MAX_MAINTENANCE - ship.maintenance) / Outpost.MAINTENANCE_PER_SECOND
        if time_to_repair < 0:
            time_to_repair = 0.0
        time_to_unload = \
            (ship.cargo_hold.ore) / Outpost.UNLOAD_ORE_PER_SECOND \
            if self.handling_includes_ore else 0
        return int(max(time_to_charge, time_to_repair + time_to_unload)) # Dockmaster is alone, repairs or unloads.

    def is_ready(self, ship: Ship) -> bool:
        """Whether the Dockmaster has nothing to offer `ship`: no handling is going on, no ore to unload, and its energy
        and maintenance are within READY_MARGIN of full (energy_max, MAX_MAINTENANCE). A handling going on is not
        judged: it still brings the ship to full."""
        full = 1 - self.READY_MARGIN
        return (self.handling_due_at is None and ship.cargo_hold.ore == 0
                and ship.energy >= ship.energy_max * full and ship.maintenance >= self.MAX_MAINTENANCE * full)

    def start_handle(self, ship: Ship) -> Outpost:
        """The outpost starts working on the pilot's `ship`, from the state it is in now: it will be ready after
        get_time_to_handle. A handle already going is first brought up to date, then restarted. The ship
        is near, so `prepare` has put the outpost in the update queue, which wakes it when the handle is due. The dates
        are saved with the outpost."""
        now = gem.current_environment.date_time
        self.update_handle(ship, now)
        self.handling_due_at = now + timedelta(seconds=self.get_time_to_handle(ship))
        self.handling_checked_at = now
        return self.set_altered()

    def update_handle(self, ship: Ship, now: datetime) -> Outpost:
        """Gives `ship` what the handling has done up to `now`. Call it before showing the ship's levels."""
        if self.handling_due_at is None:
            return self
        until = min(now, self.handling_due_at)
        seconds = (until - self.handling_checked_at).total_seconds()
        if seconds > 0:
            energy_change = min(ship.energy_max - ship.energy, self.CHARGE_PER_SECOND * seconds)
            ship.energy += energy_change
            gpp.current_player.those_who_share.adjust_reputation_by_supply("energy", -energy_change)

            if ship.maintenance < self.MAX_MAINTENANCE:
                if self.MAX_MAINTENANCE - ship.maintenance < self.MAINTENANCE_PER_SECOND * seconds:
                    # Avoid epsilon changes.
                    maintenance_change = self.MAX_MAINTENANCE - ship.maintenance
                    ship.maintenance = self.MAX_MAINTENANCE
                else:
                    maintenance_change = self.MAINTENANCE_PER_SECOND * seconds
                    ship.maintenance += maintenance_change
                gpp.current_player.those_who_share.adjust_reputation_by_supply("maintenance", -maintenance_change)

            if self.handling_includes_ore and ship.cargo_hold.ore > 0:
                ore_change = min (ship.cargo_hold.ore, self.UNLOAD_ORE_PER_SECOND * seconds)
                ship.cargo_hold.ore -= ore_change
                gpp.current_player.those_who_share.adjust_reputation_by_supply("ore", ore_change)

            self.handling_checked_at = until
        return self

    def stop_handle(self, ship: Ship, now: datetime) -> Outpost:
        self.update_handle(ship, now)
        self.handling_due_at = None
        self.handling_checked_at = None
        self.handling_includes_ore = False
        return self

    def leave(self, ship: Ship, now: datetime) -> int:
        """The pilot leaves the outpost, after its question if a handling is going on (see OutpostScreenDialog): the
        handling stops with what it has done so far. Returns the seconds leaving takes (TIME_TO_LEAVE), which the caller
        adds to the game time."""
        self.stop_handle(ship, now)
        self._set_last_visited(now + timedelta(seconds=self.TIME_TO_LEAVE))
        self.player_reputation_on_entering = None
        return self.TIME_TO_LEAVE

    def _finish_handling(self, ship: Ship, now: datetime) -> Outpost:
        """The handling is done: whatever had to be done, is done."""
        from common.dialogs.messages import Message, show_message
        self.stop_handle(ship, now)
        ship.owner.time_scale = 1
        show_message(Message(
            title=f'MESSAGE FROM DOCKMASTER {self.dockmaster.surname}',
            text=f"{self.dockmaster.get_player_title()}, your ship is ready.",
        ))
        return self
    # endregion

    # region Updating
    def get_next_update(self) -> datetime:
        """The next shift change, or the end of handling if it comes before."""
        if self.handling_due_at is None:
            return self.next_update_at
        return min(self.next_update_at, self.handling_due_at)

    def update(self, game_date_time: datetime) -> None:
        """What is due: the end of the handling, and the next employee on duty (the shifts are 8 hours)."""
        if self.handling_due_at is not None and self.handling_due_at <= game_date_time:
            import galaxies.people.player as gpp  # local: the game's environment, not needed by the rest of this module
            self._finish_handling(gpp.current_player.ship, game_date_time)
        if self.next_update_at <= game_date_time:
            self._pick_all_on_duty(game_date_time)
            self.next_update_at += timedelta(hours=8)
        update_queue.add(self)
    # endregion

    # region Alterations
    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations: dict = {}
        if self.player_reputation_on_entering is not None:
            alterations['player_reputation_on_entering'] = self.player_reputation_on_entering
        if self.handling_due_at is not None:
            alterations['handling_due_at'] = self.handling_due_at.strftime(DATE_FORMAT)
            alterations['handling_checked_at'] = self.handling_checked_at.strftime(DATE_FORMAT)
            alterations['handling_includes_ore'] = self.handling_includes_ore
        if self.last_visited is not None:
            alterations['last_visited'] = self.last_visited.strftime(DATE_FORMAT)
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
