"""The tidings of the galaxy, so the pilot can learn what is going on. Each tiding is dated by day and scoped to whom it
concerns; the ages per scope are the window of days a tiding stays current.

The rest of the galaxy reports what happened as events, with the facts it knows; this module alone decides what an
event is to a pilot at a location (its scope and text) and whether it is told there at all (`_tiding_of`). The events
are not pushed when they happen: they are pure functions of the seed and the date, so the tidings ask every source for
the events of their window, and the same tidings come out whatever was visited, saved or loaded. A source is a function
registered with `@source` in the module that owns the logic (it must be imported before the tidings are collected); the
history and the system's incidents are the tidings' own sources."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator, List, Mapping, Optional

from universe.structure import seeds

if TYPE_CHECKING:
    from universe.society.politics.expansion_history import ExpansionHistory
    from universe.society.politics.political_entity import PoliticalEntity
    from universe.artifacts.settlements.settlement import Settlement
    from universe.structure.stellar_system import StellarSystem


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


class Happening(Enum):
    SYSTEM_SETTLED = 'system settled'
    SETTLEMENT_FOUNDED = 'settlement founded'
    SETTLEMENT_ENLARGED = 'settlement enlarged'
    WATER_EMERGENCY = 'water emergency'
    STORM_BORN = 'storm born'
    SHIP_LOST = 'ship lost'
    SHIP_RESCUED = 'ship rescued'

@dataclass(frozen=True)
class Event:
    """Something that happened, as its source knows it. What it means to the pilot is decided by `_tiding_of`."""
    day: date
    happening: Happening
    system: Optional[StellarSystem] = None  # where it happened, when that is one system
    entity: Optional[PoliticalEntity] = None  # who did it
    subject: str = ''  # the name of whom or what it happened to
    facts: Mapping[str, Any] = field(default_factory=dict)  # whatever else the source knows


# The events between two days (both included) that a pilot in the system could hear of.
Source = Callable[['StellarSystem', date, date], Iterable[Event]]
_SOURCES: List[Source] = []


def source(function: Source) -> Source:
    _SOURCES.append(function)
    return function


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
    Tiding(date(700, 1, 3), Scope.SYSTEM, "Paladin Xi left the system."),
]

# The incidents a system may have on any day, with their chance per day, drawn from the system's seed in this order (a
# new one goes last).
# TODO: more incidents.
INCIDENTS: tuple[tuple[Happening, float], ...] = (
    (Happening.SHIP_LOST, 0.005),
    (Happening.SHIP_RESCUED, 0.005),
)


def _is_current(tiding: Tiding, today: date) -> bool:
    return today - MAX_AGE[tiding.scope] <= tiding.day <= today - MIN_AGE[tiding.scope]


def _tiding_of(event: Event, system: StellarSystem) -> Optional[Tiding]:
    """What an event is to a pilot in `system`, or None when it is not told there."""
    if event.happening is Happening.SYSTEM_SETTLED and event.entity is not None:
        scope = Scope.ENTITY if event.entity is system.political_entity else Scope.MANKIND
        return Tiding(event.day, scope, f"{event.entity.name} settled a new system")
    if event.system is not system:  # the others are told in their own system only
        return None
    match event.happening:
        case Happening.SETTLEMENT_FOUNDED:
            text = f"{event.subject} was founded."
        case Happening.SETTLEMENT_ENLARGED:
            text = f"{event.subject} was enlarged."
        case Happening.WATER_EMERGENCY:
            text = f"{event.subject} had a water emergency."
        case Happening.STORM_BORN:
            width = int(float(f"{2.0 * event.facts['radius'] / 1000:.1g}"))  # one digit: 4000 Km, not 4005 Km
            text = f"A storm {width} Km wide broke out on {event.subject}."
        case Happening.SHIP_LOST:
            text = "A ship failed. We could not save the pilot."
        case Happening.SHIP_RESCUED:
            text = "A pilot used the beacon on time and could be rescued alive."
        case _:
            return None
    return Tiding(event.day, Scope.SYSTEM, text)


def _incidents(system: StellarSystem, first: date, last: date) -> Iterator[Event]:
    day = first
    while day <= last:
        chance = random.Random(seeds.derive(system.seed, 'incidents', day.toordinal()))
        for happening, probability in INCIDENTS:
            if chance.random() < probability:
                yield Event(day, happening, system)
        day += DAY


class Tidings:
    def __init__(self, history: ExpansionHistory) -> None:
        self.history: ExpansionHistory = history
        self._cached_key: Optional[tuple[date, Optional[StellarSystem], Optional[Settlement]]] = None
        self._cached: List[Tiding] = []

    def collect_for(self, today: date, system: StellarSystem, settlement: Optional[Settlement]) -> List[Tiding]:
        key = (today, system, settlement)
        if key == self._cached_key:
            return list(self._cached)

        result: List[Tiding] = [tiding for tiding in STATIC_TIDINGS if _is_current(tiding, today)]
        # Every source is asked for the widest window: the scope, so the window that applies, is decided afterwards.
        first = today - max(MAX_AGE.values())
        last = today - min(MIN_AGE.values())
        for events in [self._history_events(system, first, last), _incidents(system, first, last)] + [
                each(system, first, last) for each in _SOURCES]:
            for event in events:
                tiding = _tiding_of(event, system)
                if tiding is not None and _is_current(tiding, today):
                    result.append(tiding)

        self._cached_key = key
        self._cached = result
        return list(result)

    def _history_events(self, system: StellarSystem, first: date, last: date) -> Iterator[Event]:
        """The systems settled, and the settlements of this system founded and enlarged."""
        for settled in self.history.all_systems:
            if first <= settled.founded_at.date() <= last:
                yield Event(settled.founded_at.date(), Happening.SYSTEM_SETTLED, entity=settled.entity)
        for settlement in system.settlements():
            for index, enlarged in enumerate(settlement.enlargement_dates):
                if first <= enlarged.date() <= last:
                    happening = Happening.SETTLEMENT_FOUNDED if index == 0 else Happening.SETTLEMENT_ENLARGED
                    yield Event(enlarged.date(), happening, system, subject=settlement.name)
