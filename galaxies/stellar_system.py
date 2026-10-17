from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

import logging
import math
import random
import galaxies.constants
from common.units import format_compact_distance
from galaxies.body import Body
from galaxies.star import Star
from galaxies.world import World
from galaxies.orbit import Orbit
from galaxies.orbit_layout import OrbitLayout
from galaxies.politics import political_entity
if TYPE_CHECKING:
    from galaxies.galaxy import Galaxy

logger = logging.getLogger(__name__)

class StellarSystem:

    def __init__(self, parent_galaxy: Galaxy, star: Star, saved_alterations: dict) -> None:
        ''' Using galactic coordinates here, in ly: the system is where its star is. The star is given by the galaxy.'''
        self.parent_galaxy: Galaxy = parent_galaxy
        self.entity_name: str = 'Those-Who-Share'
        self.x, self.y, self.z = star.position
        self.seed: float = StellarSystem.seed_of(self.parent_galaxy.seed, self.x, self.y, self.z)
        my_random: random.Random = random.Random(self.seed)
        self.political_entity = political_entity.THOSE_WHO_SHARE
        self.star: Star = star  # the system's star, as a body ships can navigate to
        self.star.attach_to(self)
        self.name: str = self.star.name + " System"

        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.orbits: List[Orbit] = self._generate_orbits(my_random)

    def _generate_orbits(self, my_random: random.Random) -> List[Orbit]:
        """The orbits of the system, nearest first and numbered 1.0, 2.0...: earthlike planets, asteroid belts and jovian
        planets, at distances that follow the star's luminosity (see orbit_layout.py); none for a star of type O. The
        initial system always has an earthlike planet in orbit `OrbitLayout.INITIAL_ORBIT_NUMBER`. The layout is logged."""
        is_initial_system = self.star.position == galaxies.constants.INITIAL_STAR_POSITION
        layout = OrbitLayout.generate(self.star, my_random, is_initial_system)
        orbits = [
            Orbit(self, plan.number, plan.kind, plan.distance, self.saved_alterations)
            for plan in layout.plans
        ]
        self._log_orbits(layout, orbits)
        return orbits

    def _log_orbits(self, layout: OrbitLayout, orbits: List[Orbit]) -> None:
        scales = layout.scales
        logger.info(
            f"Orbits of {self.name}: {len(orbits)} orbits. Star {self.star.type.name}: luminosity "
            f"{scales.luminosity:.3g} W, mass {scales.mass:.3g} kg. Inner edge {format_compact_distance(scales.inner_edge)}, "
            f"snow line {format_compact_distance(scales.snow_line)}."
        )
        if layout.attempts > 1:
            logger.info(f" - Initial system: {layout.attempts} layouts drawn for the initial planet"
                        + (" (none did: the fixed layout was used)" if layout.needed_fallback else ""))
        for orbit in orbits:
            period = math.tau * math.sqrt(
                orbit.distance_from_star ** 3 / (World.GRAVITATIONAL_CONSTANT * self.star.mass)
            )
            logger.info(
                f" - Orbit {orbit.number}: {orbit.kind.value}, {format_compact_distance(orbit.distance_from_star)}, "
                f"period {period:.3g} s"
            )

    @staticmethod
    def seed_of(galaxy_seed: float, x: float, y: float, z: float) -> float:
        '''The seed of the stellar system at galactic coordinates (x, y, z), in ly. Its star's seed is one more.'''
        return (galaxy_seed + x*1e1 + y + z*1e-5 + 1) % galaxies.constants.SEEDS_SCALING

    def almanack(self) -> str:
        '''Markdown almanack'''
        text: str = (
            f"## {self.name} ({self.political_entity.name})\n"
            f"* Galactic coordinates ({self.x}ly, {self.y}ly, {self.z}ly )\n"
        )
        text += self.star.almanack()
        AU: float = 1.496e11  # m. The almanack is for players: AU, like the planets' entries.
        text += "### Orbits\n" + ''.join(
            f"* Orbit {int(orbit.number)}: {orbit.kind.value}, {orbit.distance_from_star / AU:.2f} AU\n"
            for orbit in self.orbits
        )
        text += ''.join(planet.almanack() for orbit in self.orbits for planet in orbit.planets)
        return text

    def set_altered(self) -> StellarSystem:
        self.is_altered = True
        self.parent_galaxy.set_altered()
        return self

    def get_alterations_key(self) -> str:
        '''The integer cell of the star, so that the key is the same whatever the float position.'''
        return " ".join(str(c) for c in self.star.cell)

    def get_alterations(self) -> Optional[dict]:
        alterations = {}
        if self.is_altered:
            for orbit in self.orbits:
                if orbit.is_altered:
                    orbit_alterations: Optional[dict] = orbit.get_alterations()
                    if orbit_alterations:
                        alterations[orbit.get_alterations_key()] = orbit_alterations
                    else:
                        alterations.pop(orbit.get_alterations_key(), None)
        if not alterations:
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
                result = result + list(planet.moons)
        return result
