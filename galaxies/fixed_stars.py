"""The fixed stars: the stars of the sectors around the initial star, generated from the galaxy seed and kept in memory.

Galactic space is cut into cubes of SECTOR_SIZE ly, aligned to multiples of it. The sectors within SECTOR_RADIUS of the
initial star's sector (a 5 x 5 x 5 block) are generated. Each sector draws its stars from a seed derived from its index,
so the same galaxy always gives the same stars. A star has a float position inside its sector and occupies the integer
cell (1 ly) that contains it; no two stars share a cell.

A fixed star is only its seed and position, plus the properties Star derives from its seed: no orbits, planets or moons.
The initial star gets the seed a StellarSystem gives it, so the system and the fixed star describe the same star.

Nothing is saved for a fixed star: it is regenerated from the galaxy seed whenever it is needed.
"""

import logging
import math
import random
from collections import Counter
from itertools import product

from galaxies.constants import (
    FIXED_STARS_MEAN_PER_SECTOR,
    INITIAL_STAR_POSITION,
    SECTOR_RADIUS,
    SECTOR_SIZE,
    SEEDS_SCALING,
)
from galaxies.star import Star
from galaxies.stellar_system import StellarSystem

logger = logging.getLogger(__name__)

REPORT_RADIUS = 40.0  # ly: the radius around the initial star in which the log counts the stars
MAX_PLACEMENT_TRIES = 50  # attempts to find a free cell for a star before giving up on it


def sector_of(position: tuple[float, float, float]) -> tuple[int, int, int]:
    """The index of the sector that contains the position."""
    return (math.floor(position[0] / SECTOR_SIZE), math.floor(position[1] / SECTOR_SIZE), math.floor(position[2] / SECTOR_SIZE))


def _sector_origin(sector: tuple[int, int, int]) -> tuple[float, float, float]:
    return (float(sector[0] * SECTOR_SIZE), float(sector[1] * SECTOR_SIZE), float(sector[2] * SECTOR_SIZE))


def _sector_seed(galaxy_seed: float, sector: tuple[int, int, int]) -> int:
    # The indices are shifted to be non-negative and packed into 13 bits each: hash() of a negative int is not
    # injective (hash(-1) == hash(-2)), so it cannot be used on the indices. hash() of the galaxy seed (a float) is
    # not randomised per process (unlike str), so the seed is the same in every run.
    key: int = 0
    for index in sector:
        key = key * 8192 + (index + 4096)
    return ((hash(galaxy_seed) & (2 ** 64 - 1)) << 39) | key


def _poisson(my_random: random.Random, mean: float) -> int:
    """A Poisson-distributed count with the given mean (Knuth's multiplication method)."""
    limit: float = math.exp(-mean)
    count: int = 0
    product_of_uniforms: float = my_random.random()
    while product_of_uniforms > limit:
        count += 1
        product_of_uniforms *= my_random.random()
    return count


def _cell_of(position: tuple[float, float, float]) -> tuple[int, int, int]:
    return (math.floor(position[0]), math.floor(position[1]), math.floor(position[2]))


def _generate_sector(galaxy_seed: float, sector: tuple[int, int, int], used_cells: set[tuple[int, int, int]]) -> list[Star]:
    """The random stars of one sector. `used_cells` holds the cells taken so far, in the whole region; it is updated."""
    my_random: random.Random = random.Random(_sector_seed(galaxy_seed, sector))
    origin: tuple[float, float, float] = _sector_origin(sector)
    stars: list[Star] = []
    for _ in range(_poisson(my_random, FIXED_STARS_MEAN_PER_SECTOR)):
        for _ in range(MAX_PLACEMENT_TRIES):
            position: tuple[float, float, float] = tuple(c + my_random.random() * SECTOR_SIZE for c in origin)
            if _cell_of(position) not in used_cells:
                break
        else:
            logger.warning(f"No free cell found in sector {sector}; a star is left out.")
            continue
        used_cells.add(_cell_of(position))
        stars.append(Star(float(my_random.getrandbits(48)), position))
    return stars


def generate_region(galaxy_seed: float) -> list[Star]:
    """The fixed stars of the region around the initial star, the initial star included. Logs aggregate results."""
    initial_star_seed: float = (StellarSystem.seed_of(galaxy_seed, *INITIAL_STAR_POSITION) + 1) % SEEDS_SCALING
    initial_star: Star = Star(initial_star_seed, INITIAL_STAR_POSITION)
    stars: list[Star] = [initial_star]
    used_cells: set[tuple[int, int, int]] = {_cell_of(INITIAL_STAR_POSITION)}

    centre: tuple[int, int, int] = sector_of(INITIAL_STAR_POSITION)
    per_sector_counts: list[int] = []
    for offset in product(range(-SECTOR_RADIUS, SECTOR_RADIUS + 1), repeat=3):
        sector = (centre[0] + offset[0], centre[1] + offset[1], centre[2] + offset[2])
        sector_stars: list[Star] = _generate_sector(galaxy_seed, sector, used_cells)
        per_sector_counts.append(len(sector_stars))
        stars.extend(sector_stars)

    _log_summary(galaxy_seed, stars, per_sector_counts)
    return stars


def _log_summary(galaxy_seed: float, stars: list[Star], per_sector_counts: list[int]) -> None:
    within: int = sum(1 for star in stars if math.dist(star.position, INITIAL_STAR_POSITION) <= REPORT_RADIUS)
    types: Counter = Counter(star.type.name for star in stars)
    side: int = 2 * SECTOR_RADIUS + 1
    logger.info(
        f"Fixed stars of galaxy {galaxy_seed}: {len(stars)} stars (the initial one included) in {side ** 3} sectors of "
        f"{SECTOR_SIZE} ly; per sector min {min(per_sector_counts)}, mean {sum(per_sector_counts) / len(per_sector_counts):.1f}, "
        f"max {max(per_sector_counts)}."
    )
    logger.info(f"Fixed stars within {REPORT_RADIUS} ly of the initial star: {within}.")
    logger.info("Fixed stars by type: " + ", ".join(f"{name} {types[name]}" for name in sorted(types)) + ".")
