"""A settlement: a place where the pilot can dock, with staff, repairs and a mission board. Outposts are one kind,
and the portal bases another. The logic of what happens there lives here: who is on duty, what is handled for the
ship, what the mission board offers, and what is due at the shift changes. Each kind says where it is and how it is
saved (see Outpost, PortalBase)."""

from __future__ import annotations
import random
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from common.updating import Updatable, update_queue
from common.vector3 import Vector3

import game_environment as gem
from galaxies import seeds
from galaxies.settlement_kind import SettlementKind
from galaxies.people.role import (COM_OFFICER, COORDINATOR, DOCKMASTER, STAFF_AGE_MAX, STAFF_AGE_MIN, Role)

if TYPE_CHECKING:
    from galaxies.body import Body
    from galaxies.people.person import Person
    from galaxies.stellar_system import StellarSystem
    from spaceships.ship import Ship

DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'  # the dates a settlement saves
SUBSTITUTE_AGE_DROP = 2  # the substitute's age range starts this much lower
SUBSTITUTE_SOCIAL_FACTOR = 4
STAFF_SOCIAL_FACTOR = 5
SHIFT_HOURS = 8  # a shift of the staff, from the start of the day: shift 0 at 00:00, shift 1 at 08:00, shift 2 at 16:00
FREE_HOURS_AFTER_SHIFT = 6  # after a shift, free for this long, then resting for REST_HOURS (see _is_free)
REST_HOURS = 8

logger = logging.getLogger(__name__)


class Settlement(Updatable):
    """What a settlement does for the pilot's ship, and who works there. Its place (`stellar_position`), its save
    key and the world it is saved with are the subclass's (see Outpost)."""

    TIME_TO_ENTER = 30 * 60  # seconds of game time that going in takes (half an hour)
    TIME_TO_LEAVE = 30 * 60  # seconds of game time that leaving takes (half an hour)
    CHARGE_PER_SECOND = 5e7 # Wh.
    MAINTENANCE_PER_SECOND = 0.00001 # maintenance per second doable here.
    UNLOAD_ORE_PER_SECOND = 0.5 # 20Kg box unloaded in 40 seconds.
    UNLOAD_RAW_WATER_PER_SECOND = 0.5  # Kg a second, a separate rate for caution: the same number for now
    MAX_MAINTENANCE = 0.8 # maximum maintenance this place can offer
    READY_MARGIN = 0.01 # a ship this close to full needs no handling here (see is_ready)

    # What each kind has: each role with the number of teams that work it at once (each team has its shift members and
    # a substitute). Outposts have one team of each role; the portal base has what is listed for it (its first version).
    roles: Dict[Role, int] = {COM_OFFICER: 1, DOCKMASTER: 1, COORDINATOR: 1}
    # The kind of settlement: what the missions' terms are looked up by (see settlement_kind.py).
    kind: SettlementKind

    def __init__(self, seed: int) -> None:
        self.seed: int = seed
        self.is_altered: bool = False
        self.staff: List[Person] = []  # every member of every role, in the order of roles
        self.on_duty: Dict[Role, List[Person]] = {}  # the members on duty of each role, one for each team
        self.last_visited: Optional[datetime] = None
        self.player_reputation_on_entering: Optional[float] = None
        # While the settlement works on the pilot's ship: when it will be ready, last checked and if it includes ore
        # unloading. It gets saved / loaded to restart on load if needed.
        self.handling_due_at: Optional[datetime] = None
        self.handling_checked_at: Optional[datetime] = None
        self.handling_unloads: bool = False  # the ore and the raw water of the hold are unloaded by the handling
        # local: the board needs the player, which needs missions
        from galaxies.missions.mission_board import MissionBoard
        self.mission_board: MissionBoard = MissionBoard(self)  # its offers live as long as this place is in memory

    def _read_alterations(self, saved: dict) -> None:
        """Reads what the settlement saved (its own keys, see get_alterations), at the load."""
        # Read here, not in prepare: a save made before the ship goes near the settlement must keep it, and prepare
        # runs again each time ground near the settlement is made, which would put the old value back.
        if 'player_reputation_on_entering' in saved:
            self.player_reputation_on_entering = saved['player_reputation_on_entering']
        if 'last_visited' in saved:
            self.last_visited = datetime.strptime(saved['last_visited'], DATE_FORMAT)
        if 'handling_due_at' in saved:
            self.handling_due_at = datetime.strptime(saved['handling_due_at'], DATE_FORMAT)
            self.handling_checked_at = datetime.strptime(saved['handling_checked_at'], DATE_FORMAT)
            self.handling_unloads = saved['handling_unloads']

    def _alterations_of_visits(self, alterations: dict) -> None:
        """Adds the keys of the visit and the handling to `alterations`, when they are set."""
        if self.player_reputation_on_entering is not None:
            alterations['player_reputation_on_entering'] = self.player_reputation_on_entering
        if self.handling_due_at is not None:
            alterations['handling_due_at'] = self.handling_due_at.strftime(DATE_FORMAT)
            alterations['handling_checked_at'] = self.handling_checked_at.strftime(DATE_FORMAT)
            alterations['handling_unloads'] = self.handling_unloads
        if self.last_visited is not None:
            alterations['last_visited'] = self.last_visited.strftime(DATE_FORMAT)

    def set_altered(self) -> Settlement:
        if not self.is_altered:
            self.is_altered = True
            self._parent_altered()
        return self

    def _parent_altered(self) -> None:
        """What the settlement belongs to is altered too (its planet, or its system)."""
        raise NotImplementedError

    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the settlement is, in the stellar frame."""
        raise NotImplementedError

    def inside_key(self) -> str:
        """What the savefile holds for the pilot being inside this settlement (see Player.inside)."""
        raise NotImplementedError

    @property
    def stellar_system(self) -> StellarSystem:
        """The stellar system the settlement is in."""
        raise NotImplementedError

    @property
    def body(self) -> Body:
        """The body the pilot travels to for it: its planet for an outpost, the base itself for a portal base."""
        raise NotImplementedError

    def stellar_velocity(self, current_datetime: datetime) -> Vector3:
        """The velocity of the settlement in the stellar frame."""
        raise NotImplementedError

    @property
    def plane_distance(self) -> float:
        """How far the settlement is from the star's axis, in the plane where the belts lie (m): its planet's orbit
        for an outpost, and 0 for a base, which hangs over the star."""
        raise NotImplementedError

    def needs_water(self) -> bool:
        """Whether the settlement needs water delivered (an outpost on an icy world does not)."""
        raise NotImplementedError

    def address(self) -> str:
        """The user-friendly address of the settlement."""
        raise NotImplementedError

    def residency_line(self) -> str:
        """Where the staff who live here are: a line of the person's record."""
        raise NotImplementedError

    def place_details(self) -> list[str]:
        """Three lines that name the settlement's place (the screen's details): what it is on, its star, its entity."""
        raise NotImplementedError

    # region Staff
    def generate_staff(self) -> Settlement:
        """Creates the staff, once: later calls change nothing, so the same people are always returned."""
        if not self.staff:
            self.staff = [self._generate_member(role, index) for role in self.roles
                          for index in range(self.roles[role] * self._team_size(role))]
        return self

    def roster(self, role: Role) -> List[Person]:
        """The members of `role` here: team by team, each team's shift members first, its substitute (if any) last."""
        self.generate_staff()
        return [person for person in self.staff if person.role is role]

    def on_duty_list(self) -> List[Person]:
        """Everyone on duty now, in the order of `roles`."""
        return [person for role in self.roles for person in self.on_duty.get(role, [])]

    def _first_on_duty(self, role: Role) -> Optional[Person]:
        people = self.on_duty.get(role)
        return people[0] if people else None

    @property
    def com_officer(self) -> Optional[Person]:
        return self._first_on_duty(COM_OFFICER)

    @property
    def dockmaster(self) -> Optional[Person]:
        return self._first_on_duty(DOCKMASTER)

    @property
    def coordinator(self) -> Optional[Person]:
        return self._first_on_duty(COORDINATOR)

    def person_with_seed(self, seed: int) -> Optional[Person]:
        """The staff member of this settlement with that seed, or None if the seed is not one of its staff."""
        self.generate_staff()
        return next((person for person in self.staff if person.seed == seed), None)

    @staticmethod
    def _team_size(role: Role) -> int:
        """The members of one team of `role`: its shift members, and the substitute if there is vacation."""
        return role.shifts + (1 if role.vacation > 0 else 0)

    def _generate_member(self, role: Role, index: int) -> Person:
        """Member `index` of `role` (counted over all its teams). In each team, the one after the shifts is the
        substitute, if the role has any vacation."""
        substitute = index % self._team_size(role) == role.shifts and role.vacation > 0
        age_min = STAFF_AGE_MIN + role.age_raise - (SUBSTITUTE_AGE_DROP if substitute else 0)
        from galaxies.people.person import Person  # local: the people load the world, which loads this module
        return Person(seeds.derive(self.seed, role.seed_kind, index), self,
                      SUBSTITUTE_SOCIAL_FACTOR if substitute else STAFF_SOCIAL_FACTOR, role,
                      age_min, STAFF_AGE_MAX + role.age_raise)

    def shift_of(self, person: Person) -> Optional[int]:
        """The shift of `person` in their team: 0 to shifts - 1 for a shift member, `shifts` for the substitute."""
        role = person.role
        index = self.roster(role).index(person)
        return index % self._team_size(role)
    # endregion

    # region Rota
    @staticmethod
    def _shift_start(now: datetime, shift: int) -> datetime:
        """The latest start, at or before `now`, of the 8-hour `shift` of the day (0, 1 or 2)."""
        start = now.replace(hour=SHIFT_HOURS * shift, minute=0, second=0, microsecond=0)
        return start if start <= now else start - timedelta(days=1)

    def _substitute_covers(self, role: Role, shift_start: datetime, team: int = 0) -> bool:
        """Whether the substitute of `team` of `role` is on duty in the shift that starts at `shift_start`. It is a draw
        from the settlement's seed and that start, so a shift always has the same answer, whatever the visits."""
        if role.vacation <= 0:
            return False
        keys = (role.seed_kind, shift_start.isoformat()) + ((team,) if team else ())
        draw = random.Random(seeds.derive(self.seed, 'vacation', *keys))
        return draw.random() < role.vacation

    def _pick_on_duty(self, role: Role, shift_start: datetime) -> None:
        """The members of `role` on duty in the shift that starts at `shift_start`: one for each team, its shift member
        or its substitute when the substitute covers that shift (see _substitute_covers)."""
        members = self.roster(role)
        size = self._team_size(role)
        on_duty: List[Person] = []
        for team in range(self.roles[role]):
            team_members = members[team * size:(team + 1) * size]
            if self._substitute_covers(role, shift_start, team):
                on_duty.append(team_members[role.shifts])
            else:
                on_duty.append(team_members[shift_start.hour // SHIFT_HOURS % role.shifts])
        self.on_duty[role] = on_duty

    def _pick_all_on_duty(self, now: datetime) -> None:
        shift_start = self._shift_start(now, now.hour // SHIFT_HOURS)
        for role in self.roles:
            self._pick_on_duty(role, shift_start)

    @staticmethod
    def _is_free(elapsed: timedelta) -> bool:
        """Whether someone is free `elapsed` after the start of their last shift: not working in its 8 hours, and not
        resting in the REST_HOURS after the FREE_HOURS_AFTER_SHIFT that follow it. Free again after that."""
        hours = elapsed.total_seconds() / 3600
        rest_start = SHIFT_HOURS + FREE_HOURS_AFTER_SHIFT
        return hours >= SHIFT_HOURS and not rest_start <= hours < rest_start + REST_HOURS

    def _substitute_available(self, role: Role, now: datetime, team: int) -> bool:
        """The substitute is not listed while covering the current shift; otherwise the rest after the latest shift he
        covered among the last three (none: he is free)."""
        current = self._shift_start(now, now.hour // SHIFT_HOURS)
        if self._substitute_covers(role, current, team):
            return False
        for back in range(1, 4):
            start = current - timedelta(hours=SHIFT_HOURS * back)
            if self._substitute_covers(role, start, team):
                return self._is_free(now - start)
        return True

    def is_available(self, person: Person, now: datetime) -> bool:
        """Whether `person` is listed for a chat at `now`: not on vacation (the substitute covers their shift), not
        working, and not resting (see _is_free). The one-shift role, on duty all the time, is always listed."""
        role = person.role
        if role.shifts == 1 and role.vacation == 0:
            return True
        index = self.roster(role).index(person)
        team, shift = divmod(index, self._team_size(role))
        if shift == role.shifts:
            return self._substitute_available(role, now, team)
        start = self._shift_start(now, shift)
        if self._substitute_covers(role, start, team):
            return False
        return self._is_free(now - start)

    def available_staff(self, now: datetime) -> List[Person]:
        """The staff listed for a chat at `now`, in the order of `staff`."""
        self.generate_staff()
        return [person for person in self.staff if self.is_available(person, now)]
    # endregion

    # region Visits
    def prepare(self) -> Settlement:
        ''' Prepare for visit.'''
        self.generate_staff()
        shift = gem.current_environment.date_time.hour // 8
        self._pick_all_on_duty(gem.current_environment.date_time)
        self.next_update_at: datetime = gem.current_environment.date_time
        self.next_update_at = self.next_update_at.replace(hour=8 * shift, minute=0, second=0, microsecond=0)
        self.next_update_at += timedelta(hours=8)
        if self not in update_queue:  # prepare runs each time ground near the settlement is made: one entry only
            update_queue.add(self)

        return self

    def _set_last_visited(self, new_value: datetime) -> Settlement:
        self.last_visited = new_value
        self.set_altered()
        return self

    def get_time_to_handle(self, ship: Ship) -> int:
        time_to_charge = (ship.energy_max - ship.energy) / Settlement.CHARGE_PER_SECOND
        time_to_repair = (Settlement.MAX_MAINTENANCE - ship.maintenance) / Settlement.MAINTENANCE_PER_SECOND
        if time_to_repair < 0:
            time_to_repair = 0.0
        time_to_unload = (ship.cargo_hold.ore / Settlement.UNLOAD_ORE_PER_SECOND
                          + ship.cargo_hold.raw_water / Settlement.UNLOAD_RAW_WATER_PER_SECOND) \
            if self.handling_unloads else 0
        return int(max(time_to_charge, time_to_repair + time_to_unload)) # Dockmaster is alone, repairs or unloads.

    @staticmethod
    def unloading_text(ship: Ship) -> str:
        """What the Dockmaster would unload from the hold, as he asks for it: 'the ore', 'the raw water', both, or ''
        when there is nothing of either."""
        cargo = (('the ore', ship.cargo_hold.ore), ('the raw water', ship.cargo_hold.raw_water))
        names = [name for name, amount in cargo if amount > 0]
        return ' and '.join(names)

    def is_ready(self, ship: Ship) -> bool:
        """Whether the Dockmaster has nothing to offer `ship`: no handling is going on, no ore or raw water to unload,
        and its energy and maintenance are within READY_MARGIN of full (energy_max, MAX_MAINTENANCE). A handling going
        on is not judged: it still brings the ship to full."""
        full = 1 - self.READY_MARGIN
        return (self.handling_due_at is None and ship.cargo_hold.ore == 0 and ship.cargo_hold.raw_water == 0
                and ship.energy >= ship.energy_max * full and ship.maintenance >= self.MAX_MAINTENANCE * full)

    def start_handle(self, ship: Ship, extra_seconds: float = 0.0) -> Settlement:
        """The settlement starts working on the pilot's `ship`, from the state it is in now: it will be ready after
        get_time_to_handle, and `extra_seconds` more (work the ship's hold is about to lose, such as raw water
        unloaded at delivery). A handle already going is first brought up to date, then restarted. The ship
        is near, so `prepare` has put the settlement in the update queue, which wakes it when the handle is due. The
        dates are saved with the settlement."""
        now = gem.current_environment.date_time
        self.update_handle(ship, now)
        self.handling_due_at = now + timedelta(seconds=self.get_time_to_handle(ship) + extra_seconds)
        self.handling_checked_at = now
        return self.set_altered()

    def update_handle(self, ship: Ship, now: datetime) -> Settlement:
        """Gives `ship` what the handling has done up to `now`. Call it before showing the ship's levels."""
        if self.handling_due_at is None:
            return self
        import galaxies.people.player as gpp  # local: the player loads the world, which loads this module
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

            if self.handling_unloads:
                # The dockmaster unloads the ore first, then the raw water, with the time the ore did not take.
                hold = ship.cargo_hold
                ore_change = min(hold.ore, self.UNLOAD_ORE_PER_SECOND * seconds)
                hold.ore -= ore_change
                water_time = seconds - ore_change / self.UNLOAD_ORE_PER_SECOND
                water_change = min(hold.raw_water, self.UNLOAD_RAW_WATER_PER_SECOND * water_time)
                hold.raw_water -= water_change
                gpp.current_player.those_who_share.adjust_reputation_by_supply("ore", ore_change)
                gpp.current_player.those_who_share.adjust_reputation_by_supply("raw_water", water_change)

            self.handling_checked_at = until
        return self

    def stop_handle(self, ship: Ship, now: datetime) -> Settlement:
        self.update_handle(ship, now)
        self.handling_due_at = None
        self.handling_checked_at = None
        self.handling_unloads = False
        return self

    def leave(self, ship: Ship, now: datetime) -> int:
        """The pilot leaves the settlement, after its question if a handling is going on (see OutpostScreenDialog): the
        handling stops with what it has done so far. Returns the seconds leaving takes (TIME_TO_LEAVE), which the caller
        adds to the game time."""
        self.stop_handle(ship, now)
        self._set_last_visited(now + timedelta(seconds=self.TIME_TO_LEAVE))
        self.player_reputation_on_entering = None
        return self.TIME_TO_LEAVE

    def place_after_leaving(self, ship: Ship) -> None:
        """Where the ship is put when the pilot leaves: nothing for a settlement the ship stays where it was."""

    def _finish_handling(self, ship: Ship, now: datetime) -> Settlement:
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
            import galaxies.people.player as gpp  # local: the player loads the world, which loads this module
            self._finish_handling(gpp.current_player.ship, game_date_time)
        if self.next_update_at <= game_date_time:
            self._pick_all_on_duty(game_date_time)
            self.next_update_at += timedelta(hours=8)
        update_queue.add(self)
    # endregion
