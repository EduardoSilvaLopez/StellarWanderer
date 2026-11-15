"""The tidings of the galaxy, so the pilot can learn what is going on. Each tiding is dated by day and scoped to whom it
concerns. The tidings are the built-in list and the systems settled in the history, seen from a location: a settling by
the location's entity is an entity tiding, any other one a mankind tiding. The ages per scope are the window of days a
tiding stays current."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from galaxies.politics.expansion_history import ExpansionHistory
    from galaxies.settlement import Settlement
    from galaxies.stellar_system import StellarSystem


class Scope(Enum):
    MANKIND = 'mankind'
    ENTITY = 'entity'
    SYSTEM = 'system'
    SETTLEMENT = 'settlement'


@dataclass(frozen=True)
class Tiding:
    day: date
    scope: Scope
    text: str


DAY: timedelta = timedelta(days=1)

# The window of ages per scope. A tiding is current from today - MAX_AGE to today - MIN_AGE.
MIN_AGE: dict[Scope, timedelta] = {
    Scope.MANKIND: 20 * DAY,
    Scope.ENTITY: 5 * DAY,
    Scope.SYSTEM: 1 * DAY,
    Scope.SETTLEMENT: 0 * DAY,
}
MAX_AGE: dict[Scope, timedelta] = {
    Scope.MANKIND: 180 * DAY,
    Scope.ENTITY: 90 * DAY,
    Scope.SYSTEM: 15 * DAY,
    Scope.SETTLEMENT: 5 * DAY,
}

# TODO: the built-in tidings.
STATIC_TIDINGS: List[Tiding] = [
    Tiding(date(700, 1, 3), Scope.SYSTEM, "Paladin Xi left the system"),
]


def _is_current(tiding: Tiding, today: date) -> bool:
    return today - MAX_AGE[tiding.scope] <= tiding.day <= today - MIN_AGE[tiding.scope]


class Tidings:
    def __init__(self, history: ExpansionHistory) -> None:
        self.history: ExpansionHistory = history
        self._cached_key: Optional[tuple[date, Optional[StellarSystem], Optional[Settlement]]] = None
        self._cached: List[Tiding] = []

    def collect_for(self, today: date, system: StellarSystem, settlement: Optional[Settlement]) -> List[Tiding]:
        key = (today, system, settlement)
        if key == self._cached_key:
            return list(self._cached)

        # Get the static ones:
        result: List[Tiding] = [tiding for tiding in STATIC_TIDINGS if _is_current(tiding, today)]

        # Get the new systems settled: a settling by the location's entity is an entity tiding, the others mankind's.
        for settled in self.history.all_systems:
            scope = Scope.ENTITY if settled.entity is system.political_entity else Scope.MANKIND
            tiding = Tiding(settled.founded_at.date(), scope, f"{settled.entity.name} settled a new system")
            if _is_current(tiding, today):
                result.append(tiding)

        # Get the settlements of this system, founded and enlarged: system tidings for this system only.
        for settlement_here in system.settlements():
            for index, enlarged in enumerate(settlement_here.enlargement_dates):
                text = f"{settlement_here.name} was founded" if index == 0 else f"{settlement_here.name} was enlarged"
                tiding = Tiding(enlarged.date(), Scope.SYSTEM, text)
                if _is_current(tiding, today):
                    result.append(tiding)

        self._cached_key = key
        self._cached = result
        return list(result)
