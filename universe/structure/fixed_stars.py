"""The stars of the galaxy, made on demand from the galaxy seed and kept in memory (StarField).

Galactic space is cut into sectors: cubes of SECTOR_SIZE ly, aligned to multiples of it. Sectors sit in districts
(DISTRICT_SIZE ly) and districts in quadrants (QUADRANT_SIZE ly); those two levels only feed the seeds (see seeds.py).
A sector draws a Poisson count of stars (FIXED_STARS_MEAN_PER_SECTOR) at random positions inside itself. A star
occupies the integer cell (1 ly) that contains it, and its seed comes from that cell. A cell lies inside one sector,
so two sectors never clash; inside a sector, a star that lands on a cell already taken is lost (rare, and harmless).

A sector is made the first time something asks for it and then kept. Its stars depend only on the galaxy seed and its
own index, never on what was asked before, so the galaxy reads the same in any order. Nothing is saved.

The sky shows the sectors within SECTOR_RADIUS of the initial star's sector (Galaxy.fixed_star_positions). The history
reads the stars wherever its settling systems look (universe/society/politics/settling.py), so any sector can be asked
for.

A fixed star is only its seed and position, plus what Star derives from its seed: no orbits, planets or moons. Its
StellarSystem takes its seed from the star's, so the system and the fixed star describe the same star.
"""

from __future__ import annotations

import math
import random
from itertools import product
from typing import Optional

from universe.bodies.star import Star, cell_of
from universe.structure import seeds
from universe.structure.constants import (
    DISTRICT_SIZE,
    FIXED_STARS_MEAN_PER_SECTOR,
    LIGHT_YEAR_M,
    QUADRANT_SIZE,
    SECTOR_SIZE,
)

Sector = tuple[int, int, int]
Cell = tuple[int, int, int]
Position = tuple[float, float, float]
MAX_SEARCH_STEPS = 200  # the nearest star of a type is looked for in shells of SECTOR_SIZE: 200 shells is 4000 ly


def region_of(position: tuple[float, float, float], size: int) -> tuple[int, int, int]:
    """The index of the cube of `size` ly, aligned to multiples of it, that contains the position."""
    return (math.floor(position[0] / size), math.floor(position[1] / size), math.floor(position[2] / size))


def _sector_origin(sector: Sector) -> Position:
    return (float(sector[0] * SECTOR_SIZE), float(sector[1] * SECTOR_SIZE), float(sector[2] * SECTOR_SIZE))


def _sector_seed(galaxy_seed: int, sector: Sector) -> int:
    """The seed of a sector, through the quadrant and the district that contain it."""
    origin: Position = _sector_origin(sector)
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


def _generate_sector(galaxy_seed: int, sector: Sector) -> list[Star]:
    """The stars of one sector, in the order they were drawn."""
    sector_seed: int = _sector_seed(galaxy_seed, sector)
    my_random: random.Random = random.Random(sector_seed)
    origin: Position = _sector_origin(sector)
    stars: list[Star] = []
    taken: set[Cell] = set()
    for _ in range(_poisson(my_random, FIXED_STARS_MEAN_PER_SECTOR)):
        position: Position = tuple(c + my_random.random() * SECTOR_SIZE for c in origin)
        cell: Cell = cell_of(position)
        if cell in taken:
            continue
        taken.add(cell)
        stars.append(Star(seeds.derive(sector_seed, 'star', *cell), position))
    return stars


def _distance_to_sector(point: Position, sector: Sector) -> float:
    """The distance (ly) from a point to the nearest point of a sector; 0 when the point is inside it."""
    origin: Position = _sector_origin(sector)
    nearest: Position = tuple(min(max(p, lo), lo + SECTOR_SIZE) for p, lo in zip(point, origin))
    return math.dist(point, nearest)


def stellar_position(position: Position, origin: Position) -> Position:
    """A galactic position (in ly) in the stellar frame of the star at `origin`, in meters. The stellar frame has x
    right, y up and z forward (north); galactic x is forward, y right and z up, so the stellar frame takes galactic
    (y, z, x). That is a cyclic permutation, a rotation, so nothing is mirrored. The star at `origin` is the origin."""
    dx, dy, dz = (p - o for p, o in zip(position, origin))
    return (dy * LIGHT_YEAR_M, dz * LIGHT_YEAR_M, dx * LIGHT_YEAR_M)


class StarField:
    """The stars of one galaxy seed, sector by sector, made when asked for and kept."""

    def __init__(self, galaxy_seed: int) -> None:
        self.galaxy_seed: int = galaxy_seed
        self._sectors: dict[Sector, tuple[list[Star], dict[Cell, Star]]] = {}

    def sector_of(self, position: Position) -> Sector:
        """The sector that contains a galactic position (in ly)."""
        return region_of(position, SECTOR_SIZE)

    def stars_of(self, sector: Sector) -> list[Star]:
        """The stars of a sector, made if they were not yet."""
        return self._made(sector)[0]

    def star_at(self, cell: Cell) -> Optional[Star]:
        """The star that occupies a cell, or None if no star is there."""
        return self._made(self.sector_of(cell))[1].get(cell)

    def stars_within(self, centre: Position, radius: float) -> list[Star]:
        """The stars at most `radius` ly from `centre`. The sectors are visited in a fixed order, and so are their
        stars, so the list is the same whatever was asked before."""
        low: Sector = self.sector_of(tuple(c - radius for c in centre))
        high: Sector = self.sector_of(tuple(c + radius for c in centre))
        found: list[Star] = []
        for sector in product(*(range(lo, hi + 1) for lo, hi in zip(low, high))):
            if _distance_to_sector(centre, sector) > radius:
                continue
            found.extend(star for star in self.stars_of(sector) if math.dist(star.position, centre) <= radius)
        return found

    def stars_around(self, sector: Sector, radius_sectors: int) -> list[Star]:
        """The stars of the block of sectors that is `radius_sectors` sectors wide on each side of `sector`."""
        found: list[Star] = []
        for offset in product(range(-radius_sectors, radius_sectors + 1), repeat=3):
            found.extend(self.stars_of((sector[0] + offset[0], sector[1] + offset[1], sector[2] + offset[2])))
        return found

    def nearest_of_type(self, centre: Position, star_type: Star.Type) -> Star:
        """The star of a type nearest to `centre`. The search grows in shells of one sector: once a star of the type
        is found at a distance d, every star nearer than d is inside the shell already searched, so the nearest is
        exact."""
        for step in range(1, MAX_SEARCH_STEPS + 1):
            candidates: list[Star] = [star for star in self.stars_within(centre, step * SECTOR_SIZE)
                                      if star.type is star_type]
            if candidates:
                return min(candidates, key=lambda star: math.dist(star.position, centre))
        raise RuntimeError(f"No star of type {star_type.name} within {MAX_SEARCH_STEPS * SECTOR_SIZE} ly of {centre}.")

    def _made(self, sector: Sector) -> tuple[list[Star], dict[Cell, Star]]:
        made = self._sectors.get(sector)
        if made is None:
            stars: list[Star] = _generate_sector(self.galaxy_seed, sector)
            made = (stars, {star.cell: star for star in stars})
            self._sectors[sector] = made
        return made
