"""The star of a stellar system, as a body ships can navigate to."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
import math
import random
from typing import TYPE_CHECKING, Optional

from common.vector3 import Vector3
from galaxies.body import Body
from galaxies.constants import ABSOLUTE_MAGNITUDE_DISTANCE_LY, LIGHT_YEAR_M, STAR_COLOUR_VIVIDNESS

if TYPE_CHECKING:
    from galaxies.stellar_system import StellarSystem


def cell_of(position: tuple[float, float, float]) -> tuple[int, int, int]:
    """The integer cell (1 ly) that contains a galactic position. A star's cell is its key in the galaxy."""
    return (math.floor(position[0]), math.floor(position[1]), math.floor(position[2]))


def blackbody_rgb(temperature: float) -> tuple:
    """The RGB colour of a blackbody at the temperature (K), from the standard curve fit (Tanner Helland's), clamped
    to the range the fit is good for. Plain colour: no vividness applied (see _vivid)."""
    t = min(max(temperature, 1000.0), 40000.0) / 100.0
    red = 255.0 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    green = (99.4708025861 * math.log(t) - 161.1195681661 if t <= 66
             else 288.1221695283 * (t - 60) ** -0.0755148492)
    if t >= 66:
        blue = 255.0
    elif t <= 19:
        blue = 0.0
    else:
        blue = 138.5177312231 * math.log(t - 10) - 305.0447927307
    return tuple(round(min(max(c, 0.0), 255.0)) for c in (red, green, blue))


def _vivid(colour: tuple, factor: float) -> tuple:
    """The colour pushed away from its mean grey by factor (1.0 leaves it as it is), kept within 0 to 255."""
    grey = sum(colour) / 3
    return tuple(round(min(max(grey + (c - grey) * factor, 0.0), 255.0)) for c in colour)


class Star(Body):
    """The star: the origin of the stellar frame, at rest. It has no surface: nothing binds to it.

    Everything about the star is generated from its seed alone; the galactic position (in ly) is only stored. The star
    belongs to a stellar system once `attach_to` is called, which is what `stellar_system` returns.

    Its type sets the range of its mass. The mass sets the radius and the luminosity, by the main-sequence fits of
    `_generate_radius` and `_generate_luminosity`, and the luminosity and the radius set the temperature
    (Stefan-Boltzmann), so the four always agree. The heat distances are where the light has the fluxes HEAT_FLUX and
    DEATH_FLUX.
    """

    BOLOMETRIC_ZERO_POINT = 3.0128e28  # W: the luminosity of magnitude 0 (IAU 2015 nominal zero point)
    STEFAN_BOLTZMANN = 5.670e-8  # W m^-2 K^-4

    # The fits are normalised to a reference star (SI values).
    REFERENCE_MASS = 1.989e30  # kg
    REFERENCE_RADIUS = 6.957e8  # m
    REFERENCE_LUMINOSITY = 3.828e26  # W
    HEAT_FLUX = 6.3e3  # W m^-2: where the ship starts to heat up (the light at a heat radius)
    DEATH_FLUX = 6.3e5  # W m^-2: where the ship reaches its maximum temperature (the light at a death radius)

    class Type(Enum):
        M = "Red dwarf (M)"
        K = "Orange-ish (K)"
        G = "Yellow star (G)"
        F = "Yellow-white (F)"
        A = "White (A)"
        B = "Blue (B)"
        O = "Blue giant (O)"  # noqa: E741

    # The mass range of each type (kg), drawn uniformly. They follow the spectral classes' masses.
    MASS_RANGES = {
        Type.M: (2.0e29, 1.0e30),
        Type.K: (1.0e30, 1.6e30),
        Type.G: (1.6e30, 2.07e30),
        Type.F: (2.07e30, 2.79e30),
        Type.A: (2.79e30, 4.18e30),
        Type.B: (4.18e30, 3.18e31),
        Type.O: (3.18e31, 1.8e32),
    }

    is_world = False

    # region Generation
    def __init__(self, seed: int, position: tuple[float, float, float], star_type: Optional[Star.Type] = None) -> None:
        """`star_type` forces the type (the seed's type is still drawn, so the other values do not change)."""
        self.seed: int = seed
        self.position: tuple[float, float, float] = position  # galactic coordinates, in ly
        self._system: Optional[StellarSystem] = None
        my_random: random.Random = random.Random(self.seed)
        self.name: str = Star._generate_name(my_random)
        self.type: Star.Type = Star._generate_type(my_random)
        if star_type is not None:
            self.type = star_type
        self.mass: float = self._generate_mass(my_random)
        self.radius: int = self._generate_radius()
        self.luminosity: float = self._generate_luminosity()  # W
        self.temperature: float = self._generate_temperature()
        self.color: tuple = self._generate_color()  # after the temperature, which it depends on
        self.rotation_period: float = self._generate_rotation_period(my_random)
        self.default_heat_radius: int = self._generate_heat_radius(my_random)
        self.default_death_radius: int = self._generate_death_radius(my_random)

    @staticmethod
    def _generate_name(my_random: random.Random) -> str:
        """Generate a random name for the star."""
        vocals = "aeiouaeio"  # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for _ in range(1, my_random.randint(3, 6)):
            if my_random.random() < 0.4:
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if my_random.random() < 0.4:
                name += my_random.choice(consonants)

        name = name.replace("q", "qu")

        if my_random.random() < 0.5:
            name += "eia"

        return name.capitalize()

    @staticmethod
    def _generate_type(my_random: random.Random) -> Star.Type:
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

    def _generate_mass(self, my_random: random.Random) -> float:
        """The mass (kg), drawn within the range of the star's type."""
        low, high = Star.MASS_RANGES[self.type]
        return my_random.uniform(low, high)

    def _generate_radius(self) -> int:
        """The radius (m) of a main-sequence star of its mass: R = M^0.88 below the reference mass, M^0.8 above it."""
        ratio: float = self.mass / Star.REFERENCE_MASS
        exponent: float = 0.88 if ratio < 1.0 else 0.8
        return int(Star.REFERENCE_RADIUS * ratio ** exponent)

    def _generate_luminosity(self) -> float:
        """The luminosity (W) of a main-sequence star of its mass: L = 0.23 M^2.3 for the faintest, M^4 up to 16
        reference masses, and M^2.5 beyond (the mass-luminosity fits)."""
        ratio: float = self.mass / Star.REFERENCE_MASS
        if ratio < 0.43:
            factor: float = 0.23 * ratio ** 2.3
        elif ratio <= 16.0:
            factor = ratio ** 4
        else:
            factor = 16.0 ** 4 * (ratio / 16.0) ** 2.5
        return factor * Star.REFERENCE_LUMINOSITY

    def _generate_temperature(self) -> float:
        """The effective temperature (K), from the luminosity and the radius (Stefan-Boltzmann law)."""
        return (self.luminosity / (4 * math.pi * self.radius ** 2 * Star.STEFAN_BOLTZMANN)) ** 0.25

    def _generate_color(self) -> tuple:
        """The blackbody colour at the star's temperature, made more vivid by STAR_COLOUR_VIVIDNESS."""
        return _vivid(blackbody_rgb(self.temperature), STAR_COLOUR_VIVIDNESS)

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

    def _generate_heat_radius(self, my_random: random.Random) -> int:
        """The distance at which the ship starts to heat up: where the light is HEAT_FLUX, with a little spread."""
        return int(self.distance_at_flux(Star.HEAT_FLUX) * (0.9 + 0.2 * my_random.random()))

    def _generate_death_radius(self, my_random: random.Random) -> int:
        """The distance of the ship's maximum temperature: where the light is DEATH_FLUX, with a little spread."""
        return int(self.distance_at_flux(Star.DEATH_FLUX) * (0.9 + 0.2 * my_random.random()))
    # endregion

    # region Light
    def distance_at_flux(self, flux: float) -> float:
        """The distance (m) from the star at which its light is `flux` W/m^2."""
        return math.sqrt(self.luminosity / (4 * math.pi * flux))

    @property
    def absolute_magnitude(self) -> float:
        """How bright the star is at the reference distance (ABSOLUTE_MAGNITUDE_DISTANCE_LY); lower is brighter."""
        return -2.5 * math.log10(self.luminosity / Star.BOLOMETRIC_ZERO_POINT)

    def apparent_magnitude(self, distance_m: float) -> float:
        """How bright the star looks from distance_m meters away; lower is brighter."""
        distance_ly = distance_m / LIGHT_YEAR_M
        return self.absolute_magnitude + 5 * math.log10(distance_ly / ABSOLUTE_MAGNITUDE_DISTANCE_LY)
    # endregion

    # region Body
    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @property
    def cell(self) -> tuple[int, int, int]:
        """The integer cell that contains the star: its key in the galaxy."""
        return cell_of(self.position)

    def attach_to(self, system: StellarSystem) -> None:
        """Make `system` the star's stellar system (what `stellar_system` returns)."""
        self._system = system

    @property
    def stellar_system(self) -> StellarSystem:
        return self._system
    # endregion

    # region Almanack
    def markdown(self) -> str:
        '''Markdown of the star: its astronomical data. The luminosity and gravity are estimated from the
        radius, mass and temperature.'''
        GRAVITATIONAL_CONSTANT: float = 6.674e-11  # m^3 kg^-1 s^-2
        gravity: float = GRAVITATIONAL_CONSTANT * self.mass / self.radius ** 2
        equatorial_speed: float = 2 * math.pi * self.radius / self.rotation_period
        return (
            f"### Star {self.name}\n"
            f"* Type: {self.type.value}\n"
            f"* Effective temperature: {self.temperature:.0f} K\n"
            f"* Mass: {self.mass:.3e} kg\n"
            f"* Radius: {self.radius:.3e} m ({int(self.radius / 1000)} Km)\n"
            f"* Surface gravity: {gravity:.1f} m/s²\n"
            f"* Luminosity: {self.luminosity:.3e} W\n"
            f"* Rotation period: {self.rotation_period / (60 * 60):.2f} hours, equatorial speed "
            f"{equatorial_speed / 1000:.1f} Km/s\n"
            f"\n"
            )
    # endregion
