from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

import logging
from galaxies import seeds
from galaxies.rocky_world import RockyWorld
from galaxies.world import World
from galaxies.world_surface import Colour, equilibrium_temperature, vary_colour

if TYPE_CHECKING:
    from common.vector3 import Vector3
    from galaxies.orbit import Orbit
    from galaxies.star import Star

logger = logging.getLogger(__name__)


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


@dataclass(frozen=True)
class Ring:
    """A ring of a giant, in its equatorial plane: from `inner` to `outer` metres from its centre, with the optical depth
    of its material at evenly spaced radii (`opacity`, from the inner edge out), its colour (0 to 1 per channel, lit by the
    star as white) and its kind (a key of JovianWorld.RING_KINDS). Cosmetic: no mass, no pull, nothing saved."""
    inner: float
    outer: float
    opacity: Tuple[float, ...]
    colour: Tuple[float, float, float]
    kind: str


@dataclass(frozen=True)
class Storm:
    """A vortex in the clouds of a giant at a date: where (latitude and longitude on the planet, rad), how wide (m), how
    it turns (`twist`, rad at its centre: its sign is the sense of the turn), how strong it is (0 to 1: it grows when it
    is born and fades before it dies), and how often it flashes (per second). `key` tells it from the others."""
    key: int
    latitude: float
    longitude: float
    radius: float
    twist: float
    strength: float
    lightning_rate: float


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
    bands: Tuple[float, float]  # cloud bands from pole to pole: lowest, highest
    band_contrast: Tuple[float, float]  # lowest, highest: how much the bands darken and brighten the cloud tops
    wind: Tuple[float, float]  # m/s: lowest, highest speed of the fastest zonal jet
    storm_colour: Tuple[float, float, float]  # what the clouds of a storm are multiplied by: a warm red, a cold dark
    great_storm_chance: float  # that the giant has a storm that never dies


class GiantClass(Enum):
    """The two kinds of giant. They are told apart only when they are generated and in the almanack: a `JovianWorld` of
    either is the same to the rest of the game."""
    GAS = GiantTraits(
        label='Gas giant', mass=(1.0e27, 0.9, 2.5e26, 2.5e28), spin_period=(37800.0, 0.2), inertia_factor=(0.20, 0.26),
        bond_albedo=(0.30, 0.50), internal_temperature=(100.0, 0.15, 1000.0), one_bar_factor=1.33,
        helium=(0.136, 0.010), methane=(0.002, 0.006),
        clouds=((205, 175, 135), (196, 150, 108), (214, 196, 150), (176, 120, 92), (210, 205, 190)),
        bands=(6.0, 12.0), band_contrast=(0.15, 0.35), wind=(60.0, 300.0),
        storm_colour=(1.05, 0.78, 0.7), great_storm_chance=0.5,
    )
    ICE = GiantTraits(
        label='Ice giant', mass=(1.0e26, 0.3, 4.0e25, 2.5e26), spin_period=(59400.0, 0.15), inertia_factor=(0.22, 0.24),
        bond_albedo=(0.28, 0.36), internal_temperature=(100.0, 0.6, 60.0), one_bar_factor=1.25,
        helium=(0.152, 0.010), methane=(0.015, 0.040),
        clouds=((172, 216, 226), (92, 130, 205), (120, 190, 200), (110, 170, 170)),
        bands=(3.0, 6.0), band_contrast=(0.05, 0.12), wind=(40.0, 250.0),
        storm_colour=(0.62, 0.76, 1.0), great_storm_chance=0.3,
    )

    @property
    def traits(self) -> GiantTraits:
        return self.value


class JovianWorld(World):
    '''A giant planet: no surface, no ground, all atmosphere. It is a gas giant (mostly hydrogen and helium) or an ice
    giant (a smaller envelope over a deep fluid of water, ammonia and methane), see `GiantClass`. The class is drawn
    from the temperature of the orbit: the colder, the likelier an ice giant, as the outer giants of the Solar System.
    Its moons are generated largest first (`_generate_moons`), each a `RockyWorld`. Some have rings (`_generate_rings`),
    cosmetic only: they interact with nothing.

    Size and spin. The mass is drawn log-normally within the range of its class. The radius, the mean one (of a sphere
    of the same volume), follows from the mass: it grows with it up to about the mass of Saturn, as the small giants do,
    and then falls very slowly, as the large ones are compressed (`_radius_of_mass`), with a little scatter
    (RADIUS_SIGMA). The spin is drawn (never close to the breakup spin) and flattens the planet: the flattening is the
    Darwin-Radau one, from the spin and the moment of inertia (`inertia_factor`), so `equatorial_radius` and
    `polar_radius` follow, and so does the mean `density`. Clairaut's theorem gives the gravity felt at the 1 bar
    level, `gravity_equator` and `gravity_pole`; the "surface gravity" astronomy quotes is `reference_gravity`.
    The giants are far from their star, so the tides never tie their spin. The axial tilt is the orbit's inclination
    (see World); it is wider than the rocky planets', and now and then it is extreme.

    Look. The sphere is an oblate ellipsoid (`flattening`, about the spin axis). Its cloud tops have bands by latitude
    (`band_count`, `band_phase`, `band_contrast`), and jets between the bands (`wind_speed`) that carry the clouds
    eastward or westward by turns (`cloud_state`), storms that are born, drift with the jets and die (`storms`), lightning that flashes in bursts, mostly in them (`lightning`), and a
    haze above them that thins with `scale_height`. A giant has no
    surface, so none of this is ground: the gas takes light out in proportion to its density (`optical_profile`), the
    cloud tops are where it gets opaque, and a ship that dives sees less light and less distance, until all is dark.
    Inside the planet the pull is that of the mass within (`pull_at`), which falls to zero at the centre, where the
    ship can go.

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

    # The moons (see _generate_moons). The expected number above MOON_REFERENCE_RADIUS is MOONS_ABOVE_REFERENCE for the
    # mass of Jupiter, growing with the power MOON_COUNT_MASS_EXPONENT of the mass, and the number above a radius falls
    # as the power -MOON_SIZE_EXPONENT of it. The reference sets the size of every moon, so it never changes;
    # MOON_MIN_RADIUS only says where the list stops, and it may be lowered: the larger moons stay as they are.
    MOON_REFERENCE_RADIUS = 300000.0  # m
    MOONS_ABOVE_REFERENCE = 5.0
    MOON_COUNT_MASS_EXPONENT = 0.5
    MOON_SIZE_EXPONENT = 2.0
    MOON_MIN_RADIUS = 300000.0  # m, not below WORLD_MIN_RADIUS: a moon that small is a rock
    MOON_MAX_RADIUS_FRACTION = 0.1  # of the giant's mean radius

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
    # How much of the light the gas takes out: the extinction of a kilogram of it per square metre it spreads over. The
    # optical depth of a column is this times its mass (the pressure over the gravity). It is set so that the clouds
    # are opaque at about the 1 bar level, which is what makes the cloud tops the visible surface; it is tuned by eye.
    MASS_EXTINCTION = 5.0e-4  # m^2/kg
    MAX_WIND_CELLS = 16  # the most wind cells a giant has (see cloud_state)
    # Rings, cosmetic (see Ring). A giant has them with RING_CHANCE. Each kind: its chance, where the inner and the
    # outer edges lie in radii of the giant (outer ones are cut by the Roche limit of the ring's particles), the density
    # of the particles (kg/m3), the optical depth range, its colour, and its name for the almanack.
    RING_CHANCE = 0.5
    RING_SAMPLES = 64  # the radial samples of a ring's optical depth
    RING_KINDS = {
        'broad': (0.25, (1.2, 1.5), (1.9, 2.4), 920.0, (0.3, 0.9), (0.9, 0.87, 0.78), 'bright and broad'),
        'dusty': (0.45, (1.25, 1.4), (1.7, 1.9), 2000.0, (0.01, 0.04), (0.45, 0.4, 0.36), 'faint and dusty'),
        'narrow': (0.30, (1.5, 1.9), (2.0, 2.5), 1000.0, (0.05, 0.3), (0.35, 0.35, 0.37), 'narrow and dark'),
    }
    # Lightning, in the water clouds deep below the cloud tops. Jupiter flashes a few times a second over the whole
    # planet, each flash a diffuse glow of some hundred kilometres that lasts a fraction of a second.
    LIGHTNING_RATE = 0.45  # flashes per second over the whole planet, away from the storms (the storms flash more)
    LIGHTNING_BURST_MEAN = 3.2  # flashes in a burst, on average: a burst is one flash, or many over up to 3 s
    LIGHTNING_BURST_SPAN = 3.0  # s: the longest a burst lasts
    LIGHTNING_DURATION = 0.4  # s
    LIGHTNING_PRESSURE = 5.0e5  # Pa: where the flashes are, the water clouds
    LIGHTNING_PER_STORM = 0.18  # flashes per second of a storm a million metres wide, by the square of its radius
    LIGHTNING_PER_STORM_MAX = 2.0
    # Storms: vortices that are born, drift with the jet of their latitude and die. They are drawn epoch by epoch from
    # the seed, and each lives from its birth to its death, so a date says which are alive and where, with nothing
    # stored. A giant may also have a great storm that never dies.
    STORM_EPOCH = 8.64e6  # s: 100 days
    STORM_BIRTHS = 3.0  # per epoch
    STORM_LIFE = (1.73e6, 9.5e7)  # s: lowest and highest (20 days, 3 years), log-uniform
    STORM_RADIUS = (0.01, 0.06)  # of the equatorial radius, log-uniform
    STORM_TWIST = (2.0, 4.0)  # rad at the centre
    GREAT_STORM_RADIUS = (0.12, 0.25)  # of the equatorial radius
    LIGHTNING_RADIUS = (8.0e4, 4.0e5)  # m: lowest and highest radius of the glow at the cloud tops (log-uniform)

    def __init__(self, parent_orbit: Orbit, saved_alterations: Optional[dict] = None) -> None:
        super().__init__()
        self.parent_orbit = parent_orbit
        self.index = len(parent_orbit.planets)
        self.seed = seeds.derive(parent_orbit.seed, 'planet', self.index)
        my_random = random.Random(self.seed)
        star = self.stellar_system.star

        # What the player changed here: its moons (see get_alterations). Nothing else of a giant can be changed.
        self.saved_alterations: Optional[dict] = None
        own_alterations: Optional[dict] = None
        if saved_alterations is not None:
            own_alterations = saved_alterations.get(self.get_alterations_key())
        if own_alterations is not None and saved_alterations is not None:
            self.is_altered = True
            self.hidden = bool(own_alterations.get('hidden', False))
            own_alterations['date_time'] = saved_alterations['date_time']
            self.saved_alterations = own_alterations

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
        self.density: float = self.mass / (4.0 / 3.0 * math.pi * self.radius ** 3)
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
        self.band_count = my_random.uniform(*traits.bands)
        self.band_phase = my_random.uniform(0.0, math.tau)
        self.band_contrast = my_random.uniform(*traits.band_contrast)
        self.wind_speed: float = my_random.uniform(*traits.wind)
        cloud_random = random.Random(seeds.derive(self.seed, 'clouds'))  # the clouds' own stream: no draw above moves
        self.cloud_offset: Tuple[float, float, float] = (cloud_random.uniform(0.0, 60.0), cloud_random.uniform(0.0, 60.0),
                                                         cloud_random.uniform(0.0, 60.0))  # where in the noise it is
        storm_random = random.Random(seeds.derive(self.seed, 'great storm'))
        self.storm_colour: Tuple[float, float, float] = traits.storm_colour
        self.great_storm: Optional[Tuple[float, float, float, float]] = None  # sine of latitude, longitude, radius, twist
        if storm_random.random() < traits.great_storm_chance:
            sine = storm_random.choice((-1.0, 1.0)) * storm_random.uniform(0.25, 0.55)
            self.great_storm = (sine, storm_random.uniform(-math.pi, math.pi),
                                self.equatorial_radius * storm_random.uniform(*JovianWorld.GREAT_STORM_RADIUS),
                                -math.copysign(storm_random.uniform(*JovianWorld.STORM_TWIST), sine))
        self._storm_cache: Dict[int, List[Tuple[int, float, float, float, float, float, float]]] = {}
        self._burst_cache: Dict[Tuple[int, int], List[Tuple[float, float, float, float, float]]] = {}
        self._generate_atmosphere(star, traits)

        self._learn()
        self.moon_limit: float = RockyWorld.moon_limit_in_radii(self.distance_to_parent, star.mass, self.density) \
            * self.radius
        self._generate_moons()
        self._generate_rings()
        self._log_creation()

    # region Generation
    def _generate_rings(self) -> None:
        """The rings, if the giant has them: their own stream from the seed, drawn last, so nothing else moves. The outer
        edge is cut at the Roche limit of the ring's particles (2.44 R (density / particle density)^(1/3), for a fluid
        giant), which is why a dense giant has no rings beyond a few radii. The optical depth has a broad profile, with
        gaps, as the real rings do."""
        self.ring: Optional[Ring] = None
        ring_random = random.Random(seeds.derive(self.seed, 'rings'))
        if ring_random.random() >= JovianWorld.RING_CHANCE:
            return
        kinds = list(JovianWorld.RING_KINDS.items())
        roll, cumulative, kind = ring_random.random(), 0.0, kinds[-1][0]
        for name, (chance, *_rest) in kinds:
            cumulative += chance
            if roll < cumulative:
                kind = name
                break
        _, inner_share, outer_share, particle_density, depth_range, colour, _ = JovianWorld.RING_KINDS[kind]
        radius = self.equatorial_radius
        inner = radius * ring_random.uniform(*inner_share)
        outer = min(radius * ring_random.uniform(*outer_share),
                    2.44 * radius * (self.density / particle_density) ** (1.0 / 3.0))
        if outer <= inner * 1.05:
            return
        depth = ring_random.uniform(*depth_range)
        # gaps as wide as the real ones (a few per cent of the ring's width at least): narrower ones alias on screen
        gaps = [(ring_random.random(), ring_random.uniform(0.02, 0.06), ring_random.uniform(0.3, 1.0))
                for _ in range(ring_random.randint(6, 10) if kind == 'narrow' else ring_random.randint(1, 3))]
        phase = ring_random.uniform(0.0, math.tau)
        opacity: List[float] = []
        for index in range(JovianWorld.RING_SAMPLES):
            x = (index + 0.5) / JovianWorld.RING_SAMPLES
            value = depth * math.sqrt(min(1.0, 4.0 * x * (1.0 - x))) * (0.85 + 0.15 * math.sin(8.0 * x + phase))
            for centre, width, share in gaps:
                if abs(x - centre) < width:
                    value *= 1.0 - share
            opacity.append(value)
        self.ring = Ring(inner, outer, tuple(opacity), colour, kind)

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
        # The height over which the pressure falls by a factor e, in the stratosphere; the haze thins with it.
        self.scale_height: float = self.specific_gas_constant * self.temperature_stratosphere / self.reference_gravity

    @property
    def kind_title(self) -> str:
        """'Gas giant' or 'Ice giant'."""
        return self.giant_class.traits.label

    def get_alterations(self) -> Optional[dict]:
        """The alterations of its moons, under 'moons' as a rocky planet keeps them, and whether it is hidden; None if
        none of them changed."""
        moon_alterations: dict = {}
        for moon in self.moons:
            one_moon_alterations: Optional[dict] = moon.get_alterations()
            if one_moon_alterations:
                moon_alterations[moon.get_alterations_key()] = one_moon_alterations
        alterations: dict = {'moons': moon_alterations} if moon_alterations else {}
        if self.hidden:
            alterations['hidden'] = True
        return alterations or None

    def _is_initial_planet(self) -> bool:
        return False  # the start is in an earthlike planet's system

    def _generate_moons(self) -> None:
        """The moons, largest first. Their radii are the arrivals of a Poisson process of sizes: the sum of exponential
        steps, each arrival r = MOON_REFERENCE_RADIUS (arrival / expected) ^ (-1 / MOON_SIZE_EXPONENT). The k-th largest
        moon is the k-th arrival, and its seed is that of the k-th moon, so the size and seed of a moon depend on the
        giant only, never on MOON_MIN_RADIUS: a lower limit adds the smaller moons after the others, and nothing already
        generated changes. No moon is drawn and thrown away, so the cost is the number kept."""
        if self.moon_limit < RockyWorld.MOON_MIN_ROOM_RADII * self.radius:
            return
        expected = JovianWorld.MOONS_ABOVE_REFERENCE \
            * (self.mass / JovianWorld.LARGE_ANCHOR[0]) ** JovianWorld.MOON_COUNT_MASS_EXPONENT
        sizes = random.Random(seeds.derive(self.seed, 'moon_sizes'))
        arrivals = 0.0
        while True:
            arrivals += sizes.expovariate(1.0)
            size_law = JovianWorld.MOON_REFERENCE_RADIUS \
                * (arrivals / expected) ** (-1.0 / JovianWorld.MOON_SIZE_EXPONENT)
            radius = min(size_law, JovianWorld.MOON_MAX_RADIUS_FRACTION * self.radius)
            if radius < JovianWorld.MOON_MIN_RADIUS:
                break
            self.moons.append(RockyWorld(parent_planet=self, radius=radius, saved_alterations=self.saved_alterations))
    # endregion

    @property
    def reference_gravity(self) -> float:
        """m/s^2, the figure astronomy quotes as a giant's "surface gravity": G M / R^2 at the equatorial radius of the
        1 bar level. A giant has no surface: it is flavour for the knowledge base, never used by the mechanics."""
        return self.gravitational_parameter / self.equatorial_radius ** 2

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

    def ambient_at(self, relative_position: Vector3) -> Tuple[float, float]:
        """The pressure (Pa) and the temperature (K) of the gas at a position relative to the centre, in the stellar
        frame (where the spin axis is z). Beyond the model's depth they are those of the depth."""
        distance = relative_position.length()
        latitude = math.asin(max(-1.0, min(1.0, relative_position.z / distance))) if distance > 0.0 else 0.0
        return self.atmosphere_at(distance - self.one_bar_radius(latitude), latitude)

    def optical_profile(self, altitudes: Sequence[float]) -> Tuple[List[float], List[float]]:
        """What the gas does to light at each altitude (m above the 1 bar level, at the equator): the extinction
        coefficient (1/m, the extinction of a kilogram times the density) and the optical depth of the column above
        (the extinction of a kilogram times the pressure over the gravity, the mass of the column)."""
        extinctions: List[float] = []
        column_depths: List[float] = []
        for altitude in altitudes:
            pressure, temperature = self.atmosphere_at(altitude, 0.0)
            distance = max(self.equatorial_radius + altitude, JovianWorld.MIN_RADIUS_FRACTION * self.equatorial_radius)
            gravity = self.reference_gravity * (self.equatorial_radius / distance) ** 2
            density = pressure * self.mean_molecular_weight / (JovianWorld.GAS_CONSTANT * temperature)
            extinctions.append(JovianWorld.MASS_EXTINCTION * density)
            column_depths.append(JovianWorld.MASS_EXTINCTION * pressure / gravity)
        return extinctions, column_depths

    def light_transmission(self, relative_position: Vector3, direction: Vector3) -> float:
        """The share of a star's light, coming from the unit `direction`, that reaches a position relative to the
        centre (stellar frame): the column of gas above it, along the slant of the light, and nothing when the star is
        below the local horizon. The same as the shader's, for what is not drawn by it (the glare)."""
        distance = relative_position.length()
        if distance <= 0.0:
            return 0.0
        cosine = relative_position.dot(direction) / distance
        return _smoothstep(-0.02, 0.15, cosine) * math.exp(-self.column_depth_at(relative_position) / max(cosine, 0.05))

    def _cell_rate(self, cell: int) -> float:
        """The angular speed (rad/s, eastward) of the clouds of a wind cell: its jet's, at the middle of the cell."""
        half_width = self.band_count * math.pi / 2.0
        sine = max(-0.97, min(0.97, (cell * math.pi - self.band_phase) / half_width))
        speed = self.wind_speed * (-1.0) ** cell * (1.0 - 0.5 * sine * sine)
        return speed / (self.equatorial_radius * math.sqrt(1.0 - sine * sine))

    def _wind_rate(self, sine: float) -> float:
        """The angular speed (rad/s) of the clouds at a latitude (its sine): the one of its wind cell."""
        pattern = self.band_count * math.pi / 2.0 * sine + self.band_phase
        return self._cell_rate(math.floor(pattern / math.pi + 0.5))

    def storms(self, current_datetime: datetime) -> List[Storm]:
        """The storms alive at a date, with where they are: each is carried east or west by the wind of its latitude.
        Pure functions of the date: the births of every epoch are drawn from the seed, so nothing is stored."""
        seconds = self._elapsed_seconds(current_datetime)
        epoch = math.floor(seconds / JovianWorld.STORM_EPOCH)
        reach = math.ceil(JovianWorld.STORM_LIFE[1] / JovianWorld.STORM_EPOCH)
        alive: List[Storm] = []
        for past in range(epoch - reach, epoch + 1):
            for key, birth, life, sine, longitude, radius, twist in self._storms_born(past):
                age = seconds - birth
                if 0.0 <= age < life:
                    strength = min(1.0, age / (0.1 * life), (life - age) / (0.2 * life))
                    drift = self._wind_rate(sine) * age
                    flashes = min(JovianWorld.LIGHTNING_PER_STORM_MAX,
                                  JovianWorld.LIGHTNING_PER_STORM * (radius / 1.0e6) ** 2 * strength)
                    alive.append(Storm(key, math.asin(sine), (longitude + drift + math.pi) % math.tau - math.pi, radius,
                                       twist, strength, flashes))
        if self.great_storm is not None:
            sine, longitude, radius, twist = self.great_storm
            flashes = min(JovianWorld.LIGHTNING_PER_STORM_MAX, JovianWorld.LIGHTNING_PER_STORM * (radius / 1.0e6) ** 2)
            drift = self._wind_rate(sine) * seconds
            alive.append(Storm(0, math.asin(sine), (longitude + drift + math.pi) % math.tau - math.pi, radius, twist, 1.0,
                               flashes))
        return alive

    def _storms_born(self, epoch: int) -> List[Tuple[int, float, float, float, float, float, float]]:
        """The storms born in an epoch: (key, birth s, life s, sine of latitude, longitude, radius m, twist rad)."""
        if epoch not in self._storm_cache:
            storm_random = random.Random(seeds.derive(self.seed, 'storms', epoch))
            born: List[Tuple[int, float, float, float, float, float, float]] = []
            count, limit, product = 0, math.exp(-JovianWorld.STORM_BIRTHS), storm_random.random()
            while product > limit:  # a Poisson count
                count += 1
                product *= storm_random.random()
            for number in range(count):
                low, high = JovianWorld.STORM_LIFE
                life = low * (high / low) ** storm_random.random()
                sine = storm_random.uniform(-0.8, 0.8)
                low, high = JovianWorld.STORM_RADIUS
                radius = self.equatorial_radius * low * (high / low) ** storm_random.random()
                twist = storm_random.uniform(*JovianWorld.STORM_TWIST)
                if storm_random.random() < 0.85:  # most turn against the sense of the hemisphere's cyclones
                    twist = -math.copysign(twist, sine)
                else:
                    twist = math.copysign(twist, sine)
                born.append((seeds.derive(self.seed, 'storm', epoch, number) % 2 ** 31,
                             (epoch + storm_random.random()) * JovianWorld.STORM_EPOCH, life, sine,
                             storm_random.uniform(-math.pi, math.pi), radius, twist))
            self._storm_cache[epoch] = born
        return self._storm_cache[epoch]

    def cloud_state(self, current_datetime: datetime) -> Tuple[float, int, List[float]]:
        """How the clouds are turned at a date: the planet's spin angle (rad), the index of the first wind cell, and the
        angle (rad, in [0, tau)) each cell's clouds have drifted eastward of the planet's turn. The cells are the
        stretches of latitude around each boundary between two bands, where the jets are: a cell's jet blows east or
        west by turns, at the speed of its latitude. Pure functions of the date, as the orbit is."""
        half_width = self.band_count * math.pi / 2.0
        first = math.floor((self.band_phase - half_width) / math.pi + 0.5)
        last = math.floor((self.band_phase + half_width) / math.pi + 0.5)
        seconds = self._elapsed_seconds(current_datetime)
        angles: List[float] = []
        for cell in range(first, min(last, first + JovianWorld.MAX_WIND_CELLS - 1) + 1):
            angles.append(math.tau * ((self._cell_rate(cell) * seconds / math.tau) % 1.0))
        return self._spin_angle_rad(current_datetime), first, angles

    def lightning(self, current_datetime: datetime) -> List[Tuple[float, float, float, float]]:
        """The flashes alight at a date, as (latitude rad, longitude rad on the planet, radius m of the glow at the
        cloud tops, brightness 0 to 1). The flashes come in bursts (`_bursts_of_slot`): one flash, or a chaotic run of
        them over up to 3 s, near each other. They are drawn second by second from the planet's seed, so a date gives the
        same flashes every time and nothing is stored but a cache. Most bursts come from the storms (`storms`), each
        at its own rate inside its radius; the rest are anywhere, favouring the belts, away from the poles. Each flash is
        a double pulse that dies away."""
        seconds = self._elapsed_seconds(current_datetime)
        storms = self.storms(current_datetime)
        first = math.floor(seconds - JovianWorld.LIGHTNING_BURST_SPAN - JovianWorld.LIGHTNING_DURATION)
        found: List[Tuple[float, float, float, float]] = []
        for slot in range(first, math.floor(seconds) + 1):
            sources = [(0, None)] + [(storm.key + 1, storm) for storm in storms]
            for key, storm in sources:
                for start, north, east, radius, strength in self._bursts_of_slot(slot, key, storm):
                    age = seconds - start
                    if not 0.0 <= age < JovianWorld.LIGHTNING_DURATION:
                        continue
                    pulse = math.exp(-age / 0.06) + (0.7 * math.exp(-(age - 0.12) / 0.06) if age > 0.12 else 0.0)
                    if strength * pulse <= 0.02:
                        continue
                    if storm is None:  # a place on the planet
                        latitude, longitude = north, east
                    else:  # a place in the storm, in its radii
                        latitude = max(-1.5, min(1.5, storm.latitude + north * storm.radius / self.equatorial_radius))
                        longitude = storm.longitude + east * storm.radius / self.equatorial_radius \
                            / max(math.cos(storm.latitude), 0.05)
                    found.append((latitude, longitude, radius, min(1.0, strength * pulse)))
        return found

    def _bursts_of_slot(self, slot: int, key: int, storm: Optional[Storm]) -> List[Tuple[float, float, float, float, float]]:
        """The flashes of the bursts that begin in one second (`slot`) of a source (the background, or a storm): (start s,
        north, east, radius m of the glow, strength). A burst is a single flash (a third of them) or a run of up to 14
        over up to 3 s, bunched at the start with stragglers after it, all within a little of the burst's place. North
        and east are the latitude and longitude of the place for the background and, for a storm, its offset from the
        storm's centre in storm radii. They are drawn in a fixed order, so the cache only saves the work."""
        if (key, slot) not in self._burst_cache:
            if len(self._burst_cache) > 4000:
                self._burst_cache.clear()
            # the rate must not depend on the date (a storm's strength does), or the cache would change the flashes
            rate = JovianWorld.LIGHTNING_RATE if storm is None else min(
                JovianWorld.LIGHTNING_PER_STORM_MAX, JovianWorld.LIGHTNING_PER_STORM * (storm.radius / 1.0e6) ** 2)
            slot_random = random.Random(seeds.derive(self.seed, 'lightning', key, slot))
            bursts, limit, product = 0, math.exp(-rate / JovianWorld.LIGHTNING_BURST_MEAN), slot_random.random()
            while product > limit:  # a Poisson count
                bursts += 1
                product *= slot_random.random()
            flashes: List[Tuple[float, float, float, float, float]] = []
            for _ in range(bursts):
                begin = slot + slot_random.random()
                count = 1 if slot_random.random() < 0.35 else min(14, 2 + int(slot_random.expovariate(0.3)))
                span = 0.0 if count == 1 else slot_random.uniform(0.3, JovianWorld.LIGHTNING_BURST_SPAN)
                if storm is None:
                    for _ in range(8):  # the latitude: more in the belts than in the zones
                        sine = slot_random.uniform(-0.95, 0.95)
                        pattern = self.band_count * math.pi / 2.0 * sine + self.band_phase
                        if slot_random.random() < 0.25 + 0.75 * (0.5 - 0.5 * math.sin(pattern)):
                            break
                    north, east = math.asin(sine), slot_random.uniform(-math.pi, math.pi)
                    scatter = 6.0e4 / self.equatorial_radius  # the flashes of a burst are within some tens of km
                else:
                    north, east = slot_random.gauss(0.0, 0.45), slot_random.gauss(0.0, 0.45)
                    scatter = 0.12  # storm radii
                for number in range(count):
                    offset = span * slot_random.random() ** 1.6 if number else 0.0
                    low, high = JovianWorld.LIGHTNING_RADIUS
                    flashes.append((begin + offset, north + slot_random.gauss(0.0, scatter),
                                    east + slot_random.gauss(0.0, scatter), low * (high / low) ** slot_random.random(),
                                    slot_random.uniform(0.35, 1.0)))
            self._burst_cache[(key, slot)] = flashes
        return self._burst_cache[(key, slot)]

    def column_depth_at(self, relative_position: Vector3) -> float:
        """The optical depth of the gas above a position relative to the centre (stellar frame), straight up."""
        pressure, _ = self.ambient_at(relative_position)
        return JovianWorld.MASS_EXTINCTION * pressure / max(self.pull_at(relative_position.length()), 1e-3)

    def pull_at(self, distance: float) -> float:
        """The pull at a distance from the centre: a point mass's outside the planet, and inside that of the mass within
        it, which falls to zero at the centre, where a ship can go. The planet is a polytrope of index 1, the usual
        model of a giant: the mass within x (the distance over the radius) is (sin(pi x) - pi x cos(pi x)) / pi of
        the whole."""
        x = distance / self.radius
        if x >= 1.0:
            return self.gravitational_parameter / distance ** 2
        if x <= 0.0:
            return 0.0
        y = math.pi * x
        enclosed = y ** 3 / (3.0 * math.pi) if y < 0.01 else (math.sin(y) - y * math.cos(y)) / math.pi
        return self.gravitational_parameter * enclosed / (self.radius * x) ** 2

    def dynamical_time(self, distance: float) -> float:
        """Inside the planet the time of the pull's change is that of the whole planet, not of the distance."""
        return super().dynamical_time(max(distance, self.radius))
    # endregion

    # region Almanack and log
    def markdown(self) -> str:
        '''Markdown of this world.'''
        AU: float = 1.496e11
        jupiter_mass: float = JovianWorld.LARGE_ANCHOR[0]
        edge: float = self.altitude_of_pressure(JovianWorld.ATMOSPHERE_EDGE_PRESSURE, 0.0)
        text: str = (
            f"### {self.giant_class.traits.label} {self.name}\n"
            f"* Distance from the star: {self.distance_to_parent / AU:.2f} AU\n"
            f"* Year: {self.orbital_period / (365.2425 * 24 * 60 * 60):.2f} Earth years\n"
            f"* Eccentricity: {self.eccentricity:.3f}\n"
            f"* Inclination: {math.degrees(self.inclination):.1f}°\n"
            f"* Mass: {self.mass / jupiter_mass:.2f} Jupiter masses (density {self.density:.0f} Kg/m3)\n"
            f"* Equatorial radius: {int(self.equatorial_radius / 1000)} Km\n"
            f"* Flattening: {self.flattening:.3f}\n"
            f"* Gravity at the clouds (1 bar): {self.reference_gravity:.2f} m/s² "
            f"({self.reference_gravity / 9.80665:.2f} g); felt with the spin, {self.gravity_equator:.2f} m/s² at the "
            f"equator and {self.gravity_pole:.2f} m/s² at the poles\n"
            f"* Day: {self.rotation_period / (60 * 60):.2f} hours\n"
            f"* Temperature at the clouds (1 bar): {self.temperature_one_bar - 273.15:.0f} °C\n"
            f"* Atmosphere: {100 * self.hydrogen:.1f}% hydrogen, {100 * self.helium:.1f}% helium, "
            f"{100 * self.methane:.1f}% methane\n"
            f"* Mean molecular weight: {1000 * self.mean_molecular_weight:.2f} g/mol\n"
            f"* The atmosphere thins out {int(edge / 1000)} Km above the clouds\n"
        )
        if self.ring is not None:
            text += (f"* Rings, {JovianWorld.RING_KINDS[self.ring.kind][6]}: from {self.ring.inner / 1000:,.0f} to "
                     f"{self.ring.outer / 1000:,.0f} Km from the centre\n")
        if self.great_storm is not None:
            sine, _, radius, twist = self.great_storm
            text += (f"* A great storm, {int(2 * radius / 1000):,} Km across, has turned {'clockwise' if twist < 0 else 'anticlockwise'}"
                     f" at {abs(math.degrees(math.asin(sine))):.0f}° {'north' if sine > 0 else 'south'} for as long as "
                     f"anyone knows, and it flashes with lightning\n")
        text += f"\n"
        text += ''.join(moon.markdown() for moon in self.moons)
        return text

    def _log_creation(self) -> JovianWorld:
        logger.info("NEW JOVIAN PLANET CREATED")
        logger.info(f" - Orbit(Index): {int(self.parent_orbit.number)} ({self.index})")
        logger.info(f" - Name: {self.name}, Seed: {self.seed}")
        logger.info(f" - Class: {self.giant_class.traits.label}")
        logger.info(f" - Distance to parent: {f'{int(self.distance_to_parent):,}'}")
        logger.info(f" - Mass: {self.mass:.4g} kg, density: {self.density:.0f} kg/m3, "
                    f"mean radius: {f'{int(self.radius):,}'}, flattening {self.flattening:.4f}")
        logger.info(f" - Gravity at 1 bar: {self.reference_gravity:.2f} m/s2 (equator with spin "
                    f"{self.gravity_equator:.2f}, pole {self.gravity_pole:.2f})")
        logger.info(f" - Spin: rotation period {self.rotation_period:.3g} s, "
                    f"tilt {math.degrees(self.inclination):.1f}°")
        logger.info(f" - Temperature: {self.equilibrium_temperature:.0f} K in equilibrium, "
                    f"{self.internal_temperature:.0f} K internal, {self.temperature_one_bar:.0f} K at 1 bar")
        logger.info(f" - Atmosphere: molecular weight {1000 * self.mean_molecular_weight:.3f} g/mol")
        return self
    # endregion
