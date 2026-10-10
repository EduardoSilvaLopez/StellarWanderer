from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

import random
import Galaxies.constants
from Galaxies.world import World
from Galaxies.orbit import Orbit
from Galaxies.Politics import political_entity
if TYPE_CHECKING:
    from Galaxies.galaxy import Galaxy

class StellarSystem:

    SOLAR_MASS = 1.989e30  # kg
    SOLAR_RADIUS = 6.957e8  # m

    def __init__(self, parent_galaxy: Galaxy, x: int, y: int, z: int, saved_alterations: dict) -> None:
        ''' Using galactic coordinates here. Whatever that may mean in the future (unit will prolly not meters).'''
        self.parent_galaxy: Galaxy = parent_galaxy
        self.entity_name: str = 'Those-Who-Share'
        self.x: int = x
        self.y: int = y
        self.z: int = z
        self.seed: int = (self.x + self.y + self.z + self.parent_galaxy.seed) % Galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)
        self.color, self.radius = self.generate_star_type(my_random)
        self.mass: float = self.estimate_mass()

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

        self.political_entity = political_entity.THOSE_WHO_SHARE
        self.name: str = self.generate_name(my_random)

    def generate_star_type(self, rnd: random.Random) -> tuple:
        color_code = rnd.random()
        base_color: tuple = None
        radius: int = 0
        if color_code <= 0.75: #M, red dwarf
            base_color = (255, 96, 96)
            radius = int(200000000 * (0.4 + 1.2 * rnd.random()))
        elif color_code <= 0.88: #K, Orange-ish.
            base_color = (255, 192, 128)
            radius = int(550000000 * (0.9 + 0.2 * rnd.random()))
        elif color_code <= 0.96: #G, Yellow(-ish)
            base_color = (255, 255, 128)
            radius = int(700000000 * (0.95 + 0.1 * rnd.random()))
        elif color_code <= 0.99: #F, yellow-white
            base_color = (255, 255, 224)
            radius = int(880000000 * (0.9 + 0.2 * rnd.random()))
        elif color_code <= 0.997: #A, White
            base_color = (255, 255, 255)
            radius = int(1300000000 * (0.75 + 0.5 * rnd.random()))
        elif color_code <= 0.999999: #B, Blue-white
            base_color = (192, 192, 255)
            radius = int(3500000000 * (0.85 + 0.3 * rnd.random()))
        else: #0, Blue
            base_color = (96, 96, 255)
            radius = int(10500000000 * (0.3 + 0.6 * rnd.random()))
        color_variation = (
            -16 + rnd.randint(0, 32),
            -16 + rnd.randint(0, 32),
            -16 + rnd.randint(0, 32)
        )
        star_color = tuple(max(0, min(255, b + v)) for b, v in zip(base_color, color_variation))
        return star_color, radius

    def estimate_mass(self) -> float:
        """Main-sequence mass (kg) from the radius: R ~ M^0.8 up to one solar radius, R ~ M^0.57 above.
        Derived from the radius so it consumes no random numbers."""
        radius_ratio = self.radius / StellarSystem.SOLAR_RADIUS
        exponent = 1.0 / 0.8 if radius_ratio <= 1.0 else 1.0 / 0.57
        return StellarSystem.SOLAR_MASS * radius_ratio ** exponent

    def generate_name(self, my_random: random.Random) -> str:
        """Generate a random name for the world."""
        vocals = "aeiouaeio" # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for sylIdx in range(1, my_random.randint(3, 6)):
            if (my_random.random() < 0.4):
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if (my_random.random() < 0.4):
                name += my_random.choice(consonants)

        if (my_random.random() < 0.5):
            name += "eia"

        return name.capitalize()

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
                    if orbit_alterations is not None:
                        alterations[orbit.get_alterations_key()] = orbit_alterations
        if alterations == {}:
            return None
        return alterations

    def get_orbit(self, number: float) -> Orbit:
        return next((orbit for orbit in self.orbits if orbit.number == number), None)

    def get_all_worlds(self) -> List[World]:
        result: List[World] = []
        for orbit in self.orbits:
            for planet in orbit.planets:
                result.append(planet)
                result = result + [m for m in planet.moons]
        return result