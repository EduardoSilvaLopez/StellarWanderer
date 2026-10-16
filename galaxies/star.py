"""The star of a stellar system, as a body ships can navigate to."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
import math
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

    class Type(Enum):
        M = "Red dwarf (M)"
        K = "Orange-ish (K)"
        G = "Yellow star (G)"
        F = "Yellow-white (F)"
        A = "White (A)"
        B = "Blue (B)"
        O = "Blue giant (O)"

    is_world = False

    def __init__(self, system: StellarSystem) -> None:
        self.seed = (system.seed + 1) % galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)
        self._system: StellarSystem = system
        self.name: str = Star._generate_name(my_random)
        self.type: Star.Type = Star._generate_star_type(my_random)
        self.color: tuple = self._generate_color(my_random)
        self.radius: int = self._generate_radius(my_random)
        self.mass: int = self._generate_mass(my_random)
        self.temperature: float = self._generate_temperature(my_random)
        self.rotation_period: float = self._generate_rotation_period(my_random)
        self.heat_radius: int = self._generate_heat_effect_distance(my_random)
        self.death_radius: int = self._generate_heat_death_distance(my_random)

    @staticmethod
    def _generate_name(my_random: random.Random) -> str:
        """Generate a random name for the world."""
        vocals = "aeiouaeio"  # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for _ in range(1, my_random.randint(3, 6)):
            if my_random.random() < 0.4:
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if my_random.random() < 0.4:
                name += my_random.choice(consonants)

        if my_random.random() < 0.5:
            name += "eia"

        return name.capitalize()

    @staticmethod
    def _generate_star_type(my_random: random.Random) -> Star.Type:
        rnd = my_random.random()

        if rnd <= 0.75:
            return Star.Type.M
        elif rnd <= 0.88:
            return Star.Type.K
        elif rnd <= 0.96:
            return Star.Type.G
        elif rnd <= 0.99:
            return Star.Type.F
        elif rnd <= 0.997:
            return Star.Type.A
        elif rnd <= 0.999999:
            return Star.Type.B
        else:
            return Star.Type.O

    def _generate_color(self, my_random: random.Random) -> tuple:

        base_color: tuple = None
        if self.type == Star.Type.M:
            base_color = (255, 96, 96)
        elif self.type == Star.Type.K:
            base_color = (255, 192, 128)
        elif self.type == Star.Type.G:
            base_color = (255, 255, 128)
        elif self.type == Star.Type.F:
            base_color = (255, 255, 224)
        elif self.type == Star.Type.A:
            base_color = (255, 255, 255)
        elif self.type == Star.Type.B:
            base_color = (192, 192, 255)
        elif self.type == Star.Type.O:
            base_color = (96, 96, 255)

        color_variation = (
            -16 + my_random.randint(0, 32),
            -16 + my_random.randint(0, 32),
            -16 + my_random.randint(0, 32)
        )

        result = tuple(max(0, min(255, b + v)) for b, v in zip(base_color, color_variation))
        return result

    def _generate_radius(self, my_random: random.Random) -> int:
        if self.type == Star.Type.M:
            radius = int(200000000 * (0.4 + 1.2 * my_random.random()))
        elif self.type == Star.Type.K:
            radius = int(550000000 * (0.9 + 0.2 * my_random.random()))
        elif self.type == Star.Type.G:
            radius = int(700000000 * (0.95 + 0.1 * my_random.random()))
        elif self.type == Star.Type.F:
            radius = int(880000000 * (0.9 + 0.2 * my_random.random()))
        elif self.type == Star.Type.A:
            radius = int(1300000000 * (0.75 + 0.5 * my_random.random()))
        elif self.type == Star.Type.B:
            radius = int(3500000000 * (0.85 + 0.3 * my_random.random()))
        elif self.type == Star.Type.O:
            radius = int(10500000000 * (0.3 + 0.6 * my_random.random()))
        return radius

    def _generate_mass(self, my_random: random.Random) -> int:

        # Typical masses per type (very approximate)
        typical_mass = {
            Star.Type.M: 0.3 * Star.SOLAR_MASS,
            Star.Type.K: 0.7 * Star.SOLAR_MASS,
            Star.Type.G: 1.0 * Star.SOLAR_MASS,
            Star.Type.F: 1.3 * Star.SOLAR_MASS,
            Star.Type.A: 2.0 * Star.SOLAR_MASS,
            Star.Type.B: 5.0 * Star.SOLAR_MASS,
            Star.Type.O: 20.0 * Star.SOLAR_MASS
        }.get(self.type, 1.0)

        return int(typical_mass * (0.98 + 0.04 * my_random.random()))

    def _generate_temperature(self, my_random: random.Random) -> float:
        """
        Estimate a realistic stellar effective temperature (Kelvin)
        using spectral type + mass + radius + random variation.
        """
        # Canonical average temperatures by spectral type
        base_temp = {
            Star.Type.M: 3500,
            Star.Type.K: 4800,
            Star.Type.G: 5800,
            Star.Type.F: 7000,
            Star.Type.A: 8500,
            Star.Type.B: 12000,
            Star.Type.O: 30000
        }.get(self.type, 6000)  # fallback to G-like

        # Combine corrections (mild influence)
        result = base_temp * (0.85 + 0.15 * self.mass / Star.SOLAR_MASS) * (0.9 + 0.1 * self.radius / Star.SOLAR_RADIUS)

        # Add random scatter (±8%)
        result *= my_random.uniform(0.92, 1.08)

        return result

    def _generate_rotation_period(self, my_random: random.Random) -> float:
        """
        Compute a realistic stellar rotation period (seconds)
        using temperature-based rotation regimes + randomness.
        """
        # Determine rotation velocity range from temperature
        if self.temperature < 4500:
            v_min, v_max = 1, 15  # km/s
        elif self.temperature < 6000:
            v_min, v_max = 2, 20
        elif self.temperature < 7000:
            v_min, v_max = 20, 100
        elif self.temperature < 10000:
            v_min, v_max = 100, 200
        elif self.temperature < 20000:
            v_min, v_max = 150, 300
        else:
            v_min, v_max = 200, 400

        # Random velocity inside the range
        v_eq_kms = my_random.uniform(v_min, v_max)
        v_eq = v_eq_kms * 1000  # convert to m/s

        # Compute rotation period
        period_seconds = (2 * math.pi * self.radius) / v_eq
        return period_seconds

    def _generate_heat_effect_distance(self, my_random: random.Random) -> int:
        factor: int = 100
        if self.type == Star.Type.M:
            factor = 48
        elif self.type == Star.Type.K:
            factor = 76
        elif self.type == Star.Type.G:
            factor = 100
        elif self.type == Star.Type.F:
            factor = 140
        elif self.type == Star.Type.A:
            factor = 300
        elif self.type == Star.Type.B:
            factor = 700
        elif self.type == Star.Type.O:
            factor = 7500

        return int(self.radius * factor * (0.9 + 0.2 * my_random.random()))

    def _generate_heat_death_distance(self, my_random: random.Random) -> int:
        factor: int = 10
        if self.type == Star.Type.M:
            factor = 4.6
        elif self.type == Star.Type.K:
            factor = 7.5
        elif self.type == Star.Type.G:
            factor = 10
        elif self.type == Star.Type.F:
            factor = 14
        elif self.type == Star.Type.A:
            factor = 30
        elif self.type == Star.Type.B:
            factor = 70
        elif self.type == Star.Type.O:
            factor = 750

        return int(self.radius * factor * (0.9 + 0.2 * my_random.random()))

    def almanack(self) -> str:
        '''Markdown almanack of the star: its astronomical data. The luminosity and gravity are estimated from the
        radius, mass and temperature.'''
        AU: float = 1.496e11  # m
        GRAVITATIONAL_CONSTANT: float = 6.674e-11  # m^3 kg^-1 s^-2
        SUN_TEMPERATURE: float = 5772.0  # K, the Sun's effective temperature
        luminosity: float = (self.radius / Star.SOLAR_RADIUS) ** 2 * (self.temperature / SUN_TEMPERATURE) ** 4
        gravity: float = GRAVITATIONAL_CONSTANT * self.mass / self.radius ** 2
        equatorial_speed: float = 2 * math.pi * self.radius / self.rotation_period
        return (
            f"### Star {self.name}\n"
            f"* Type: {self.type.value}\n"
            f"* Seed: {self.seed}\n"
            f"* Effective temperature: {self.temperature:.0f} K\n"
            f"* Mass: {self.mass / Star.SOLAR_MASS:.3f} solar masses\n"
            f"* Radius: {self.radius / Star.SOLAR_RADIUS:.3f} solar radii ({int(self.radius / 1000)} Km)\n"
            f"* Surface gravity: {gravity:.1f} m/s²\n"
            f"* Luminosity: {luminosity:.3g} solar luminosities\n"
            f"* Rotation period: {self.rotation_period / (60 * 60):.2f} hours, equatorial speed {equatorial_speed / 1000:.1f} Km/s\n"
            f"* Heat radius: {self.heat_radius / AU:.3f} AU, death radius: {self.death_radius / AU:.4f} AU\n"
            f"\n"
            )

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @property
    def stellar_system(self) -> StellarSystem:
        return self._system
