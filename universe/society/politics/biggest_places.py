"""The biggest systems, worlds and settlements of a political entity at a date, as its history made them: the ones with
the largest total size. A settlement's size is its own; a world's and a system's is the sum of the settlements on it.

The history knows no world, and a world is known only once its system is built, so the systems are built to be read
(Galaxy.preview_system), from the biggest on, only while one can still enter the lists, and each only once per game.
The result is a pure function of the galaxy seed, the entity and the year, so what an NPC says about where they were
born never changes with the game date. The people ask for it (Person._generate_place_of_birth, Person.diploma_place).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from universe.society.people.person import Ethnicity
    from universe.society.politics.expansion_history import SystemHistory
    from universe.society.politics.oldest_places import OldestNames
    from universe.society.politics.place_rows import PlaceRows
    from universe.society.politics.political_entity import PoliticalEntity
    from universe.structure.galaxy import Galaxy

BIGGEST_SYSTEMS = 5  # how many of each the lists keep
BIGGEST_WORLDS = 7
BIGGEST_SETTLEMENTS = 20


@dataclass(frozen=True)
class Ranked:
    """A system or a world of the lists, with its total size (and for a world, the system it is in)."""
    name: str
    size: int
    system: str = ''


@dataclass(frozen=True)
class Place:
    """A settlement of the lists. `ethnicity` is the one most of its people have, None if it has none that matters."""
    name: str
    world: str
    system: str
    size: int
    ethnicity: Optional[Ethnicity] = None


@dataclass(frozen=True)
class Biggest:
    systems: tuple[Ranked, ...]
    worlds: tuple[Ranked, ...]
    settlements: tuple[Place, ...]


class BiggestPlaces:
    """The lists of one galaxy, by entity and year, and the rows of the systems built to make them."""

    def __init__(self, galaxy: Galaxy, rows: PlaceRows) -> None:
        self._galaxy: Galaxy = galaxy
        self._rows: PlaceRows = rows
        self._lists: dict[tuple[str, int], Biggest] = {}

    def at(self, entity: PoliticalEntity, date: datetime) -> Biggest:
        """The biggest places of `entity` as of the start of the year of `date`."""
        key: tuple[str, int] = (entity.name, date.year)
        if key not in self._lists:
            self._lists[key] = self._rank(entity, datetime(date.year, 1, 1))
        return self._lists[key]

    def _rank(self, entity: PoliticalEntity, when: datetime) -> Biggest:
        """Takes the systems from the biggest on, building one only if it can still enter the lists (a world is not
        bigger than its system, and a settlement not bigger than the biggest of its system); equal sizes are told apart
        by the seeds, so the lists do not depend on which systems were skipped. The names are the ones of the real
        places, with the hand-given ones of the entity's oldest places (OldestPlaces)."""
        named: Optional[OldestNames] = self._galaxy.oldest_places.names_of(entity)
        systems: list[tuple[SystemHistory, int]] = sorted(
            ((system, sum(system.settlement_sizes_at(when))) for system in self._galaxy.history.all_systems
             if system.entity == entity and system.founded_at <= when),
            key=lambda item: (-item[1], item[0].chain))
        worlds: dict[int, tuple[int, str, str]] = {}  # by seed: total size, name, system
        settlements: list[tuple[int, int, Place]] = []  # size, seed, place
        for system, total in systems:
            world_cut: Optional[int] = self._cut(sorted((size for size, _, _ in worlds.values()), reverse=True),
                                                 BIGGEST_WORLDS)
            settlement_cut: Optional[int] = self._cut(sorted((size for size, _, _ in settlements), reverse=True),
                                                      BIGGEST_SETTLEMENTS)
            if world_cut is not None and total < world_cut \
                    and settlement_cut is not None and max(system.settlement_sizes_at(when)) < settlement_cut:
                continue
            for row in self._rows.of(system):
                size: int = row.size_at(when)
                if size == 0:
                    continue
                world: str = named.worlds.get(row.world_seed, row.world) if named else row.world
                name, ethnicity = named.settlements.get(row.seed, (row.name, None)) if named else (row.name, None)
                worlds[row.world_seed] = (worlds.get(row.world_seed, (0, '', ''))[0] + size, world, row.system)
                settlements.append((size, row.seed, Place(name, world, row.system, size, ethnicity)))
        top_worlds = sorted(((-size, seed, name, in_system) for seed, (size, name, in_system) in worlds.items()))
        top_settlements = sorted(settlements, key=lambda item: (-item[0], item[1]))
        return Biggest(
            systems=tuple(Ranked(system.star.name + " System", total) for system, total in systems[:BIGGEST_SYSTEMS]),
            worlds=tuple(Ranked(name, -negative, in_system) for negative, _, name, in_system
                         in top_worlds[:BIGGEST_WORLDS]),
            settlements=tuple(place for _, _, place in top_settlements[:BIGGEST_SETTLEMENTS]))

    @staticmethod
    def _cut(sizes_descending: list[int], count: int) -> Optional[int]:
        """The size of the last one that is kept, None while fewer than `count` are known (anything can enter)."""
        return sizes_descending[count - 1] if len(sizes_descending) >= count else None
