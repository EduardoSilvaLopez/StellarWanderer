"""What is read from the systems the game builds only to look at them: each outpost as a row (its name, its world, its
dates). A system is built the first time it is asked for and then forgotten, so the places that rank outposts (by size,
BiggestPlaces, or by age, OldestPlaces) build each system once per game between them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from universe.artifacts.settlements.settlement_kind import SettlementKind
from universe.structure.fixed_stars import Cell

if TYPE_CHECKING:
    from universe.society.politics.expansion_history import SystemHistory
    from universe.structure.galaxy import Galaxy


@dataclass(frozen=True)
class Row:
    seed: int
    name: str
    world_seed: int
    world: str
    system: str
    enlargement_dates: tuple[datetime, ...]

    def size_at(self, when: datetime) -> int:
        return sum(1 for enlarged in self.enlargement_dates if enlarged <= when)


class PlaceRows:
    """The rows of the systems built so far in one galaxy."""

    def __init__(self, galaxy: Galaxy) -> None:
        self._galaxy: Galaxy = galaxy
        self._rows: dict[Cell, tuple[Row, ...]] = {}

    def of(self, system: SystemHistory) -> tuple[Row, ...]:
        """The outposts of a system (only the ones its history has founded by the game date), as rows."""
        rows: Optional[tuple[Row, ...]] = self._rows.get(system.cell)
        if rows is None:
            built = self._galaxy.preview_system(system.star)
            rows = tuple(Row(outpost.seed, outpost.name, outpost.planet.seed, outpost.planet.name, built.name,
                             tuple(outpost.enlargement_dates))
                         for outpost in built.settlements() if outpost.kind is SettlementKind.OUTPOST)
            self._rows[system.cell] = rows
        return rows

    @property
    def built(self) -> int:
        """How many systems have been built to be read."""
        return len(self._rows)
