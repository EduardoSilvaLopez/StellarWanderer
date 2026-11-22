"""The expansion of mankind from Sol: which star each settled system is, when and by which system it was settled,
and its settlements with their enlargements.

The history is a pure function of the galaxy seed and of the date it runs to, which is never earlier than HORIZON, so
the galaxy makes it again whenever it is made (a new game, a load) and nothing of it is saved. Running it to a later
date only adds what comes after the earlier run, so a run to a later date gives the same systems up to the earlier
one. `simulation_script.py` runs it without the game.

The run (ExpansionHistory._run). Sol is the yellow star nearest to SOL_REFERENCE_POSITION, and it is settled first.
Every settled system has one pending action, which is the next thing it does: settle a new star, enlarge one of its
settlements, or found a new settlement. Each action is dated when it is done. The actions of all systems are taken in
date order, from one queue, so a star goes to whoever reaches it first, and the result never depends on the order in
which the code visits the systems. An action dated at or after the horizon is not taken: the history ends there.

The pending action of a system is rolled from its own generator (SystemHistory.next_action). The slots of its entity's
profile decide between a new star, an enlargement and a new settlement; the time each takes is a Gaussian draw, divided
by the tech factor, which grows with time for everybody.

A new star (settling.py). The settling system draws a candidate from the stars in reach, weighted by colour, by
direction away from Sol and by distance. If the drawn star is already settled, the settling is dropped: the action is
used up and nothing else changes. Otherwise the star is settled by the system, which takes the entity of its settling
system, except that the first system of Those-Who-Share (founded on or after 555) and the first of The Shining Throne
(on or after 575) are the first of their entity.

The initial system is not chosen by the run: it is the anchor, which is the last system of Those-Who-Share founded on
or before EPOCH with at least two settlements by then (ExpansionHistory.initial_system). Its star is the galaxy's
initial star, and so the place of the start is the result of the generation.

Each event is dated at the end of its period. The first settlement of a system is its portal base, founded with the
system; the others are outposts made by StellarSystem._place_settlements.

The oldest systems of each entity are named by the entity (`oldest_systems`), oldest first; its oldest worlds and
settlements are named when they are made (oldest_places.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import heapq
import logging
import random
from typing import TYPE_CHECKING, Dict, List, Optional

from universe.bodies.star import Star
from universe.society.politics import settling
from universe.structure import seeds
from universe.structure.constants import SOL_REFERENCE_POSITION
from universe.structure.fixed_stars import Cell, Position, StarField

if TYPE_CHECKING:
    from universe.society.politics.political_entity import PoliticalEntity

logger = logging.getLogger(__name__)

HORIZON = datetime(750, 1, 1)  # the history runs at least to here, or to the game date if that is later
SOL_FOUNDED = datetime(518, 1, 1)
CACHE_VERSION = 1  # bumped whenever the run changes what it makes, so an old cache is not read as the new history


class Action(Enum):
    NEW_STAR = 0
    ENLARGEMENT = 1
    NEW_SETTLEMENT = 2


@dataclass(frozen=True)
class Pending:
    """The next action of a system: what it does, when it is done, and for an enlargement, which settlement."""
    when: datetime
    action: Action
    index: int = 0


class SystemHistory:
    """The history of one settled system: its star, when and by whom it was settled, and its settlements, in the order
    they were founded. Each settlement is the list of the dates of its enlargements, from the first, which is its
    founding. The first settlement is the portal base."""

    SECS_PER_YEAR = 365.2425 * 24 * 60 * 60
    NEW_STAR_AVG = 20 * SECS_PER_YEAR
    NEW_STAR_SIG = 5 * SECS_PER_YEAR
    UPGRADE_AVG = 3 * SECS_PER_YEAR / 12
    UPGRADE_SIG = 3 * SECS_PER_YEAR / 120
    SIZE_OF_CITY = 13

    def __init__(self, full_history: ExpansionHistory, star: Star, founded_at: datetime,
                 origin: Optional[SystemHistory], index: int) -> None:
        self.full_history: ExpansionHistory = full_history
        self.star: Star = star
        self.cell: Cell = star.cell
        self.seed: int = seeds.derive(full_history.seed, 'system', *self.cell)
        self.my_random: random.Random = random.Random(self.seed)
        self.chain: str = "sol" if origin is None else origin.chain + ">" + str(index)
        self.founded_at: datetime = founded_at
        self.cur_time: datetime = founded_at
        self.origin: Optional[SystemHistory] = origin
        self.children_count: int = 0
        self.children: List[SystemHistory] = []  # the systems it settled, in the order it settled them
        self.size: int = 0
        self.size_dates: List[datetime] = []  # when each step of size was done, from the start (see grow)
        self.settlements: List[List[datetime]] = [[founded_at]]  # the portal base is founded with the system
        self.pending: Optional[Pending] = None

        import universe.society.politics.political_entity as pe
        self.entity: PoliticalEntity = pe.UNITED_DIVERSITY if origin is None else origin.entity
        if self.entity == pe.UNITED_DIVERSITY \
                and self.founded_at >= datetime(555, 1, 1) and not self.full_history.was_ths_founded:
            self.entity = pe.THOSE_WHO_SHARE
            self.full_history.was_ths_founded = True
        elif self.entity == pe.UNITED_DIVERSITY \
                and self.founded_at >= datetime(575, 1, 1) and not self.full_history.was_tst_founded:
            self.entity = pe.THE_SHINING_THRONE
            self.full_history.was_tst_founded = True

    def next_action(self) -> Pending:
        """Rolls the next action from the current time: an action of the entity's profile, dated when it is done. A
        new star is only rolled once the system has the size it needs; until then the roll is redone."""
        profile = self.entity.expansion_profile
        while True:
            tech_factor: float = self._time_tech_factor(self.cur_time, profile.tech_factor)
            rolled: int = self.my_random.randint(
                1, profile.slots_for_new_star + len(self.settlements) + profile.slots_for_new_settlement)
            if rolled <= profile.slots_for_new_star:
                if self.size < profile.size_for_new_star:
                    continue
                cost: float = self.my_random.gauss(self.NEW_STAR_AVG, self.NEW_STAR_SIG) / tech_factor
                return Pending(self._after(cost), Action.NEW_STAR)
            cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / tech_factor
            when: datetime = self._after(cost)
            if rolled <= profile.slots_for_new_star + len(self.settlements):
                index: int = rolled - profile.slots_for_new_star - 1
                if index == 0:  # the portal base gets enhanced rarely. Try again.
                    index = self.my_random.randint(0, len(self.settlements) - 1)
                return Pending(when, Action.ENLARGEMENT, index)
            return Pending(when, Action.NEW_SETTLEMENT)

    def settlement_sizes_at(self, date: datetime) -> List[int]:
        """The size at `date` of each settlement founded by then, in the order they were founded."""
        sizes = [sum(1 for enlarged in dates if enlarged <= date) for dates in self.settlements]
        return [size for size in sizes if size > 0]

    def size_at(self, date: datetime) -> int:
        """The size at `date`: the size the system started with, plus the steps done by then."""
        return self.size - len(self.size_dates) + sum(1 for when in self.size_dates if when <= date)

    def settlements_at(self, date: datetime) -> int:
        """The number of settlements founded by `date`."""
        return sum(1 for dates in self.settlements if dates[0] <= date)

    def grow(self, when: datetime) -> None:
        """One more step of size, done at `when`."""
        self.size += 1
        self.size_dates.append(when)

    @property
    def settlement_sizes(self) -> List[int]:
        """The sizes at the game date the history was made for."""
        return self.settlement_sizes_at(self.full_history.now)

    def _after(self, cost: float) -> datetime:
        return self.cur_time + timedelta(seconds=cost)

    # Tech slowly advances for everybody.
    def _time_tech_factor(self, now: datetime, base_tech_factor: float) -> float:
        years: float = (now - datetime(518, 1, 1)).total_seconds() / SystemHistory.SECS_PER_YEAR
        return (1 + years / 100) * base_tech_factor


class ExpansionHistory:
    """Every system settled from Sol up to the horizon, with the stars of the galaxy they are in. The two flags remember
    whether the first system of Those-Who-Share and of The Shining Throne was founded: they belong to the run, which is
    in date order, so two runs of the same seed give the same history."""

    def __init__(self, galaxy_seed: int, now: datetime) -> None:
        self.galaxy_seed: int = galaxy_seed
        self.seed: int = seeds.derive(galaxy_seed, 'history')
        self.now: datetime = now
        self.horizon: datetime = max(now, HORIZON)
        self.stars: StarField = StarField(galaxy_seed)
        self.was_ths_founded: bool = False
        self.was_tst_founded: bool = False
        self.dropped_already_settled: List[datetime] = []  # when each settling was dropped, and why
        self.dropped_no_candidate: List[datetime] = []

        sol_star: Star = self.stars.nearest_of_type(SOL_REFERENCE_POSITION, Star.Type.G)
        self.sol_position: Position = sol_star.position
        sol = SystemHistory(self, sol_star, SOL_FOUNDED, None, 0)
        sol.size = 5000
        sol.settlements = [[sol.founded_at] * 100]
        # Blatant lie which represents the wish for expansion in sol.
        self.settled: Dict[Cell, SystemHistory] = {sol.cell: sol}
        self._run(sol)

        self.all_settled: List[SystemHistory] = sorted(self.settled.values(), key=lambda system: system.founded_at)
        # The ones founded after `now` are not part of the history the game knows yet.
        self.all_systems: List[SystemHistory] = [system for system in self.all_settled if system.founded_at <= now]
        self._by_cell: Dict[Cell, SystemHistory] = {system.cell: system for system in self.all_systems}
        self._name_oldest_systems()

    def _name_oldest_systems(self) -> None:
        """The oldest systems of each entity take the names it gave them by hand, oldest first. Foundation dates never
        change, and a run to a later date only adds younger systems, so a system keeps its name whatever the date."""
        named: Dict[str, int] = {}
        for system in self.all_settled:
            taken: int = named.get(system.entity.name, 0)
            if taken < len(system.entity.oldest_systems):
                system.star.name = system.entity.oldest_systems[taken]
            named[system.entity.name] = taken + 1

    def to_dict(self) -> dict:
        """The whole history as plain data, for the cache of the run (data/Cache/<seed>/history.json): every settled
        system up to the horizon, with its star, its entity, the system that settled it and its settlements."""
        return {
            'version': CACHE_VERSION,
            'galaxy_seed': self.galaxy_seed,
            'horizon': self.horizon.isoformat(),
            'settling_reach_ly': settling.SETTLING_REACH,
            'systems': [
                {
                    'cell': list(system.cell),
                    'name': system.star.name,
                    'type': system.star.type.name,
                    'position': list(system.star.position),
                    'founded_at': system.founded_at.isoformat(),
                    'entity': system.entity.name,
                    'chain': system.chain,
                    'settled_by': None if system.origin is None else list(system.origin.cell),
                    'settlements': [[date.isoformat() for date in dates] for dates in system.settlements],
                }
                for system in self.all_settled
            ],
        }

    def system_at(self, cell: Cell) -> Optional[SystemHistory]:
        """The history of the system of a star's cell, if the star is settled as of the game date."""
        return self._by_cell.get(cell)

    def initial_system(self, epoch: datetime) -> SystemHistory:
        """The system a new game starts in: the last one of Those-Who-Share founded on or before `epoch` that has at
        least two settlements by then; a system still without them gives way to the next newest. Dates and entities do
        not depend on the date the history is run to, so the choice is the same whatever `now` is. A history without
        one is an error: a galaxy needs its initial system."""
        # local: the entities import the people, who import the galaxy
        import universe.society.politics.political_entity as pe
        candidates = [system for system in self.all_settled
                      if system.entity == pe.THOSE_WHO_SHARE and system.founded_at <= epoch]
        for system in reversed(candidates):
            if len(system.settlement_sizes_at(epoch)) >= 2:
                return system
        raise RuntimeError(f"No system of Those-Who-Share had two settlements by {epoch:%Y-%m-%d} in the history of "
                           f"galaxy {self.galaxy_seed}.")

    def _run(self, sol: SystemHistory) -> None:
        """Takes the actions of all the systems in date order until the horizon (see the module docstring)."""
        queue: List[tuple[datetime, Cell]] = []
        self._schedule(sol, queue)
        while queue:
            when, cell = heapq.heappop(queue)
            if when >= self.horizon:
                break
            system: SystemHistory = self.settled[cell]
            self._take(system, queue)
            self._schedule(system, queue)

    def _schedule(self, system: SystemHistory, queue: List[tuple[datetime, Cell]]) -> None:
        system.pending = system.next_action()
        heapq.heappush(queue, (system.pending.when, system.cell))

    def _take(self, system: SystemHistory, queue: List[tuple[datetime, Cell]]) -> None:
        """The pending action of a system, done: the time has come to it."""
        pending: Optional[Pending] = system.pending
        assert pending is not None, "a system is only queued with its next action"
        system.cur_time = pending.when
        if pending.action is Action.NEW_STAR:
            star: Optional[Star] = settling.draw_candidate(self.stars, system.star, self.sol_position,
                                                           system.my_random)
            if star is None:
                self.dropped_no_candidate.append(pending.when)
            elif star.cell in self.settled:
                self.dropped_already_settled.append(pending.when)
            else:
                child = SystemHistory(self, star, pending.when, system, system.children_count)
                system.children_count += 1
                system.children.append(child)
                self.settled[child.cell] = child
                self._schedule(child, queue)
        elif pending.action is Action.ENLARGEMENT:
            system.grow(pending.when)
            system.settlements[pending.index].append(pending.when)
        else:
            system.grow(pending.when)
            system.settlements.append([pending.when])

    def log_results(self) -> None:
        """Logs the header, the dropped settlings, then the results (see results_text)."""
        logger.info(f"Expansion history of galaxy {self.galaxy_seed}: to {self.now.strftime('%Y-%m-%d')}, run to "
                    f"{self.horizon.strftime('%Y-%m-%d')}.")
        logger.info(self.dropped_text())
        logger.info(self.results_text())

    def dropped_text(self) -> str:
        """The settlings dropped up to the game date, and why."""
        already = sum(1 for when in self.dropped_already_settled if when <= self.now)
        none = sum(1 for when in self.dropped_no_candidate if when <= self.now)
        return (f"Settling actions dropped up to {self.now:%Y-%m-%d}: {already} because the star was already settled, "
                f"{none} because no star was in reach.")

    def results_text(self) -> str:
        """The systems of each entity, then how many each has and how many have cities, as the log shows them."""
        by_entity: Dict[str, List[SystemHistory]] = {}
        for system in self.all_systems:
            by_entity.setdefault(system.entity.name, []).append(system)

        text: str = "\n\nRESULTS:"
        for entity, systems in by_entity.items():
            big = sum(1 for system in systems if max(system.settlement_sizes) >= SystemHistory.SIZE_OF_CITY)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with cities"
            for system in systems:
                largest = sorted(system.settlement_sizes, reverse=True)
                  # a copy: the list is in the order of foundation
                settlement_list: str = ''
                for i in range(0, 5):
                    if len(largest) > i:
                        settlement_list += str(largest[i]) + ', '
                if len(largest) > 5:
                    settlement_list += '...'
                text += (
                    f"\n- System '{system.chain}',"
                    f" founded {system.founded_at.strftime('%Y-%m-%d')},"
                    f" size {system.size_at(self.now)},"
                    f" {system.settlements_at(self.now)} settlements: {settlement_list}"
                    )

        text += "\n\nSUMMARY:"
        for entity, systems in by_entity.items().__reversed__():
            big = sum(1 for system in systems if max(system.settlement_sizes) >= SystemHistory.SIZE_OF_CITY)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with cities."

        return text
