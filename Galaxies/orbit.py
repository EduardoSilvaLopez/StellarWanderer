from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional

import Galaxies.constants
from Galaxies.world import World
if TYPE_CHECKING:
    from Galaxies.stellar_system import StellarSystem

'''An orbit can have 2 planets, even more later - but very seldom.'''
class Orbit:

    def __init__(self,
                 parent_stellar_system: StellarSystem,
                 number: float,
                 saved_alterations: dict
                 ) -> None:
        self.parent_stellar_system: StellarSystem = parent_stellar_system
        self.number: float = number
        self.seed: int = (self.number + self.parent_stellar_system.seed) % Galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.distance_from_star: int = self.calculate_distance_from_star(my_random)

        self.planets: List[World] = []
        world_count = max(min(int(my_random.gauss(1, 0.2)), 2), 1) # >1 is extraordinary!

        first_world = World(self, None, self.saved_alterations)
        self.planets.append(first_world)
        if world_count > 1:
            second_world = World(self, None, self.saved_alterations)
            self.planets.append(second_world)

    def calculate_distance_from_star(self, my_random: random) -> float:
        # Tuned to give ~1 AU for orbit number 3 and size of a G-type star.
        return 24.0 * self.parent_stellar_system.radius * self.number**2

    def set_altered(self) -> Orbit:
        self.is_altered = True
        self.parent_stellar_system.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.number)

    def get_alterations(self) -> Optional[dict]:
        alterations = dict()
        if self.is_altered:
            for world in self.planets:
                if world.is_altered:
                    world_alterations: Optional[dict] = world.get_alterations()
                    if world_alterations is not None:
                        alterations[world.get_alterations_key()] = world_alterations
        if alterations == {}:
            return None
        return alterations
