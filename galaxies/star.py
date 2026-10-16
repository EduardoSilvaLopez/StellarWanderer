"""The star of a stellar system, as a body ships can navigate to."""

from __future__ import annotations
from datetime import datetime
import random
from typing import TYPE_CHECKING

from common.vector3 import Vector3
import galaxies.constants
from galaxies.body import Body

if TYPE_CHECKING:
    from galaxies.stellar_system import StellarSystem


class Star(Body):
    """The star: the origin of the stellar frame, at rest. It has no surface: nothing binds to it."""

    SOLAR_MASS = 1.989e30  # kg
    SOLAR_RADIUS = 6.957e8  # m

    is_world = False

    def __init__(self, system: StellarSystem) -> None:
        self.seed = (system.seed + 1) % galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)
        self._system: StellarSystem = system
        self.name: str = Star._generate_name(my_random)
        self.type = Star._generate_star_type(my_random)
        self.color: tuple = self._generate_color(my_random)
        self.radius: int = self._generate_radius(my_random)
        self.mass: float = self._generate_mass(my_random)
        self.heat_radius: int = self._generate_heat_effect_distance(my_random)
        self.death_radius: int = self._generate_heat_death_distance(my_random)

    @staticmethod
    def _generate_name(my_random: random.Random) -> str:
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
    
    @staticmethod
    def _generate_star_type(my_random: random.Random) -> str:
        rnd = my_random.random()

        if rnd <= 0.75:  # M, red dwarf
            result = "Red dwarf (M)"
        elif rnd <= 0.88:  # K, Orange-ish
            result = "Orange-ish (K)"
        elif rnd <= 0.96:  # G, Yellow(-ish)
            result = "Yellow star (G)"
        elif rnd <= 0.99:  # F, yellow-white
            result = "Yellow-white (F)"
        elif rnd <= 0.997:  # A, White
            result = "White (A)"
        elif rnd <= 0.999999:  # B, Blue-white
            result = "Blue (B)"
        else:  # O, Blue giant
            result = "Blue giant (O)"

        return result

    def _generate_color(self, rnd: random.Random) -> tuple:

        base_color: tuple = None
        if self.type == "Red dwarf (M)":
            base_color = (255, 96, 96)
        elif self.type == "Orange-ish (K)":
            base_color = (255, 192, 128)
        elif self.type == "Yellow star (G)":
            base_color = (255, 255, 128)
        elif self.type == "Yellow-white (F)":
            base_color = (255, 255, 224)
        elif self.type == "White (A)":
            base_color = (255, 255, 255)
        elif self.type == "Blue (B)":
            base_color = (192, 192, 255)
        elif self.type == "Blue giant (O)":
            base_color = (96, 96, 255)

        color_variation = (
            -16 + rnd.randint(0, 32),
            -16 + rnd.randint(0, 32),
            -16 + rnd.randint(0, 32)
        )

        result = tuple(max(0, min(255, b + v)) for b, v in zip(base_color, color_variation))
        return result

    def _generate_radius(self, rnd: random.Random) -> int:
        radius: int = None
        if self.type == "Red dwarf (M)":
            radius = int(200000000 * (0.4 + 1.2 * rnd.random()))
        elif self.type == "Orange-ish (K)":
            radius = int(550000000 * (0.9 + 0.2 * rnd.random()))
        elif self.type == "Yellow star (G)":
            radius = int(700000000 * (0.95 + 0.1 * rnd.random()))
        elif self.type == "Yellow-white (F)":
            radius = int(880000000 * (0.9 + 0.2 * rnd.random()))
        elif self.type == "White (A)":
            radius = int(1300000000 * (0.75 + 0.5 * rnd.random()))
        elif self.type == "Blue (B)":
            radius = int(3500000000 * (0.85 + 0.3 * rnd.random()))
        elif self.type == "Blue giant (O)":
            radius = int(10500000000 * (0.3 + 0.6 * rnd.random()))
        return radius

    def _generate_heat_effect_distance(self, rnd: random.Random) -> int:
        factor: int = 100
        if self.type == "Red dwarf (M)":
            factor = 48
        elif self.type == "Orange-ish (K)":
            factor = 76
        elif self.type == "Yellow star (G)":
            factor = 100
        elif self.type == "Yellow-white (F)":
            factor = 140
        elif self.type == "White (A)":
            factor = 300
        elif self.type == "Blue (B)":
            factor = 700
        elif self.type == "Blue giant (O)":
            factor = 7500

        return int(self.radius * factor * (0.9 + 0.2 * rnd.random()))

    def _generate_heat_death_distance(self, rnd: random.Random) -> int:
        factor: int = 10
        if self.type == "Red dwarf (M)":
            factor = 4.6
        elif self.type == "Orange-ish (K)":
            factor = 7.5
        elif self.type == "Yellow star (G)":
            factor = 10
        elif self.type == "Yellow-white (F)":
            factor = 14
        elif self.type == "White (A)":
            factor = 30
        elif self.type == "Blue (B)":
            factor = 70
        elif self.type == "Blue giant (O)":
            factor = 750

        return int(self.radius * factor * (0.9 + 0.2 * rnd.random()))

    def _generate_mass(self, rnd: random.Random) -> int:
        """Main-sequence mass (kg) from the radius: R ~ M^0.8 up to one solar radius, R ~ M^0.57 above.
        Derived from the radius so it consumes no random numbers."""
        radius_ratio = self.radius / Star.SOLAR_RADIUS
        exponent = 1.0 / 0.8 if radius_ratio <= 1.0 else 1.0 / 0.57
        return Star.SOLAR_MASS * radius_ratio ** exponent * (0.98 + 0.04 * rnd.random())

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @property
    def stellar_system(self) -> StellarSystem:
        return self._system
