"""The fixed stars: the stars of the sectors around the initial star, generated from the galaxy seed and kept in memory.

Galactic space is cut into cubes of SECTOR_SIZE ly, aligned to multiples of it. Sectors sit in districts (DISTRICT_SIZE
ly) and districts in quadrants (QUADRANT_SIZE ly); those two levels only feed the seeds for now (see seeds.py). The
sectors within SECTOR_RADIUS of the initial star's sector (a block of 2 * SECTOR_RADIUS + 1 sectors on each side, 5 x 5
x 5 for a radius of 2) are generated. Each sector draws its stars from a seed derived from its quadrant, its district
and its index, so the same galaxy always gives the same stars. A star has a float position inside its sector and
occupies the integer cell (1 ly) that contains it; no two stars share a cell, and its seed comes from that cell.

A fixed star is only its seed and position, plus the properties Star derives from its seed: no orbits, planets or moons.
Its StellarSystem takes its seed from the star's, so the system and the fixed star describe the same star.

Nothing is saved for a fixed star: it is regenerated from the galaxy seed whenever it is needed.
"""

import logging
import math
import random
from collections import Counter
from itertools import product

from galaxies import seeds
from galaxies.constants import (
    DISTRICT_SIZE,
    FIXED_STARS_MEAN_PER_SECTOR,
    INITIAL_STAR_POSITION,
    LIGHT_YEAR_M,
    QUADRANT_SIZE,
    SECTOR_RADIUS,
    SECTOR_SIZE,
)
from galaxies.star import Star, cell_of

logger = logging.getLogger(__name__)

REPORT_RADIUS = 40.0  # ly: the radius around the initial star in which the log counts the stars


def region_of(position: tuple[float, float, float], size: int) -> tuple[int, int, int]:
    """The index of the cube of `size` ly, aligned to multiples of it, that contains the position."""
    return (math.floor(position[0] / size), math.floor(position[1] / size), math.floor(position[2] / size))


def _sector_origin(sector: tuple[int, int, int]) -> tuple[float, float, float]:
    return (float(sector[0] * SECTOR_SIZE), float(sector[1] * SECTOR_SIZE), float(sector[2] * SECTOR_SIZE))


def _sector_seed(galaxy_seed: float, sector: tuple[int, int, int]) -> int:
    """The seed of a sector, through the quadrant and the district that contain it."""
    origin: tuple[float, float, float] = _sector_origin(sector)
    quadrant_seed: int = seeds.derive(galaxy_seed, 'quadrant', *region_of(origin, QUADRANT_SIZE))
    district_seed: int = seeds.derive(quadrant_seed, 'district', *region_of(origin, DISTRICT_SIZE))
    return seeds.derive(district_seed, 'sector', *sector)


def _poisson(my_random: random.Random, mean: float) -> int:
    """A Poisson-distributed count with the given mean (Knuth's multiplication method)."""
    limit: float = math.exp(-mean)
    count: int = 0
    product_of_uniforms: float = my_random.random()
    while product_of_uniforms > limit:
        count += 1
        product_of_uniforms *= my_random.random()
    return count


def _generate_sector(galaxy_seed: float, sector: tuple[int, int, int],
                     used_cells: set[tuple[int, int, int]]) -> tuple[list[Star], int]:
    """The random stars of one sector, and the number skipped because their cell was taken. `used_cells` holds the
    cells taken so far, in the whole region; it is updated."""
    sector_seed: int = _sector_seed(galaxy_seed, sector)
    my_random: random.Random = random.Random(sector_seed)
    origin: tuple[float, float, float] = _sector_origin(sector)
    stars: list[Star] = []
    skipped: int = 0
    for _ in range(_poisson(my_random, FIXED_STARS_MEAN_PER_SECTOR)):
        position: tuple[float, float, float] = tuple(c + my_random.random() * SECTOR_SIZE for c in origin)
        if cell_of(position) in used_cells:
            skipped += 1  # one attempt only: a collision is rare, and losing the star is harmless
            continue
        used_cells.add(cell_of(position))
        stars.append(Star(seeds.derive(sector_seed, 'star', *cell_of(position)), position))
    return stars, skipped


def stellar_position(position: tuple[float, float, float]) -> tuple[float, float, float]:
    """A galactic position (in ly) in the stellar frame of the initial star, in meters. The stellar frame has x right,
    y up and z forward (north); galactic x is forward, y right and z up, so the stellar frame takes galactic (y, z, x).
    That is a cyclic permutation, a rotation, so nothing is mirrored. The initial star is the origin."""
    dx, dy, dz = (p - i for p, i in zip(position, INITIAL_STAR_POSITION))
    return (dy * LIGHT_YEAR_M, dz * LIGHT_YEAR_M, dx * LIGHT_YEAR_M)


def generate_region(galaxy_seed: float) -> list[Star]:
    """The fixed stars of the region around the initial star, the initial star included (always a G star). Logs
    aggregate results."""
    centre: tuple[int, int, int] = region_of(INITIAL_STAR_POSITION, SECTOR_SIZE)
    initial_star_seed: int = seeds.derive(_sector_seed(galaxy_seed, centre), 'star', *cell_of(INITIAL_STAR_POSITION))
    initial_star: Star = Star(initial_star_seed, INITIAL_STAR_POSITION, Star.Type.G)
    stars: list[Star] = [initial_star]
    used_cells: set[tuple[int, int, int]] = {cell_of(INITIAL_STAR_POSITION)}

    per_sector_counts: list[int] = []
    skipped_total: int = 0
    for offset in product(range(-SECTOR_RADIUS, SECTOR_RADIUS + 1), repeat=3):
        sector = (centre[0] + offset[0], centre[1] + offset[1], centre[2] + offset[2])
        sector_stars, skipped = _generate_sector(galaxy_seed, sector, used_cells)
        per_sector_counts.append(len(sector_stars))
        stars.extend(sector_stars)
        skipped_total += skipped

    _log_summary(galaxy_seed, stars, per_sector_counts, skipped_total)
    return stars


def _log_summary(galaxy_seed: float, stars: list[Star], per_sector_counts: list[int], skipped: int) -> None:
    within: int = sum(1 for star in stars if math.dist(star.position, INITIAL_STAR_POSITION) <= REPORT_RADIUS)
    types: Counter = Counter(star.type.name for star in stars)
    side: int = 2 * SECTOR_RADIUS + 1
    logger.info(
        f"Fixed stars of galaxy {galaxy_seed}: {len(stars)} stars (the initial one included) in {side ** 3} sectors of "
        f"{SECTOR_SIZE} ly; per sector min {min(per_sector_counts)}, "
        f"mean {sum(per_sector_counts) / len(per_sector_counts):.1f}, "
        f"max {max(per_sector_counts)}."
    )
    logger.info(f"Fixed stars skipped because their cell was taken: {skipped}.")
    logger.info(f"Fixed stars within {REPORT_RADIUS} ly of the initial star: {within}.")
    logger.info("Fixed stars by type: " + ", ".join(f"{name} {types[name]}" for name in sorted(types)) + ".")
