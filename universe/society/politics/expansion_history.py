"""The expansion of mankind from Sol: which systems were colonised, when, by which entity, and how many settlements
each has and how big they are. The history is a pure function of the galaxy's seed and of the date it is run to, so the
galaxy makes it again whenever it is made (a new game, a load) and nothing of it is saved. `simulation_script.py` runs
it without the game."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import random
from typing import Dict, List, Optional

from galaxies import seeds

logger = logging.getLogger(__name__)

class SystemHistory:
    """The history of one system: when and by whom it was founded, and its settlements, in the order they were founded
    (the first is the portal base). Each settlement is the list of the dates of its enlargements, from the first, which
    is its founding; an event is dated when its period ends. The last event of a system may fall after the date the
    history runs to: it is kept, as it is still to happen."""

    SECS_PER_YEAR = 365.2425 * 24 * 60 * 60
    NEW_STAR_AVG = 20 * SECS_PER_YEAR
    NEW_STAR_SIG = 5 * SECS_PER_YEAR
    MAX_CHILDREN = 7  # No more systems would be available after that. This is a guessing.
    UPGRADE_AVG = 3 * SECS_PER_YEAR / 12
    UPGRADE_SIG = 3 * SECS_PER_YEAR / 120
    SIZE_OF_CITY = 12

    def __init__(
            self,
            full_history: ExpansionHistory,
            index: int,
            founded_at: datetime,
            origin: Optional[SystemHistory],
            stop_at: datetime,
            ) -> None:
        self.full_history: ExpansionHistory = full_history
        self.index: int = index
        self.seed: int = full_history.seed if origin is None else seeds.derive(origin.seed, 'sh', self.index)
        self.my_random: random.Random = random.Random(self.seed)
        self.chain: str = "sol" if origin is None else origin.chain + ">" + str(index)
        self.founded_at: datetime = founded_at
        self.origin: SystemHistory = origin  # type: ignore
        self.size: int = 0

        import galaxies.politics.political_entity as pe
        self.entity: pe.PoliticalEntity =  pe.UNITED_DIVERSITY if origin is None else origin.entity
        if self.entity == pe.UNITED_DIVERSITY \
                and self.founded_at >= datetime(555,1,1) and not self.full_history.was_ths_founded:
            self.entity = pe.THOSE_WHO_SHARE
            self.full_history.was_ths_founded = True
        elif self.entity == pe.UNITED_DIVERSITY \
                and self.founded_at >= datetime(575,1,1) and not self.full_history.was_tst_founded:
            self.entity = pe.THE_SHINING_THRONE
            self.full_history.was_tst_founded = True

        self.settlements: List[List[datetime]] = [[founded_at]]  # the portal base is founded with the system
        self.stop_at: datetime = stop_at

    def run(self) -> List[SystemHistory]:
        children: List[SystemHistory] = []

        cur_time = self.founded_at
        slots_for_new_star = self.entity.expansion_profile.slots_for_new_star
        base_tech_factor = self.entity.expansion_profile.tech_factor
        while cur_time < self.stop_at:
            tech_factor = self._time_tech_factor(cur_time, base_tech_factor)
            # Roll:
            rolled = self.my_random.randint(
                1, slots_for_new_star + len(self.settlements) + self.entity.expansion_profile.slots_for_new_settlement
                )
            if rolled <= slots_for_new_star:
                if self.size >= self.entity.expansion_profile.size_for_new_star \
                        and len(children) < SystemHistory.MAX_CHILDREN:
                    # New star:
                    time_cost = self.my_random.gauss(self.NEW_STAR_AVG, self.NEW_STAR_SIG) / tech_factor
                    cur_time += timedelta(seconds=time_cost)
                    new_system = SystemHistory(
                        self.full_history,
                        len(children),
                        cur_time,
                        self,
                        self.stop_at
                    )
                    children.append(new_system)
            elif rolled <= self.entity.expansion_profile.slots_for_new_star + len(self.settlements):
                # settlement upgrade:
                time_cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / tech_factor
                cur_time += timedelta(seconds=time_cost)  # an event is dated when its period ends
                self.size += 1

                index = rolled - self.entity.expansion_profile.slots_for_new_star - 1
                if index == 0:  # the portal base gets enhanced rarely. Try again.
                    index = self.my_random.randint(0, len(self.settlements) - 1)
                self.settlements[index].append(cur_time)
            else:
                # New settlement:
                time_cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / tech_factor
                cur_time += timedelta(seconds=time_cost)
                self.size += 1
                self.settlements.append([cur_time])

        # Now, for each children, add its run:
        result: List[SystemHistory] = list(children)
        for child in children:
            result.extend(child.run())

        return result

    def settlement_sizes_at(self, date: datetime) -> List[int]:
        """The size at `date` of each settlement founded by then, in the order they were founded."""
        sizes = [sum(1 for enlarged in dates if enlarged <= date) for dates in self.settlements]
        return [size for size in sizes if size > 0]

    @property
    def settlement_sizes(self) -> List[int]:
        """The sizes at the date the history runs to."""
        return self.settlement_sizes_at(self.stop_at)

    # Tech slowly advances for everybody.
    def _time_tech_factor(self, now: datetime, base_tech_factor: float) -> float:
        return (1 + (now - datetime(518,1,1)).total_seconds() / (100 * SystemHistory.SECS_PER_YEAR)) * base_tech_factor

class ExpansionHistory:
    """Every system colonised from Sol up to `now`, oldest first. The two flags remember whether the first system of
    Those-Who-Share and of The Shining Throne was founded: they belong to the run, not to the class, so two runs of the
    same seed give the same history."""

    def __init__(self, galaxy_seed: int, now: datetime) -> None:
        self.galaxy_seed: int = galaxy_seed
        self.seed: int = seeds.derive(galaxy_seed, 'history')
        self.now: datetime = now
        self.was_ths_founded: bool = False
        self.was_tst_founded: bool = False

        sol_system = SystemHistory(self, 0, datetime(518,1,1), None, now)
        sol_system.size = 5000
        sol_system.settlements = [[sol_system.founded_at] * 100]
            # Blatant lie which represents the wish for expansion in sol.
        self.all_systems: List[SystemHistory] = [sol_system]
        self.all_systems.extend(sol_system.run())

        # The ones founded after `now` are not part of the history yet.
        self.all_systems = [system for system in self.all_systems if system.founded_at <= now]
        self.all_systems.sort(key=lambda system: system.founded_at)

    def initial_system(self, epoch: datetime) -> SystemHistory:
        """The system a new game starts in: the last one of Those-Who-Share founded on or before `epoch` that has an
        outpost by then; a system still without one (too young) gives way to the next newest. Dates and entities do
        not depend on the date the history is run to, so the choice is the same whatever `now` is. A history without
        one is an error: a galaxy needs its initial system."""
        import galaxies.politics.political_entity as pe  # local: the entities import the people, who import the galaxy
        candidates = [system for system in self.all_systems
                      if system.entity is pe.THOSE_WHO_SHARE and system.founded_at <= epoch]
        for system in reversed(candidates):
            if len(system.settlement_sizes_at(epoch)) >= 2:
                return system
        raise RuntimeError(f"No system of Those-Who-Share had an outpost by {epoch:%Y-%m-%d} in the history of "
                           f"galaxy {self.galaxy_seed}.")

    def log_results(self) -> None:
        """Logs the systems of each entity, then how many each has and how many have cities."""
        logger.info(f"Expansion history of galaxy {self.galaxy_seed}: to {self.now.strftime('%Y-%m-%d')}.")
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
                    f" size {system.size},"
                    f" {len(system.settlements)} settlements: {settlement_list}"
                    )

        text += "\n\nSUMMARY:"
        for entity, systems in by_entity.items().__reversed__():
            big = sum(1 for system in systems if max(system.settlement_sizes) >= SystemHistory.SIZE_OF_CITY)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with cities."

        logger.info(text)
