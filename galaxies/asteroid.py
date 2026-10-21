"""A relevant asteroid: one the player has a reason to follow (the target of a mission).

Most of a belt is cosmetic: rows of arrays that are regenerated whenever needed and are never remembered (see
asteroid_belt.py). A relevant asteroid is one of those rows, promoted: it leaves the cosmetic population and follows a full
elliptical orbit, with the eccentricity and inclination the cosmetic ones do without. Its orbit is a pure function of its
key, so the savefile holds only the key (an alteration of the belt).
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Iterable, Optional, Tuple

from common.vector3 import Vector3
from galaxies import seeds
from galaxies.body import Body
from galaxies.kepler import eccentric_anomaly, orbit_axes
from galaxies.world import World

if TYPE_CHECKING:
    from galaxies.asteroid_belt import AsteroidBelt
    from galaxies.stellar_system import StellarSystem


@dataclass(frozen=True)
class AsteroidKey:
    """Where an asteroid is generated: the tier (`AsteroidTier.index`), the epoch of the belt and the sector's indices, and
    the integer cell of the asteroid inside it (see asteroid_belt.py)."""
    tier: int
    epoch: int
    sector: Tuple[int, int, int]
    cell: Tuple[int, int, int]

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

    def __init__(self, parent_belt: AsteroidBelt, key: AsteroidKey, semi_major_axis: float, diameter: float) -> None:
        self._position_cache: Optional[Tuple[datetime, Vector3]] = None
        self._velocity_cache: Optional[Tuple[datetime, Vector3]] = None
        self.parent_belt: AsteroidBelt = parent_belt
        self.key: AsteroidKey = key
        self.seed: int = seeds.derive(parent_belt.seed, 'asteroid', str(key))
        my_random = random.Random(self.seed)

        self.name: str = f"{self.stellar_system.star.name} belt {int(parent_belt.number)} #{self.seed % 1_000_000:06d}"
        self.radius: float = diameter / 2.0
        self.semi_major_axis: float = semi_major_axis
        self.eccentricity: float = min(abs(my_random.gauss(0.0, Asteroid.ECCENTRICITY_SIGMA)), Asteroid.MAX_ECCENTRICITY)
        self.inclination: float = math.radians(
            min(abs(my_random.gauss(0.0, Asteroid.INCLINATION_SIGMA_DEGREES)), Asteroid.MAX_INCLINATION_DEGREES))
        self.node_longitude: float = my_random.random() * math.tau
        self.periapsis_argument: float = my_random.random() * math.tau
        self.mean_anomaly_at_epoch: float = my_random.random() * math.tau
        self._periapsis_axis, self._quarter_axis = orbit_axes(
            self.node_longitude, self.inclination, self.periapsis_argument)
        self.mean_motion: float = math.sqrt(parent_belt.gravitational_parameter / semi_major_axis ** 3)

    @property
    def stellar_system(self) -> StellarSystem:
        return self.parent_belt.parent_stellar_system

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

    def _mean_anomaly(self, current_datetime: datetime) -> float:
        from game_environment import GameEnvironment  # local: as World does, the game environment needs the galaxy to load
        elapsed_seconds = (current_datetime - GameEnvironment.EPOCH).total_seconds()
        return self.mean_anomaly_at_epoch + self.mean_motion * elapsed_seconds
