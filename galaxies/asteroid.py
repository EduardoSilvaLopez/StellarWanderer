"""A relevant asteroid: one the player has a reason to follow (the target of a mission).

Most of a belt is cosmetic: rows of arrays that are regenerated whenever needed and are never remembered (see
asteroid_belt.py). A relevant asteroid is one of those rows, promoted: it leaves the cosmetic population and follows a
full elliptical orbit, with the eccentricity and inclination the cosmetic ones do without. Its orbit is a pure function
of its key, name included, so the savefile holds only the key (an alteration of the belt).

A free-living asteroid (`Asteroid.free_living`) belongs to no belt: the near-Earth objects and their like, on eccentric
and tilted orbits that cross those of the planets, drawn from a seed alone. There is no cosmetic row to take out for it.
When it matters (a mission's target), the stellar system keeps it (`StellarSystem.promote_free_asteroid`) and saves its
seed.
"""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

from common.units import format_compact_distance
from common.vector3 import Vector3
from galaxies import seeds
from galaxies.asteroid_class import class_of
from galaxies.asteroid_sizes import AsteroidTier, sample_diameters
from galaxies.body import Body
from galaxies.kepler import eccentric_anomaly, orbit_axes
from galaxies.orbit_layout import SystemScales
from galaxies.world import World

if TYPE_CHECKING:
    from galaxies.asteroid_belt import AsteroidBelt
    from galaxies.stellar_system import StellarSystem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AsteroidKey:
    """Where an asteroid is generated: the tier (`AsteroidTier.index`), the epoch of the belt and the sector's indices,
    and the integer cell of the asteroid inside it (see asteroid_belt.py)."""
    tier: int
    epoch: int
    sector: tuple[int, int, int]
    cell: tuple[int, int, int]

    @staticmethod
    def from_ints(values: Iterable[int]) -> AsteroidKey:
        tier, epoch, *indices = (int(value) for value in values)
        return AsteroidKey(tier, epoch, tuple(indices[:3]), tuple(indices[3:6]))

    def __str__(self) -> str:
        return " ".join(str(value) for value in (self.tier, self.epoch, *self.sector, *self.cell))


class Asteroid(Body):
    """An asteroid on an elliptical orbit around the star. A position and a velocity are pure functions of the date,
    memoised for the date of the last call, as for a `World`. It is not a world: no surface to bind to."""

    is_world = False

    ECCENTRICITY_SIGMA = World.ECCENTRICITY_SIGMA
    MAX_ECCENTRICITY = World.MAX_ECCENTRICITY
    INCLINATION_SIGMA_DEGREES = 5.0  # about the thickness of a belt
    MAX_INCLINATION_DEGREES = 20.0

    # Free-living asteroids: from the Mars-crossers to the region of the giants, eccentric and tilted.
    FREE_SNOW_LINES = (0.4, 3.0)  # the semi-major axis is log-uniform between these distances, in snow lines
    FREE_ECCENTRICITY_SIGMA = 0.3
    FREE_MAX_ECCENTRICITY = 0.7
    FREE_PERIAPSIS_INNER_EDGES = 1.5  # the periapsis is never closer to the star than this, in inner edges
    FREE_INCLINATION_SIGMA_DEGREES = 15.0
    FREE_MAX_INCLINATION_DEGREES = 40.0
    # The tier of the size is drawn with these weights.
    FREE_TIERS = ((AsteroidTier.MEDIUM, 3.0), (AsteroidTier.BIG, 1.0))

    # Scanning (see Scanner): the beam works within SCAN_RANGE_DIAMETERS diameters of the surface (and never farther
    # than SCAN_MAX_RANGE), while the ship moves at most SCAN_MAX_SPEED relative to the asteroid and has it in the
    # crosshair.
    # A scan takes SCAN_SECONDS_PER_SQRT_KM game seconds for an asteroid of a kilometre, and the square root of its
    # diameter in kilometres times that for any other. What the knowledge base shows of it depends on the share of the
    # scan done (`markdown`): the orbit from the start, then each of these at its share.
    SCAN_SECONDS_PER_SQRT_KM = 30.0
    SCAN_RANGE_DIAMETERS = 5.0
    SCAN_MAX_RANGE = 100.0e3  # m
    SCAN_MAX_SPEED = 50.0  # m/s
    SCAN_DIAMETER = 0.25
    SCAN_CLASS = 0.5  # and the temperature, which depends on it
    SCAN_MASS = 0.75  # and the gravity at the surface
    SCAN_STRUCTURE = 1.0

    def __init__(self, stellar_system: StellarSystem, seed: int, my_random: random.Random, semi_major_axis: float,
                 diameter: float, eccentricity: float, inclination: float,
                 parent_belt: AsteroidBelt | None = None, key: AsteroidKey | None = None,
                 offer_seed: int | None = None) -> None:
        """Made by `of_belt` and `free_living`, which have drawn from `my_random` (the generator of `seed`) the values
        that differ between them. The node, the periapsis argument and the mean anomaly follow, and the name last."""
        self._position_cache: tuple[datetime, Vector3] | None = None
        self._velocity_cache: tuple[datetime, Vector3] | None = None
        self._stellar_system: StellarSystem = stellar_system
        self.parent_belt: AsteroidBelt | None = parent_belt  # None for a free-living asteroid
        self.key: AsteroidKey | None = key
        self.offer_seed: int | None = offer_seed  # the seed of the mission it comes from, for a free-living asteroid
        self.seed: int = seed

        self.radius: float = diameter / 2.0
        self.semi_major_axis: float = semi_major_axis
        self.eccentricity: float = eccentricity
        self.inclination: float = inclination
        self.node_longitude: float = my_random.random() * math.tau
        self.periapsis_argument: float = my_random.random() * math.tau
        self.mean_anomaly_at_epoch: float = my_random.random() * math.tau
        self._periapsis_axis, self._quarter_axis = orbit_axes(
            self.node_longitude, self.inclination, self.periapsis_argument)
        self.mean_motion: float = math.sqrt(
            World.GRAVITATIONAL_CONSTANT * stellar_system.star.mass / semi_major_axis ** 3)
        self.name: str = self._generate_name(my_random)
        self.scan_progress: float = 0.0  # 0 to 1, the share of the scan done; saved with the asteroid (get_alterations)
        # 0 to 1, the share of a whole scoop done; not saved (see Ship.collect_raw_water)
        self.scoop_progress: float = 0.0

    @property
    def stellar_system(self) -> StellarSystem:
        return self._stellar_system

    @staticmethod
    def of_belt(parent_belt: AsteroidBelt, key: AsteroidKey, semi_major_axis: float, diameter: float) -> Asteroid:
        """The asteroid of a belt's key: the semi-major axis and the diameter of its cosmetic row, the rest drawn from
        the belt's seed and the key. A pure function of them, name included, whenever it is made."""
        seed = seeds.derive(parent_belt.seed, 'asteroid', str(key))
        my_random = random.Random(seed)
        eccentricity = min(abs(my_random.gauss(0.0, Asteroid.ECCENTRICITY_SIGMA)), Asteroid.MAX_ECCENTRICITY)
        inclination = math.radians(
            min(abs(my_random.gauss(0.0, Asteroid.INCLINATION_SIGMA_DEGREES)), Asteroid.MAX_INCLINATION_DEGREES))
        return Asteroid(parent_belt.parent_stellar_system, seed, my_random, semi_major_axis, diameter, eccentricity,
                        inclination, parent_belt, key)

    @staticmethod
    def free_living(stellar_system: StellarSystem, offer_seed: int) -> Asteroid:
        """An asteroid of no belt, drawn from the system's seed and `offer_seed` (the mission's). Drawn in this order:
        semi-major axis, eccentricity, inclination, tier and the diameter's generator."""
        seed = seeds.derive(stellar_system.seed, 'free asteroid', offer_seed)
        my_random = random.Random(seed)
        scales = SystemScales.of(stellar_system.star)
        low, high = (scales.snow_line * ratio for ratio in Asteroid.FREE_SNOW_LINES)
        semi_major_axis = math.exp(my_random.uniform(math.log(low), math.log(high)))
        # The periapsis stays clear of the star: the eccentricity is capped by it.
        eccentricity = min(abs(my_random.gauss(0.0, Asteroid.FREE_ECCENTRICITY_SIGMA)), Asteroid.FREE_MAX_ECCENTRICITY,
                           1.0 - Asteroid.FREE_PERIAPSIS_INNER_EDGES * scales.inner_edge / semi_major_axis)
        inclination = math.radians(min(abs(my_random.gauss(0.0, Asteroid.FREE_INCLINATION_SIGMA_DEGREES)),
                                       Asteroid.FREE_MAX_INCLINATION_DEGREES))
        tiers = [tier for tier, _ in Asteroid.FREE_TIERS]
        weights = [weight for _, weight in Asteroid.FREE_TIERS]
        tier = my_random.choices(tiers, weights)[0]
        diameter = float(sample_diameters(tier, np.random.default_rng(my_random.getrandbits(64)), 1)[0])
        return Asteroid(stellar_system, seed, my_random, semi_major_axis, diameter, eccentricity, inclination,
                        offer_seed=offer_seed)

    def site(self) -> dict:
        """What identifies the asteroid in its system, as a savefile holds it: the belt's orbit number and the key for a
        belt-born one, the offer's seed for a free-living one (see StellarSystem.asteroid_from_site)."""
        if self.parent_belt is not None:
            return {'belt': int(self.parent_belt.number), 'key': str(self.key), 'seed': None}
        return {'belt': None, 'key': None, 'seed': self.offer_seed}

    @property
    def mass(self) -> float:
        """The mass, in Kg: the density of its class times the volume of its sphere."""
        return class_of(self.seed).density * 4.0 / 3.0 * math.pi * self.radius ** 3

    def consume(self) -> None:
        """The scoop has taken the whole asteroid: it is gone from its belt or its system, for good."""
        if self.parent_belt is not None:
            self.parent_belt.consume(self.key)
        else:
            self.stellar_system.consume_free_asteroid(self.offer_seed)

    def advance_scan(self, game_seconds: float) -> bool:
        """The beam has worked for `game_seconds` on it: the scan advances, never back. True when it has just
        finished."""
        was_scanned = self.scan_progress >= 1.0
        duration = Asteroid.SCAN_SECONDS_PER_SQRT_KM * math.sqrt(2.0 * self.radius / 1000.0)
        self.scan_progress = min(1.0, self.scan_progress + game_seconds / duration)
        return self.scan_progress >= 1.0 and not was_scanned

    def get_alterations(self) -> dict:
        """What the savefile holds of the asteroid besides its key: the scan, once begun."""
        return {'scan': self.scan_progress} if self.scan_progress > 0.0 else {}

    def apply_alterations(self, saved: dict) -> Asteroid:
        self.scan_progress = float(saved.get('scan', 0.0))
        return self

    def _generate_name(self, my_random: random.Random) -> str:
        """The asteroid's name, derived from its discoverer, usually a scientist."""
        from galaxies.people.person import _pick_name

        gender = 'female' if my_random.random() < 0.55 else 'male'
        language: str = 'chinese' if my_random.random() < 0.6 else 'english'
        discoverer_name = _pick_name(my_random, f'{language}_{gender}_surnames.txt')

        number: int = min(my_random.randint(1, 1000), my_random.randint(1, 1000))

        return f"{discoverer_name.capitalize()}-{number}"

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        """Position relative to the star, in the reference frame (meters). Memoised for the date of the last call."""
        cached = self._position_cache
        if cached is not None and cached[0] == current_datetime:
            return cached[1]
        anomaly = eccentric_anomaly(self.eccentricity, self._mean_anomaly(current_datetime))
        a, e = self.semi_major_axis, self.eccentricity
        x = a * (math.cos(anomaly) - e)
        y = a * math.sqrt(1.0 - e * e) * math.sin(anomaly)
        p, q = self._periapsis_axis, self._quarter_axis
        result = Vector3(x * p[0] + y * q[0], x * p[1] + y * q[1], x * p[2] + y * q[2])
        self._position_cache = (current_datetime, result)
        return result

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        """Velocity relative to the star (meters per second), in the frame of calculate_stellar_position. Memoised for
        the date of the last call."""
        cached = self._velocity_cache
        if cached is not None and cached[0] == current_datetime:
            return cached[1]
        anomaly = eccentric_anomaly(self.eccentricity, self._mean_anomaly(current_datetime))
        a, e = self.semi_major_axis, self.eccentricity
        rate = self.mean_motion / (1.0 - e * math.cos(anomaly))  # d(anomaly)/dt
        vx = -a * math.sin(anomaly) * rate
        vy = a * math.sqrt(1.0 - e * e) * math.cos(anomaly) * rate
        p, q = self._periapsis_axis, self._quarter_axis
        result = Vector3(vx * p[0] + vy * q[0], vx * p[1] + vy * q[1], vx * p[2] + vy * q[2])
        self._velocity_cache = (current_datetime, result)
        return result

    def orbit_points(self, current_datetime: datetime, steps: int) -> np.ndarray:
        """The orbit as an (n, 3) array of points round the star, in the frame of calculate_stellar_position: `steps`
        evenly spread, plus some close to the asteroid's own place at the date (one of them), so that a line through
        them passes through it (as World.orbit_points does)."""
        own = eccentric_anomaly(self.eccentricity, self._mean_anomaly(current_datetime))
        near = np.array([0.0, *World.ORBIT_NEAR_ANOMALIES, *(-a for a in World.ORBIT_NEAR_ANOMALIES)]) + own
        anomalies = np.sort(np.mod(np.concatenate([math.tau * np.arange(steps) / steps, near]), math.tau))
        a, e = self.semi_major_axis, self.eccentricity
        x = a * (np.cos(anomalies) - e)
        y = a * math.sqrt(1.0 - e * e) * np.sin(anomalies)
        return x[:, None] * np.array(self._periapsis_axis) + y[:, None] * np.array(self._quarter_axis)

    def markdown(self) -> str:
        """The asteroid's entry in the knowledge base: what the game has worked out about it, in the friendly units of
        the almanack (AU, Earth years, Km/s), like the planets' entries. The orbit is known as soon as the asteroid is
        followed, the rest as the scan advances (SCAN_DIAMETER and the other shares)."""
        AU: float = 1.496e11
        star = self.stellar_system.star
        asteroid_class = class_of(self.seed)
        diameter = 2.0 * self.radius
        mass = self.mass
        gravity = World.GRAVITATIONAL_CONSTANT * mass / self.radius ** 2
        a, e = self.semi_major_axis, self.eccentricity
        periapsis, apoapsis = a * (1.0 - e), a * (1.0 + e)
        gm = World.GRAVITATIONAL_CONSTANT * star.mass
        speed_at_periapsis = math.sqrt(gm * (2.0 / periapsis - 1.0 / a))
        speed_at_apoapsis = math.sqrt(gm * (2.0 / apoapsis - 1.0 / a))

        def temperature(distance: float) -> float:  # K, in balance with the light it takes in (as World's)
            absorbed = star.luminosity * (1.0 - asteroid_class.reflectance)
            return (absorbed / (16.0 * math.pi * star.STEFAN_BOLTZMANN * distance ** 2)) ** 0.25

        place = (f"belt {int(self.parent_belt.number)}, at {self.parent_belt.distance_from_star / AU:.2f} AU"
                 if self.parent_belt is not None else "free-living, in no belt")
        year = math.tau / self.mean_motion / (365.2425 * 24 * 60 * 60)
        # The rows come in the order they are learnt: what the orbit gives, from the start, then each group at its
        # share of the scan, so that scanning only adds rows at the end.
        text = (
            f"### Asteroid {self.name}\n"
            f"* Place: {place}\n"
            f"* Eccentricity: {e:.3f}\n"
            f"* Distance from the star:\n"
            f"  * Average: {a / AU:.2f} AU\n"
            f"  * Periapsis: {periapsis / AU:.2f} AU - Orbital speed {speed_at_periapsis / 1000:.1f} Km/s\n"
            f"  * Apoapsis: {apoapsis / AU:.2f} AU - Orbital speed {speed_at_apoapsis / 1000:.1f} Km/s\n"
            f"* Year: {year:.2f} Earth years\n"
            f"* Inclination: {math.degrees(self.inclination):.1f}°\n"
            f"* Longitude of the ascending node: {math.degrees(self.node_longitude):.1f}°\n"
            f"* Argument of periapsis: {math.degrees(self.periapsis_argument):.1f}°\n"
        )
        if self.scan_progress >= Asteroid.SCAN_DIAMETER:
            text += f"* Diameter: {format_compact_distance(diameter)} across\n"
        if self.scan_progress >= Asteroid.SCAN_CLASS:
            text += (
                f"* Class: {asteroid_class.name}\n"
                f"* Temperature: {temperature(apoapsis) - 273.15:.0f} °C at the farthest, "
                f"{temperature(periapsis) - 273.15:.0f} °C at the closest\n"
            )
        if self.scan_progress >= Asteroid.SCAN_MASS:
            text += (
                f"* Mass: {mass:.2e} Kg (density {asteroid_class.density:.0f} Kg/m3)\n"
                f"* Surface gravity: {gravity:.2e} m/s2\n"
            )
        if self.scan_progress >= Asteroid.SCAN_STRUCTURE:
            text += "\nDetailed structure / composition data saved for scientific analysis.\n"
        return text + "\n"

    def _mean_anomaly(self, current_datetime: datetime) -> float:
        # Local: as World does, the game environment needs the galaxy to load.
        from game_environment import GameEnvironment
        elapsed_seconds = (current_datetime - GameEnvironment.EPOCH).total_seconds()
        return self.mean_anomaly_at_epoch + self.mean_motion * elapsed_seconds
