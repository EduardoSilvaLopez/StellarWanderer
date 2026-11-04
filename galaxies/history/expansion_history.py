from datetime import datetime, timedelta
import logging
import random
from typing import Dict, List, Optional

from galaxies import seeds

logger = logging.getLogger(__name__)

class ExpansionProfile:
    def __init__(
            self,
            entity: str,
            slots_for_new_star: int,
            slots_for_new_settlement: int,
            size_for_new_star,
            tech_factor: float
            ):
        self.entity = entity
        self.slots_for_new_star = slots_for_new_star
        self.slots_for_new_settlement = slots_for_new_settlement
        self.size_for_new_star = size_for_new_star
        self.tech_factor = tech_factor

LowTechImperialist = ExpansionProfile("The Shining Throne", 6, 10, 130, 0.8)  # Median 51 with cities
TechConservative = ExpansionProfile("Those-Who-Share", 2, 8, 350, 1)  # Median 16 with cities
TechOrganic = ExpansionProfile("United Diversity", 3, 6, 595, 1)  # Median 9 with cities

class SystemHistory:
    SECS_PER_YEAR = 365.2425 * 24 * 60 * 60
    NEW_STAR_AVG = 10 * SECS_PER_YEAR
    NEW_STAR_SIG = 2 * SECS_PER_YEAR
    MAX_CHILDREN = 7  # No more systems would be available after that. This is a guessing.
    UPGRADE_AVG = SECS_PER_YEAR / 12
    UPGRADE_SIG = SECS_PER_YEAR / 120
    SIZE_OF_CITY = 10

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
        self.seed: int = index if origin is None else seeds.derive(origin.seed, 'sh', self.index)
        self.my_random = random.Random(self.seed)
        self.chain: str = "sol" if origin is None else origin.chain + ">" + str(index)
        self.founded_at: datetime = founded_at
        self.origin: SystemHistory = origin  # type: ignore
        self.size: int = 0

        self.profile: ExpansionProfile = TechOrganic if origin is None else origin.profile
        if self.profile == TechOrganic \
                and self.founded_at >= datetime(555,1,1) and not self.full_history.was_ths_founded:
            self.profile = TechConservative
            self.full_history.was_ths_founded = True
        elif self.profile == TechOrganic \
                and self.founded_at >= datetime(575,1,1) and not self.full_history.was_tst_founded:
            self.profile = LowTechImperialist
            self.full_history.was_tst_founded = True

        self.settlements: List[int] = [1]
        self.stop_at: datetime = stop_at

    def run(self) -> List[SystemHistory]:
        children: List[SystemHistory] = []

        cur_time = self.founded_at
        while cur_time < self.stop_at:
            # Roll:
            rolled = self.my_random.randint(
                1, self.profile.slots_for_new_star + len(self.settlements) + self.profile.slots_for_new_settlement
                )
            if rolled <= self.profile.slots_for_new_star:
                if self.size >= self.profile.size_for_new_star and len(children) < SystemHistory.MAX_CHILDREN:
                    # New star:
                    time_cost = self.my_random.gauss(self.NEW_STAR_AVG, self.NEW_STAR_SIG) / self.profile.tech_factor
                    cur_time += timedelta(seconds=time_cost)
                    new_system = SystemHistory(
                        self.full_history,
                        len(children),
                        cur_time,
                        self,
                        self.stop_at
                    )
                    children.append(new_system)
            elif rolled <= self.profile.slots_for_new_star + len(self.settlements):
                # settlement upgrade:
                time_cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / self.profile.tech_factor
                cur_time += timedelta(seconds=time_cost)
                self.size += 1

                index = rolled - self.profile.slots_for_new_star - 1
                if index == 0:  # the portal base gets enhanced rarely. Try again.
                    index = self.my_random.randint(0, len(self.settlements) - 1)
                self.settlements[index] += 1
            else:
                # New settlement:
                time_cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / self.profile.tech_factor
                cur_time += timedelta(seconds=time_cost)
                self.size += 1
                self.settlements.append(1)

        # Now, for each children, add its run:
        result: List[SystemHistory] = list(children)
        for child in children:
            result.extend(child.run())

        return result

class ExpansionHistory:
    all_systems: List[SystemHistory] = []

    def __init__(self, called_seed: int, now: datetime):
        logger.info(
            f"Started with seed {called_seed}: to {now.strftime('%Y-%m-%d')}."
            )

        self.was_ths_founded: bool = False
        self.was_tst_founded: bool = False

        sol_system = SystemHistory(self, called_seed, datetime(518,1,1), None, now)
        sol_system.size = 5000
        sol_system.settlements = [100] # Blatant lie which represents the wish for expansion in sol.
        sol_system.chain = 'sol'
        self.all_systems = [
                sol_system,
            ]

        # Run:
        self.all_systems.extend(sol_system.run())

        # Log the results, one block per entity:
        self.all_systems = [system for system in self.all_systems if system.founded_at <= now]
        self.all_systems.sort(key=lambda s : s.founded_at)
        by_entity: Dict[str, List[SystemHistory]] = {}
        for system in self.all_systems:
            by_entity.setdefault(system.profile.entity, []).append(system)

        text: str = "\n\nRESULTS:"
        for entity, systems in by_entity.items():
            big = sum(1 for system in systems if max(system.settlements) >= SystemHistory.SIZE_OF_CITY)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with cities"
            for system in systems:
                system.settlements.sort(key=lambda s:s, reverse=True)
                settlement_list: str = ''
                for i in range(0, 5):
                    if len(system.settlements) > i+1:
                        settlement_list += str(system.settlements[i]) + ', '
                if len(system.settlements) > 5:
                    settlement_list += '...'
                text += (
                    f"\n- System '{system.chain}',"
                    f" founded {system.founded_at.strftime('%Y-%m-%d')},"
                    f" size {system.size},"
                    f" {len(system.settlements)} settlements: {settlement_list}"
                    )

        text += "\n\nSUMMARY:"
        for entity, systems in by_entity.items():
            big = sum(1 for system in systems if max(system.settlements) >= SystemHistory.SIZE_OF_CITY)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with cities."

        logger.info(text)

    # Tech slowly advances for everybody.
    def _time_tech_factor(self, now: datetime, base_tech_factor: float) -> float:
        return (1 + (datetime(518,1,1) - now).total_seconds() / (100 * SystemHistory.SECS_PER_YEAR)) * base_tech_factor
