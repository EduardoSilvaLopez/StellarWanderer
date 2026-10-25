from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Tuple

import logging
from galaxies import seeds
from galaxies.world import World
from galaxies.world_surface import Colour, equilibrium_temperature, vary_colour

if TYPE_CHECKING:
    from galaxies.orbit import Orbit
    from galaxies.star import Star

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GiantTraits:
    """What sets a class of giant apart: the ranges its values are drawn from. SI, but for the colours."""
    label: str
    mass: Tuple[float, float, float, float]  # kg: median, sigma of its logarithm, lowest, highest
    spin_period: Tuple[float, float]  # s: median, sigma of its logarithm
    inertia_factor: Tuple[float, float]  # lowest, highest: moment of inertia in m R^2
    bond_albedo: Tuple[float, float]  # lowest, highest
    internal_temperature: Tuple[float, float, float]  # K: at the mass of Jupiter, sigma of its logarithm, highest
    one_bar_factor: float  # the temperature at 1 bar, in effective temperatures
    helium: Tuple[float, float]  # mole fraction: mean, sigma
    methane: Tuple[float, float]  # mole fraction: lowest, highest
    clouds: Tuple[Colour, ...]  # the colours of the cloud tops, before the variation (see world_surface.vary_colour)


class GiantClass(Enum):
    """The two kinds of giant. They are told apart only when they are generated and in the almanack: a `JovianWorld` of
    either is the same to the rest of the game."""
    GAS = GiantTraits(
        label='Gas giant', mass=(1.0e27, 0.9, 2.5e26, 2.5e28), spin_period=(37800.0, 0.2), inertia_factor=(0.20, 0.26),
        bond_albedo=(0.30, 0.50), internal_temperature=(100.0, 0.15, 1000.0), one_bar_factor=1.33,
        helium=(0.136, 0.010), methane=(0.002, 0.006),
        clouds=((205, 175, 135), (196, 150, 108), (214, 196, 150), (176, 120, 92), (210, 205, 190)),
    )
    ICE = GiantTraits(
        label='Ice giant', mass=(1.0e26, 0.3, 4.0e25, 2.5e26), spin_period=(59400.0, 0.15), inertia_factor=(0.22, 0.24),
        bond_albedo=(0.28, 0.36), internal_temperature=(100.0, 0.6, 60.0), one_bar_factor=1.25,
        helium=(0.152, 0.010), methane=(0.015, 0.040),
        clouds=((172, 216, 226), (92, 130, 205), (120, 190, 200), (110, 170, 170)),
    )

    @property
    def traits(self) -> GiantTraits:
        return self.value


class JovianWorld(World):
    '''A giant planet: no surface, no ground, all atmosphere. It is a gas giant (mostly hydrogen and helium) or an ice
    giant (a smaller envelope over a deep fluid of water, ammonia and methane), see `GiantClass`. The class is drawn
    from the temperature of the orbit: the colder, the likelier an ice giant, as the outer giants of the Solar System.
    Moons, rings and outposts are not generated yet.

    Size and spin. The mass is drawn log-normally within the range of its class. The radius, the mean one (of a sphere
    of the same volume), follows from the mass: it grows with it up to about the mass of Saturn, as the small giants do,
    and then falls very slowly, as the large ones are compressed (`_radius_of_mass`), with a little scatter
    (RADIUS_SIGMA). The spin is drawn (never close to the breakup spin) and flattens the planet: the flattening is the
    Darwin-Radau one, from the spin and the moment of inertia (`inertia_factor`), so `equatorial_radius` and
    `polar_radius` follow. Clairaut's theorem gives the gravity at the 1 bar level, `gravity_equator` and
    `gravity_pole`. The giants are far from their star, so the tides never tie their spin. The axial tilt is the
    orbit's inclination (see World); it is wider than the rocky planets', and now and then it is extreme.

    Temperature. The equilibrium temperature `equilibrium_temperature` takes the albedo of the clouds. A giant also
    radiates the heat of its interior, `internal_temperature` (it grows with the mass): the effective temperature is the
    fourth root of the sum of their fourth powers, the 1 bar level is warmer than that by the class's `one_bar_factor`,
    and the stratosphere is at the effective temperature.

    Atmosphere. It is an ideal gas of hydrogen, helium and methane (`helium`, `methane`, mole fractions), in
    hydrostatic balance in a gravity that falls with the square of the distance from the centre. Below the tropopause
    the temperature follows the dry adiabat; above it the atmosphere is isothermal. Both have a closed form, so
    `atmosphere_at` and `altitude_of_pressure` cost a handful of operations. The 1 bar level is the altitude zero; the
    altitude is measured from it, along the radius, and the level is an ellipse, so a latitude is needed. The model is
    an ideal gas: it is meant for the range the ship can survive, and below it the pressure is only a number that is
    large. The edge of the atmosphere, `ATMOSPHERE_EDGE_PRESSURE`, is where it starts to matter to a ship.
    '''

    GAS_CONSTANT = 8.314  # J mol^-1 K^-1
    ONE_BAR = 1.0e5  # Pa

    # The size law: R = RADIUS_ANCHOR * (M / MASS_ANCHOR) ^ exponent; the radius is the lesser of the two (they cross
    # at about 8.4e26 kg). The first law is drawn through a small giant and Saturn, the second through Jupiter.
    SMALL_ANCHOR = (1.024e26, 2.4622e7)  # kg, m
    SMALL_EXPONENT = 0.518
    LARGE_ANCHOR = (1.898e27, 6.9911e7)  # kg, m
    LARGE_EXPONENT = -0.04
    RADIUS_SIGMA = 0.04  # of the logarithm of the radius

    MIN_SPIN_BREAKUP_PERIODS = 2.5  # the spin is at least this many times slower than the breakup spin

    # Ice giants are likelier where it is cold: the odds are 1 / (1 + exp((T - ICE_TEMPERATURE_MIDPOINT) / WIDTH)), T
    # being the equilibrium temperature of an airless world (World.equilibrium_temperature of a rocky one).
    ICE_TEMPERATURE_MIDPOINT = 85.0  # K
    ICE_TEMPERATURE_WIDTH = 12.0  # K
    INTERNAL_MASS_EXPONENT = 0.4  # the heat of the interior grows with this power of the mass

    # Orbit tilt: |N(0, sigma)|, capped, but now and then an extreme one.
    INCLINATION_SIGMA_DEGREES = 20.0
    MAX_INCLINATION_DEGREES = 45.0
    EXTREME_TILT_CHANCE = 0.1
    EXTREME_TILT_DEGREES = (60.0, 100.0)

    # The atmosphere: the molar masses (kg/mol) and the specific heat at constant pressure (in gas constants per mole)
    # of its gases.
    HYDROGEN = (2.016e-3, 3.5)
    HELIUM = (4.0026e-3, 2.5)
    METHANE = (16.043e-3, 4.0)
    ATMOSPHERE_EDGE_PRESSURE = 1.0e-4  # Pa: where the atmosphere is said to end
    MIN_RADIUS_FRACTION = 0.3  # the model stops this deep, in radii of the 1 bar level

    def __init__(self, parent_orbit: Orbit) -> None:
        super().__init__()
        self.parent_orbit = parent_orbit
        self.index = len(parent_orbit.planets)
        self.seed = seeds.derive(parent_orbit.seed, 'planet', self.index)
        my_random = random.Random(self.seed)
        star = self.stellar_system.star

        self.name = self._generate_planet_name(my_random)
        self.distance_to_parent = int(parent_orbit.distance_from_star)

        airless_temperature = equilibrium_temperature(star, self.distance_to_parent)
        ice_odds = 1.0 / (1.0 + math.exp((airless_temperature - JovianWorld.ICE_TEMPERATURE_MIDPOINT)
                                         / JovianWorld.ICE_TEMPERATURE_WIDTH))
        self.giant_class: GiantClass = GiantClass.ICE if my_random.random() < ice_odds else GiantClass.GAS
        traits = self.giant_class.traits

        median, sigma, lowest, highest = traits.mass
        self.mass = min(highest, max(lowest, math.exp(my_random.gauss(math.log(median), sigma))))
        self.radius = self._radius_of_mass(self.mass) * math.exp(my_random.gauss(0.0, JovianWorld.RADIUS_SIGMA))
        gravitational_parameter = World.GRAVITATIONAL_CONSTANT * self.mass

        self.initial_degrees_in_orbit = my_random.random() * 360.0
        self.orbital_period = math.tau * math.sqrt(
            self.distance_to_parent ** 3 / (World.GRAVITATIONAL_CONSTANT * (star.mass + self.mass)))

        median, sigma = traits.spin_period
        breakup_period = math.tau * math.sqrt(self.radius ** 3 / gravitational_parameter)
        self.rotation_period = max(math.exp(my_random.gauss(math.log(median), sigma)),
                                   JovianWorld.MIN_SPIN_BREAKUP_PERIODS * breakup_period)
        self.inertia_factor: float = my_random.uniform(*traits.inertia_factor)
        self._shape_by_spin(gravitational_parameter)

        self.bond_albedo: float = my_random.uniform(*traits.bond_albedo)
        reference, sigma, highest = traits.internal_temperature
        self.internal_temperature: float = min(highest, reference * math.exp(my_random.gauss(0.0, sigma))
                                               * (self.mass / JovianWorld.LARGE_ANCHOR[0])
                                               ** JovianWorld.INTERNAL_MASS_EXPONENT)
        self.helium: float = min(0.3, max(0.0, my_random.gauss(*traits.helium)))
        self.methane: float = my_random.uniform(*traits.methane)

        self._generate_orbit_orientation(my_random, JovianWorld.INCLINATION_SIGMA_DEGREES,
                                         JovianWorld.MAX_INCLINATION_DEGREES)
        if my_random.random() < JovianWorld.EXTREME_TILT_CHANCE:
            self.inclination = math.radians(my_random.uniform(*JovianWorld.EXTREME_TILT_DEGREES))
            self._set_orbit_axes()

        self.surface_colour = vary_colour(my_random, my_random.choice(traits.clouds))
        self._generate_atmosphere(star, traits)

        self._learn()
        self._log_creation()

    # region Generation
    @staticmethod
    def _radius_of_mass(mass: float) -> float:
        """The mean radius (m) of a giant of the mass (kg), before the scatter: the lesser of the two laws."""
        small_mass, small_radius = JovianWorld.SMALL_ANCHOR
        large_mass, large_radius = JovianWorld.LARGE_ANCHOR
        return min(small_radius * (mass / small_mass) ** JovianWorld.SMALL_EXPONENT,
                   large_radius * (mass / large_mass) ** JovianWorld.LARGE_EXPONENT)

    def _shape_by_spin(self, gravitational_parameter: float) -> None:
        """The flattening (Darwin-Radau, solved by iteration: the spin parameter depends on the equatorial radius, and
        that on the flattening), the radii, and Clairaut's gravity at the 1 bar level."""
        spin = math.tau / self.rotation_period
        flattening = 0.0
        for _ in range(8):
            spin_parameter = spin ** 2 * self.radius ** 3 / (gravitational_parameter * (1.0 - flattening))
            flattening = 2.5 * spin_parameter / (1.0 + 6.25 * (1.0 - 1.5 * self.inertia_factor) ** 2)
        self.flattening: float = flattening
        self.equatorial_radius: float = self.radius / (1.0 - flattening) ** (1.0 / 3.0)
        self.polar_radius: float = self.equatorial_radius * (1.0 - flattening)
        spin_parameter = spin ** 2 * self.equatorial_radius ** 3 / gravitational_parameter
        self.gravity_equator: float = gravitational_parameter / self.equatorial_radius ** 2 \
            - spin ** 2 * self.equatorial_radius
        self.gravity_pole: float = self.gravity_equator * (1.0 + 2.5 * spin_parameter - flattening)

    def _generate_atmosphere(self, star: Star, traits: GiantTraits) -> None:
        """The temperatures and the gas: the numbers `atmosphere_at` needs."""
        self.equilibrium_temperature = equilibrium_temperature(star, self.distance_to_parent, self.bond_albedo)
        self.effective_temperature: float = (self.equilibrium_temperature ** 4 + self.internal_temperature ** 4) ** 0.25
        self.temperature_one_bar: float = traits.one_bar_factor * self.effective_temperature
        self.temperature_stratosphere: float = self.effective_temperature

        hydrogen = 1.0 - self.helium - self.methane
        self.hydrogen: float = hydrogen
        self.mean_molecular_weight: float = (
            hydrogen * JovianWorld.HYDROGEN[0] + self.helium * JovianWorld.HELIUM[0]
            + self.methane * JovianWorld.METHANE[0])
        specific_heat_in_gas_constants = (
            hydrogen * JovianWorld.HYDROGEN[1] + self.helium * JovianWorld.HELIUM[1]
            + self.methane * JovianWorld.METHANE[1])
        self.specific_gas_constant: float = JovianWorld.GAS_CONSTANT / self.mean_molecular_weight
        self.specific_heat: float = specific_heat_in_gas_constants * self.specific_gas_constant
        self.adiabatic_exponent: float = 1.0 / specific_heat_in_gas_constants  # R / cp
    # endregion

    # region Atmosphere
    def one_bar_radius(self, latitude_angle: float) -> float:
        """The distance (m) from the centre to the 1 bar level, at the latitude (radians, from the equator): the
        ellipse of the equatorial and polar radii."""
        return self.equatorial_radius * self.polar_radius / math.hypot(
            self.polar_radius * math.cos(latitude_angle), self.equatorial_radius * math.sin(latitude_angle))

    def _level(self, latitude_angle: float) -> Tuple[float, float, float]:
        """The 1 bar level at the latitude: its distance from the centre, the gravitational parameter that reproduces
        its gravity (Clairaut: the pull grows towards the pole) with the pull falling as the square of the distance,
        and the inverse of the distance of the tropopause (where the adiabat reaches the stratosphere's temperature)."""
        radius = self.one_bar_radius(latitude_angle)
        gravity = self.gravity_equator * (1.0 + (self.gravity_pole / self.gravity_equator - 1.0)
                                          * math.sin(latitude_angle) ** 2)
        gravitational_parameter = gravity * radius ** 2
        tropopause = 1.0 / radius - self.specific_heat * (
            self.temperature_one_bar - self.temperature_stratosphere) / gravitational_parameter
        return radius, gravitational_parameter, tropopause

    def atmosphere_at(self, altitude: float, latitude_angle: float) -> Tuple[float, float]:
        """The pressure (Pa) and the temperature (K) at the altitude (m above the 1 bar level, along the radius,
        negative below it) and the latitude (radians, from the equator). Below the model's depth (MIN_RADIUS_FRACTION)
        it gives the values of that depth."""
        radius, gravitational_parameter, tropopause = self._level(latitude_angle)
        inverse_distance = 1.0 / max(radius + altitude, JovianWorld.MIN_RADIUS_FRACTION * radius)
        if inverse_distance >= tropopause:
            temperature = self.temperature_one_bar + gravitational_parameter / self.specific_heat * (
                inverse_distance - 1.0 / radius)
            pressure = JovianWorld.ONE_BAR * (temperature / self.temperature_one_bar) ** (1.0 / self.adiabatic_exponent)
            return pressure, temperature
        tropopause_pressure = self._tropopause_pressure()
        pressure = tropopause_pressure * math.exp(-gravitational_parameter / (
            self.specific_gas_constant * self.temperature_stratosphere) * (tropopause - inverse_distance))
        return pressure, self.temperature_stratosphere

    def altitude_of_pressure(self, pressure: float, latitude_angle: float) -> float:
        """The altitude (m above the 1 bar level) where the pressure (Pa) is that, at the latitude (radians, from the
        equator): the inverse of `atmosphere_at`. Infinite if the isothermal layer never gets down to that pressure."""
        radius, gravitational_parameter, tropopause = self._level(latitude_angle)
        tropopause_pressure = self._tropopause_pressure()
        if pressure >= tropopause_pressure:
            temperature = self.temperature_one_bar * (pressure / JovianWorld.ONE_BAR) ** self.adiabatic_exponent
            inverse_distance = 1.0 / radius + self.specific_heat * (temperature - self.temperature_one_bar) \
                / gravitational_parameter
        else:
            inverse_distance = tropopause - self.specific_gas_constant * self.temperature_stratosphere \
                / gravitational_parameter * math.log(tropopause_pressure / pressure)
            if inverse_distance <= 0.0:
                return math.inf
        return 1.0 / inverse_distance - radius

    def _tropopause_pressure(self) -> float:
        return JovianWorld.ONE_BAR * (self.temperature_stratosphere / self.temperature_one_bar) \
            ** (1.0 / self.adiabatic_exponent)
    # endregion

    # region Almanack and log
    def markdown(self) -> str:
        '''Markdown of this world.'''
        AU: float = 1.496e11
        jupiter_mass: float = JovianWorld.LARGE_ANCHOR[0]
        edge: float = self.altitude_of_pressure(JovianWorld.ATMOSPHERE_EDGE_PRESSURE, 0.0)
        return (
            f"### {self.giant_class.traits.label} {self.name}\n"
            f"* Distance from the star: {self.distance_to_parent / AU:.2f} AU\n"
            f"* Year: {self.orbital_period / (365.2425 * 24 * 60 * 60):.2f} Earth years\n"
            f"* Eccentricity: {self.eccentricity:.3f}\n"
            f"* Inclination: {math.degrees(self.inclination):.1f}°\n"
            f"* Mass: {self.mass / jupiter_mass:.2f} Jupiter masses\n"
            f"* Equatorial radius: {int(self.equatorial_radius / 1000)} Km\n"
            f"* Flattening: {self.flattening:.3f}\n"
            f"* Gravity at the clouds: {self.gravity_equator:.1f} m/s² at the equator, "
            f"{self.gravity_pole:.1f} m/s² at the poles\n"
            f"* Day: {self.rotation_period / (60 * 60):.2f} hours\n"
            f"* Temperature at the clouds (1 bar): {self.temperature_one_bar - 273.15:.0f} °C\n"
            f"* Atmosphere: {100 * self.hydrogen:.1f}% hydrogen, {100 * self.helium:.1f}% helium, "
            f"{100 * self.methane:.1f}% methane\n"
            f"* Mean molecular weight: {1000 * self.mean_molecular_weight:.2f} g/mol\n"
            f"* The atmosphere thins out {int(edge / 1000)} Km above the clouds\n"
            f"\n"
        )

    def _log_creation(self) -> JovianWorld:
        logger.info("NEW JOVIAN PLANET CREATED")
        logger.info(f" - Orbit(Index): {int(self.parent_orbit.number)} ({self.index})")
        logger.info(f" - Name: {self.name}, Seed: {self.seed}")
        logger.info(f" - Class: {self.giant_class.traits.label}")
        logger.info(f" - Distance to parent: {f'{int(self.distance_to_parent):,}'}")
        logger.info(f" - Mass: {self.mass:.4g} kg, mean radius: {f'{int(self.radius):,}'}, "
                    f"flattening {self.flattening:.4f}")
        logger.info(f" - Spin: rotation period {self.rotation_period:.3g} s, "
                    f"tilt {math.degrees(self.inclination):.1f}°")
        logger.info(f" - Temperature: {self.equilibrium_temperature:.0f} K in equilibrium, "
                    f"{self.internal_temperature:.0f} K internal, {self.temperature_one_bar:.0f} K at 1 bar")
        logger.info(f" - Atmosphere: molecular weight {1000 * self.mean_molecular_weight:.3f} g/mol")
        return self
    # endregion
