"""The names an entity gave by hand to its oldest worlds and settlements, which override the generated ones: the first
name goes to the oldest, and so on, and the places beyond the end of a list keep their generated names. (The oldest
systems are named by the history itself, ExpansionHistory.)

A place is as old as its foundation: a settlement's own, a world's the one of its first outpost. Those dates never
change, and a history run to a later date only adds younger places, so a place keeps its name whatever the game date
is. The oldest are found by building the systems from the oldest on (PlaceRows) and stopping as soon as no later system
can hold an older world or settlement. The names are worked out once for each entity, before its first system is made,
and each world and outpost takes its own when it is made (RockyWorld, Outpost)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from universe.society.people.person import Ethnicity
    from universe.society.politics.political_entity import PoliticalEntity
    from universe.structure.galaxy import Galaxy


@dataclass(frozen=True)
class OldestNames:
    """The hand-given names of one entity by the seed of the place that has them; a settlement's also holds the
    ethnicity of its people, if the entity gave one."""
    worlds: dict[int, str]
    settlements: dict[int, tuple[str, Optional[Ethnicity]]]


class OldestPlaces:

    def __init__(self, galaxy: Galaxy) -> None:
        self._galaxy: Galaxy = galaxy
        self._names: dict[str, OldestNames] = {}
        self._computing: set[str] = set()

    def names_of(self, entity: Optional[PoliticalEntity]) -> Optional[OldestNames]:
        """The names of the entity's oldest places, worked out the first time. None without an entity, and while they
        are being worked out: the systems built for that are not named."""
        if entity is None or entity.name in self._computing:
            return None
        if entity.name not in self._names:
            self._computing.add(entity.name)
            try:
                self._names[entity.name] = self._work_out(entity)
            finally:
                self._computing.discard(entity.name)
        return self._names[entity.name]

    def _work_out(self, entity: PoliticalEntity) -> OldestNames:
        world_names: list[str] = entity.oldest_worlds
        settlement_names: list[tuple[str, Optional[Ethnicity]]] = entity.oldest_settlements
        first_outposts: dict[int, datetime] = {}  # world seed: when its first outpost was founded
        settlements: list[tuple[datetime, int]] = []  # when founded, seed
        for system in (system for system in self._galaxy.history.all_systems if system.entity == entity):
            cut: Optional[datetime] = self._cut(sorted(first_outposts.values()), len(world_names),
                                                sorted(date for date, _ in settlements), len(settlement_names))
            if cut is not None and system.founded_at > cut:
                break  # nothing founded in it, or after it, is older than what the lists have already
            for row in self._galaxy.place_rows.of(system):
                founded: datetime = row.enlargement_dates[0]
                first_outposts[row.world_seed] = min(founded, first_outposts.get(row.world_seed, founded))
                settlements.append((founded, row.seed))
        oldest_worlds = sorted((founded, seed) for seed, founded in first_outposts.items())
        return OldestNames(
            worlds={seed: name for (_, seed), name in zip(oldest_worlds, world_names)},
            settlements={seed: named for (_, seed), named in zip(sorted(settlements), settlement_names)})

    @staticmethod
    def _cut(world_dates: list[datetime], worlds_named: int, settlement_dates: list[datetime],
             settlements_named: int) -> Optional[datetime]:
        """The date after which nothing can still enter the lists: the one of the last place the lists need, None while
        a list is not full yet. With nothing to name, any date will do."""
        cuts: list[datetime] = []
        for dates, count in ((world_dates, worlds_named), (settlement_dates, settlements_named)):
            if count == 0:
                continue
            if len(dates) < count:
                return None
            cuts.append(dates[count - 1])
        return max(cuts) if cuts else datetime.min
