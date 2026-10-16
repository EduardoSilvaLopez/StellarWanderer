from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

import random
from common.units import format_compact_distance
import galaxies.constants
from galaxies.body import Body
from galaxies.star import Star
from galaxies.world import World
from galaxies.orbit import Orbit
from galaxies.politics import political_entity
if TYPE_CHECKING:
    from galaxies.galaxy import Galaxy

class StellarSystem:

    def __init__(self, parent_galaxy: Galaxy, x: float, y: float, z: float, saved_alterations: dict) -> None:
        ''' Using galactic coordinates here. Whatever that may mean in the future (unit will prolly not meters).'''
        self.parent_galaxy: Galaxy = parent_galaxy
        self.entity_name: str = 'Those-Who-Share'
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.seed: float = (self.parent_galaxy.seed + self.x*1e1 + self.y + self.z*1e-5 + 1) % galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)
        self.political_entity = political_entity.THOSE_WHO_SHARE
        self.star: Star = Star(self)  # the system's star, as a body ships can navigate to
        self.name: str = self.star.name + " System"

        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        orbits_count = min(int(my_random.gauss(4.5, 1)), 7)
        # the first-ever system must have three orbits.
        if (x, y, z) == (26000, 0, 0): # Original stellar system.
            orbits_count = max(3, orbits_count)
        self.orbits: List[Orbit] = []
        for orbit_number in range(1, orbits_count+1):
            new_orbit = Orbit(self, orbit_number, self.saved_alterations)
            self.orbits.append(new_orbit)

    def almanack(self) -> str:
        '''Markdown almanack'''
        text: str = (
            f"## {self.name} ({self.political_entity.name})\n"
            f"* Galactic coordinates ({self.x}ly, {self.y}ly, {self.z}ly )\n"
            f"* {self.star.type} star, radius {format_compact_distance(self.star.radius)}\n"
        )
        for orbit in self.orbits:
            for planet in orbit.planets:
                text += planet.almanack()
        return text

    def set_altered(self) -> StellarSystem:
        self.is_altered = True
        self.parent_galaxy.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.x) + " " + str(self.y) + " " + str(self.z)

    def get_alterations(self) -> Optional[dict]:
        alterations = dict()
        if self.is_altered:
            for orbit in self.orbits:
                if orbit.is_altered:
                    orbit_alterations: Optional[dict] = orbit.get_alterations()
                    if orbit_alterations is not None and len(orbit_alterations) > 0:
                        alterations[orbit.get_alterations_key()] = orbit_alterations
                    else:
                        alterations.pop(orbit.get_alterations_key())
        if len(alterations) <= 0:
            return None
        return alterations

    def get_orbit(self, number: float) -> Orbit:
        return next((orbit for orbit in self.orbits if orbit.number == number), None)

    def get_all_bodies(self) -> List[Body]:
        """The star first, then every world (each planet before its moons)."""
        return [self.star] + self.get_all_worlds()

    def get_all_worlds(self) -> List[World]:
        result: List[World] = []
        for orbit in self.orbits:
            for planet in orbit.planets:
                result.append(planet)
                result = result + [m for m in planet.moons]
        return result