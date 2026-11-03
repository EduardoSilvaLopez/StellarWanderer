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

LowTechImperialist = ExpansionProfile("The Shining Throne", 3, 10, 200, 0.8)
TechConservative = ExpansionProfile("Those-Who-Share", 2, 15, 300, 1)
TechOrganic = ExpansionProfile("United Diversity", 3, 5, 800, 1)

class SystemHistory:
    SECS_PER_YEAR = 365.2425 * 24 * 60 * 60
    NEW_STAR_AVG = 10 * SECS_PER_YEAR
    NEW_STAR_SIG = 2 * SECS_PER_YEAR
    UPGRADE_AVG = SECS_PER_YEAR / 12
    UPGRADE_SIG = SECS_PER_YEAR / 120

    WasThsFounded: bool = False
    WasTstFounded: bool = False

    def __init__(
            self,
            index: int,
            founded_at: datetime,
            origin: Optional[SystemHistory],
            stop_at: datetime,
            ) -> None:
        self.index: int = index
        self.seed: int = index if origin is None else seeds.derive(origin.seed, 'sh', self.index)
        self.my_random = random.Random(self.seed)
        self.chain: str = "sol" if origin is None else origin.chain + ">" + str(index)
        self.founded_at: datetime = founded_at
        self.origin: SystemHistory = origin  # type: ignore
        self.size: int = 0

        self.profile: ExpansionProfile = TechOrganic if origin is None else origin.profile
        if self.profile == TechOrganic and self.founded_at >= datetime(555,1,1) and not SystemHistory.WasThsFounded:
            self.profile = TechConservative
            SystemHistory.WasThsFounded = True
        elif self.profile == TechOrganic and self.founded_at >= datetime(575,1,1) and not SystemHistory.WasTstFounded:
            self.profile = LowTechImperialist
            SystemHistory.WasTstFounded = True

        self.settlements: int = 1
        self.stop_at: datetime = stop_at

    def run(self) -> List[SystemHistory]:
        children: List[SystemHistory] = []

        cur_time = self.founded_at
        while cur_time < self.stop_at:
            # Roll:
            rolled = self.my_random.randint(
                1, self.profile.slots_for_new_star + self.settlements + self.profile.slots_for_new_settlement
                )
            if rolled <= self.profile.slots_for_new_star and self.size >= self.profile.size_for_new_star:
                # New star:
                time_cost = self.my_random.gauss(self.NEW_STAR_AVG, self.NEW_STAR_SIG) / self.profile.tech_factor
                cur_time += timedelta(seconds=time_cost)
                new_system = SystemHistory(
                    len(children),
                    cur_time,
                    self,
                    self.stop_at
                )
                children.append(new_system)
            elif rolled <= self.profile.slots_for_new_star + self.settlements:
                # settlement upgrade:
                time_cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / self.profile.tech_factor
                cur_time += timedelta(seconds=time_cost)
                self.size += 1
            else:
                # New settlement:
                time_cost = self.my_random.gauss(self.UPGRADE_AVG, self.UPGRADE_SIG) / self.profile.tech_factor
                cur_time += timedelta(seconds=time_cost)
                self.settlements += 1
                self.size += 1

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

        sol_system = SystemHistory(called_seed, datetime(518,1,1), None, now)
        sol_system.size = 5000
        sol_system.settlements = 0 # Blatant lie which represents the wish for expansion in sol.
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
            big = sum(1 for system in systems if system.size >= 100)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with size >= 100"
            for system in systems:
                text += (
                    f"\n- System '{system.chain}',"
                    f" founded {system.founded_at.strftime('%Y-%m-%d')},"
                    f" size {system.size},"
                    f" {system.settlements} settlements"
                    )

        text += "\n\nSUMMARY:"
        for entity, systems in by_entity.items():
            big = sum(1 for system in systems if system.size >= 100)
            text += f"\n\n{entity}: {len(systems)} systems, {big} with cities."

        logger.info(text)

    # Tech slowly advances for everybody.
    def _time_tech_factor(self, now: datetime, base_tech_factor: float) -> float:
        return (1 + (datetime(518,1,1) - now).total_seconds() / (100 * SystemHistory.SECS_PER_YEAR)) * base_tech_factor
