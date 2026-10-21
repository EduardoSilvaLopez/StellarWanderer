"""The sizes of the asteroids, and the six tiers ("asteroidal sectors") they are generated in.

A belt has asteroids down to dust, and the count N(>D) grows without limit towards small diameters. Only those from
MIN_DIAMETER (1 m, about a tonne) up are generated. Above MAX_DIAMETER (the diameter of the smallest world) a body is a
dwarf planet, made by another method; the law gives the number to expect there, so both methods fit.

The cumulative count follows a broken power law, N(>D) ~ D^-b, anchored on the main belt's measured N(>1 km). The slopes follow
the surveys (approximately; the real curve is wavy): collisional equilibrium (2.5, Dohnanyi) below 100 m, steeper from 100 m to
1 km, about 1.85 from 1 km to 100 km, and a steep top end above that, which leaves about half a body above MAX_DIAMETER in the reference belt (Ceres).

The tiers split the diameters by decades. Each has its own grid of sectors (see asteroid_belt.py), so that a query for big
asteroids does not generate the countless tiny ones.
"""

from __future__ import annotations
from enum import Enum
from typing import Union

import numpy as np

from galaxies.world import World

MIN_DIAMETER = 1.0  # m
MAX_DIAMETER = 2.0 * World.WORLD_MIN_RADIUS  # m

ANCHOR_DIAMETER = 1.0e3  # m
ANCHOR_COUNT = 1.1e6  # asteroids above ANCHOR_DIAMETER in the reference belt (surveys: 1.1 to 1.9 million)

# Segments of the law: [BREAKS[i], BREAKS[i + 1]) has the cumulative slope SLOPES[i].
BREAKS = np.array([MIN_DIAMETER, 100.0, 1.0e3, 1.0e5, MAX_DIAMETER])
SLOPES = np.array([2.5, 2.7, 1.85, 3.4])
ANCHOR_INDEX = 2  # BREAKS[2] is ANCHOR_DIAMETER


def _cumulative_at_breaks() -> np.ndarray:
    """N(>D) at each break, as a multiple of N(>ANCHOR_DIAMETER)."""
    result = np.ones(len(BREAKS))
    for i in range(ANCHOR_INDEX + 1, len(BREAKS)):
        result[i] = result[i - 1] * (BREAKS[i] / BREAKS[i - 1]) ** -SLOPES[i - 1]
    for i in range(ANCHOR_INDEX - 1, -1, -1):
        result[i] = result[i + 1] * (BREAKS[i + 1] / BREAKS[i]) ** SLOPES[i]
    return result


CUMULATIVE = _cumulative_at_breaks()


class AsteroidTier(Enum):
    TINY = (0, MIN_DIAMETER, 10.0)
    SMALL = (1, 10.0, 100.0)
    MEDIUM = (2, 100.0, 1.0e3)
    BIG = (3, 1.0e3, 1.0e4)
    LARGE = (4, 1.0e4, 1.0e5)
    HUGE = (5, 1.0e5, MAX_DIAMETER)

    def __init__(self, index: int, lower: float, upper: float) -> None:
        self.index: int = index
        self.lower: float = lower  # m: diameters from here (included)
        self.upper: float = upper  # m: up to here (excluded)


def cumulative(diameter: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """N(>D) as a multiple of N(>ANCHOR_DIAMETER), for diameters from MIN_DIAMETER to MAX_DIAMETER."""
    segment = np.clip(np.searchsorted(BREAKS, diameter, side='right') - 1, 0, len(SLOPES) - 1)
    return CUMULATIVE[segment] * (diameter / BREAKS[segment]) ** -SLOPES[segment]


def generated_count() -> float:
    """The asteroids generated in the reference belt: from MIN_DIAMETER up to MAX_DIAMETER."""
    return ANCHOR_COUNT * (CUMULATIVE[0] - CUMULATIVE[-1])


def tier_share(tier: AsteroidTier) -> float:
    """The fraction of the generated asteroids that are of the tier."""
    return (cumulative(tier.lower) - cumulative(tier.upper)) / (CUMULATIVE[0] - CUMULATIVE[-1])


def sample_diameters(tier: AsteroidTier, my_random: np.random.Generator, count: int) -> np.ndarray:
    """`count` diameters (m) of the tier, following the law: the cumulative count is drawn uniformly and inverted."""
    top, bottom = cumulative(tier.upper), cumulative(tier.lower)
    target = top + my_random.random(count) * (bottom - top)
    segment = np.clip(np.searchsorted(-CUMULATIVE, -target, side='right') - 1, 0, len(SLOPES) - 1)
    diameters = BREAKS[segment] * (CUMULATIVE[segment] / target) ** (1.0 / SLOPES[segment])
    return np.clip(diameters, tier.lower, np.nextafter(tier.upper, 0.0))
