from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional

import galaxies.constants
from galaxies.orbit_layout import OrbitKind
from galaxies.world import World
if TYPE_CHECKING:
    from galaxies.stellar_system import StellarSystem


class Orbit:
    """One orbit of a stellar system, numbered from the star (1.0 is the closest, then 2.0, 3.0... every kind together). Its `kind` and
    `distance_from_star` come from the system's layout (`OrbitLayout`). An earthlike orbit can have 2 planets, even more
    later, but very seldom. Asteroid belt and jovian orbits have none for now: they only mark where they are (see
    orbit_layout.py)."""

    def __init__(self,
                 parent_stellar_system: StellarSystem,
                 number: float,
                 kind: OrbitKind,
                 distance_from_star: float,
                 saved_alterations: dict
                 ) -> None:
        self.parent_stellar_system: StellarSystem = parent_stellar_system
        self.number: float = number
        self.kind: OrbitKind = kind
        self.seed: float = (self.parent_stellar_system.seed + self.number + 1) % galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.distance_from_star: float = distance_from_star  # metres: the semi-major axis, or the middle of a belt

        self.planets: List[World] = []
        if kind is OrbitKind.EARTHLIKE:
            world_count = max(min(int(my_random.gauss(1, 0.2)), 2), 1)  # >1 is extraordinary!
            for _ in range(world_count):
                self.planets.append(World(self, None, self.saved_alterations))

    def set_altered(self) -> Orbit:
        self.is_altered = True
        self.parent_stellar_system.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(int(self.number))  # "3", not "3.0": the key the savefiles hold

    def get_alterations(self) -> Optional[dict]:
        alterations = {}
        if self.is_altered:
            for world in self.planets:
                if world.is_altered:
                    world_alterations: Optional[dict] = world.get_alterations()
                    if world_alterations:
                        alterations[world.get_alterations_key()] = world_alterations
        if not alterations:
            return None
        return alterations
