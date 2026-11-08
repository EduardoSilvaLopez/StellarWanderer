"""The ground of a rocky world: its height at a point of the surface, from the world's seed alone.

The height is a function of the direction from the world's centre, so it wraps at the anti-meridian without a seam and
the same seed gives the same ground whatever is visited or drawn. The surface frame is flat (longitude and latitude in
metres), so a point is taken at the angles longitude / radius and latitude / radius; as in the Km2 grid, the ground is
stretched in longitude towards the poles.

Nothing of the game is imported here on purpose: the terrain meshes are built in helper processes, which load only this
module (and numpy). A world with no relief is flat: its ground is the datum, the sphere of its radius, everywhere.
A point has one height (`Terrain.height`); many points at once (`heights`) and the regular grid of a mesh
(`grid_heights`) give the same numbers, the grid with its smooth octaves taken from a coarse sample of it, within
centimetres.

Where people build, the ground is graded: a platform (`add_platform`) levels a disc to the natural height at its centre,
and a smooth apron leads from the disc to the natural ground. The platforms are part of the terrain's identity (the
helpers that build the meshes are told them), and a mesh too coarse to show one is left as it was.
"""

from __future__ import annotations
import math
from typing import Tuple

import numpy as np

BASE_CELL = 1.59275e6    # m: the lattice cell of the first octave; each octave halves it
MASK_CELL = 3747647.0588    # m: the cell of the noise that places the mountains
GROUND_DETAIL = 1.0      # m: the finest horizontal detail of the height, which sets the number of octaves
MAX_OCTAVES = 26
PLAIN_AMPLITUDE = 2000.0  # m: the hills and basins, in the first octave
PLAIN_GAIN = 0.55         # the amplitude of an octave over the one before
RIDGE_FIRST = 3           # the first octave of the mountains: its cell is about 200 km
RIDGE_AMPLITUDE = 3500.0  # m
RIDGE_GAIN = 0.55
MOUNTAIN_EDGES = (0.40, 0.65)   # the mask noise between these makes mountains: about 40% of a world, with soft edges
COARSE_SAMPLES = 9        # a grid's smooth octaves are sampled on this many points a side and interpolated
COARSE_RATIO = 16.0       # an octave is smooth over a grid when its cell is this many grid widths wide
PLATFORM_FLAT = 75.0      # m: the graded disc's radius (holds the pads and the annex of the largest outpost)
PLATFORM_APRON = 100.0    # m: the width of the smooth slope from the disc to the natural ground
PLATFORM_MAX_STEP = 16.0  # m: a mesh with cells wider than this does not show the platforms

_MASK32 = 0xFFFFFFFF
_P1, _P2, _P3, _C1 = 374761393, 668265263, 2246822519, 2246822519


# region One point
def _noise(x: float, y: float, z: float, salt: int) -> float:
    """3D value noise in [0, 1) at a point; a lattice hash with a smooth blend between the lattice points."""
    fx, fy, fz = math.floor(x), math.floor(y), math.floor(z)
    tx, ty, tz = x - fx, y - fy, z - fz
    tx = tx * tx * tx * (tx * (tx * 6.0 - 15.0) + 10.0)
    ty = ty * ty * ty * (ty * (ty * 6.0 - 15.0) + 10.0)
    tz = tz * tz * tz * (tz * (tz * 6.0 - 15.0) + 10.0)
    s = salt & _MASK32
    ax = [((int(fx) + k) * _P1 & _MASK32) ^ s for k in (0, 1)]
    ay = [(int(fy) + k) * _P2 & _MASK32 for k in (0, 1)]
    az = [(int(fz) + k) * _P3 & _MASK32 for k in (0, 1)]

    def corner(a: int, b: int, c: int) -> float:
        h = ((ax[a] ^ ay[b] ^ az[c]) ^ ((ax[a] ^ ay[b] ^ az[c]) >> 15)) * _C1 & _MASK32
        return (h ^ (h >> 13)) * (1.0 / 4294967296.0)

    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    return lerp(lerp(lerp(corner(0, 0, 0), corner(1, 0, 0), tx), lerp(corner(0, 1, 0), corner(1, 1, 0), tx), ty),
                lerp(lerp(corner(0, 0, 1), corner(1, 0, 1), tx), lerp(corner(0, 1, 1), corner(1, 1, 1), tx), ty), tz)


def octave_count(detail: float) -> int:
    """The octaves whose cell (half of it is the finest feature) a mesh of spacing `detail` metres can still show."""
    return max(1, min(MAX_OCTAVES, int(math.log2(BASE_CELL / (2.0 * detail))) + 1))


def natural_height(direction: Tuple[float, float, float], seed: int, radius: float,
                   detail: float = GROUND_DETAIL) -> float:
    """The height in metres of the full relief at a unit direction from the centre of a world of `radius` metres: hills
    and basins (plain noise from the first octave) and, over about 40% of the world, mountains (ridged noise, each
    octave weighted by the one before). The octaves go down to `detail` metres."""
    dx, dy, dz = direction
    scale = radius / MASK_CELL
    t = min(1.0, max(0.0, (_noise(dx * scale, dy * scale, dz * scale, seed + 7919) - MOUNTAIN_EDGES[0])
                     / (MOUNTAIN_EDGES[1] - MOUNTAIN_EDGES[0])))
    mountains = t * t * (3.0 - 2.0 * t)
    plain = ridged = 0.0
    weight = 1.0
    for octave in range(octave_count(detail)):
        scale = radius * 2.0 ** octave / BASE_CELL
        n = _noise(dx * scale, dy * scale, dz * scale, seed + octave * 40503)
        plain += (n * 2.0 - 1.0) * (PLAIN_AMPLITUDE * PLAIN_GAIN ** octave)
        if octave >= RIDGE_FIRST:
            r = 1.0 - abs(n * 2.0 - 1.0)
            r = r * r * weight
            weight = min(1.0, max(0.0, r * 2.0))
            ridged += r * (RIDGE_AMPLITUDE * RIDGE_GAIN ** (octave - RIDGE_FIRST))
    return plain + ridged * mountains
# endregion


# region Many points
_U1, _U2, _U3, _UC = np.uint32(_P1), np.uint32(_P2), np.uint32(_P3), np.uint32(_C1)
_SHIFT15, _SHIFT13 = np.uint32(15), np.uint32(13)


def _mix(h: np.ndarray) -> np.ndarray:
    h = (h ^ (h >> _SHIFT15)) * _UC
    return (h ^ (h >> _SHIFT13)).astype(np.float64) * (1.0 / 4294967296.0)


def _lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    return a + (b - a) * t


def _noise_array(q: np.ndarray, salt: int) -> np.ndarray:
    """`_noise` at points q of shape (..., 3)."""
    base = np.floor(q)
    t = q - base
    t = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    i = base.astype(np.int64)
    j = i + 1
    s = np.uint32(salt & _MASK32)
    ax0 = (i[..., 0].astype(np.uint32) * _U1) ^ s
    ax1 = (j[..., 0].astype(np.uint32) * _U1) ^ s
    ay0, ay1 = i[..., 1].astype(np.uint32) * _U2, j[..., 1].astype(np.uint32) * _U2
    az0, az1 = i[..., 2].astype(np.uint32) * _U3, j[..., 2].astype(np.uint32) * _U3
    tx, ty, tz = t[..., 0], t[..., 1], t[..., 2]
    y0z0, y1z0, y0z1, y1z1 = ay0 ^ az0, ay1 ^ az0, ay0 ^ az1, ay1 ^ az1
    low = _lerp(_lerp(_mix(ax0 ^ y0z0), _mix(ax1 ^ y0z0), tx), _lerp(_mix(ax0 ^ y1z0), _mix(ax1 ^ y1z0), tx), ty)
    high = _lerp(_lerp(_mix(ax0 ^ y0z1), _mix(ax1 ^ y0z1), tx), _lerp(_mix(ax0 ^ y1z1), _mix(ax1 ^ y1z1), tx), ty)
    return _lerp(low, high, tz)


class _Fractal:
    """The running sums of the hills and the mountains over many points; they continue from one octave range to the
    next, so that the smooth octaves of a grid can be summed on a coarse sample and the rest on the grid itself."""

    def __init__(self, shape: Tuple[int, ...]) -> None:
        self.plain = np.zeros(shape)
        self.ridged = np.zeros(shape)
        self.weight = np.ones(shape)

    def add_octaves(self, directions: np.ndarray, seed: int, radius: float, first: int, last: int) -> None:
        for octave in range(first, last):
            n = _noise_array(directions * (radius * 2.0 ** octave / BASE_CELL), seed + octave * 40503)
            self.plain += (n * 2.0 - 1.0) * (PLAIN_AMPLITUDE * PLAIN_GAIN ** octave)
            if octave >= RIDGE_FIRST:
                r = 1.0 - np.abs(n * 2.0 - 1.0)
                r = r * r * self.weight
                self.weight = np.clip(r * 2.0, 0.0, 1.0)
                self.ridged += r * (RIDGE_AMPLITUDE * RIDGE_GAIN ** (octave - RIDGE_FIRST))

    def height(self, mountains: np.ndarray) -> np.ndarray:
        return self.plain + self.ridged * mountains


def _mountain_mask(directions: np.ndarray, seed: int, radius: float) -> np.ndarray:
    n = _noise_array(directions * (radius / MASK_CELL), seed + 7919)
    t = np.clip((n - MOUNTAIN_EDGES[0]) / (MOUNTAIN_EDGES[1] - MOUNTAIN_EDGES[0]), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _directions(longitudes: np.ndarray, latitudes: np.ndarray, radius: float) -> np.ndarray:
    """The unit directions (..., 3) of points of the flat surface frame, as Terrain.height takes them."""
    lon, lat = longitudes / radius, latitudes / radius
    return np.stack([np.cos(lat) * np.cos(lon), np.sin(lat), np.cos(lat) * np.sin(lon)], axis=-1)
# endregion


# region A grid
_COARSE_WEIGHTS: dict = {}


def _coarse_weights(count: int) -> np.ndarray:
    """(count, COARSE_SAMPLES): the linear interpolation from the coarse samples to `count` evenly spaced points."""
    if count not in _COARSE_WEIGHTS:
        weights = np.zeros((count, COARSE_SAMPLES))
        position = np.arange(count) * (COARSE_SAMPLES - 1) / max(1, count - 1)
        lower = np.minimum(position.astype(int), COARSE_SAMPLES - 2)
        fraction = position - lower
        weights[np.arange(count), lower] = 1.0 - fraction
        weights[np.arange(count), lower + 1] = fraction
        _COARSE_WEIGHTS[count] = weights
    return _COARSE_WEIGHTS[count]


def _natural_grid(seed: int, radius: float, xs: np.ndarray, zs: np.ndarray, detail: float) -> np.ndarray:
    """The full relief at the grid xs x zs (metres, regular), shape (len(xs), len(zs)). The octaves much wider than the
    grid are smooth across it: they are summed on COARSE_SAMPLES points a side and interpolated, and only the finer ones
    are evaluated at every point (the coarse sum differs from the exact one by millimetres, under the finest detail)."""
    octaves = octave_count(detail)
    extent = max(float(xs[-1] - xs[0]), float(zs[-1] - zs[0]), detail)
    smooth_width = COARSE_RATIO * extent
    coarse = int(math.log2(BASE_CELL / smooth_width)) + 1 if smooth_width < BASE_CELL else 0
    coarse = max(0, min(coarse, octaves))
    mask_is_coarse = smooth_width <= MASK_CELL
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    directions = _directions(gx, gz, radius)
    fractal = _Fractal(gx.shape)
    if coarse == 0 and not mask_is_coarse:
        fractal.add_octaves(directions, seed, radius, 0, octaves)
        return fractal.height(_mountain_mask(directions, seed, radius))
    wx, wz = _coarse_weights(len(xs)), _coarse_weights(len(zs))
    cx, cz = np.meshgrid(np.linspace(xs[0], xs[-1], COARSE_SAMPLES), np.linspace(zs[0], zs[-1], COARSE_SAMPLES),
                         indexing="ij")
    coarse_directions = _directions(cx, cz, radius)
    coarse_fractal = _Fractal(cx.shape)
    coarse_fractal.add_octaves(coarse_directions, seed, radius, 0, coarse)
    fractal.plain = wx @ coarse_fractal.plain @ wz.T
    fractal.ridged = wx @ coarse_fractal.ridged @ wz.T
    fractal.weight = wx @ coarse_fractal.weight @ wz.T
    fractal.add_octaves(directions, seed, radius, coarse, octaves)
    mask = (wx @ _mountain_mask(coarse_directions, seed, radius) @ wz.T if mask_is_coarse
            else _mountain_mask(directions, seed, radius))
    return fractal.height(mask)
# endregion


def _graded(heights: np.ndarray, xs: np.ndarray, zs: np.ndarray, platforms: Tuple[Tuple[float, float, float], ...]
            ) -> np.ndarray:
    """`heights` at the points (xs, zs) with each platform's grading: the level inside the disc, the natural ground
    beyond the apron, a smooth blend between."""
    for x, z, level in platforms:
        distance = np.hypot(xs - x, zs - z)
        if distance.min() >= PLATFORM_FLAT + PLATFORM_APRON:
            continue
        t = np.clip((distance - PLATFORM_FLAT) / PLATFORM_APRON, 0.0, 1.0)
        heights = level + (heights - level) * (t * t * (3.0 - 2.0 * t))
    return heights


class Terrain:
    """The ground of one world. `height` is metres above the datum; `relief` scales it, 0 for a flat world."""

    def __init__(self, seed: int, radius: float, relief: float = 0.0,
                 platforms: Tuple[Tuple[float, float, float], ...] = ()) -> None:
        self.seed = seed
        self.radius = radius
        self.relief = relief
        self.platforms = platforms   # (longitude, latitude, level) of each graded site
        self._last: Tuple[float, float, float] = (math.nan, math.nan, 0.0)   # a frame asks the same point several times

    def natural(self, longitude: float, latitude: float) -> float:
        """The height of the ground as nature made it, without the platforms."""
        lon, lat = longitude / self.radius, latitude / self.radius
        direction = (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))
        return self.relief * natural_height(direction, self.seed, self.radius)

    def add_platform(self, longitude: float, latitude: float) -> None:
        """Grades a site, levelled to the natural height at its centre. Before anything is drawn from this terrain."""
        if self.relief == 0.0 or any(p[:2] == (longitude, latitude) for p in self.platforms):
            return
        self.platforms += ((float(longitude), float(latitude), self.natural(longitude, latitude)),)
        self._last = (math.nan, math.nan, 0.0)

    def height(self, longitude: float, latitude: float) -> float:
        """The ground's height in metres above the datum at a point of the surface frame (longitude: x east, latitude:
        z north, both in metres from the origin)."""
        if self.relief == 0.0:
            return 0.0
        if (longitude, latitude) == self._last[:2]:
            return self._last[2]
        height = self.natural(longitude, latitude)
        if self.platforms:
            height = float(_graded(np.float64(height), np.float64(longitude), np.float64(latitude), self.platforms))
        self._last = (longitude, latitude, height)
        return height

    def height_for_mesh(self, longitude: float, latitude: float, detail: float) -> float:
        """`height` with only the octaves a mesh of `detail` metres shows, and no cache: the height of a chunk's centre,
        which only has to agree with the chunk."""
        if self.relief == 0.0:
            return 0.0
        lon, lat = longitude / self.radius, latitude / self.radius
        direction = (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))
        height = self.relief * natural_height(direction, self.seed, self.radius, detail)
        if self.platforms and detail <= PLATFORM_MAX_STEP:
            height = float(_graded(np.float64(height), np.float64(longitude), np.float64(latitude), self.platforms))
        return height

    def heights(self, longitudes: np.ndarray, latitudes: np.ndarray) -> np.ndarray:
        """`height` at many points at once (arrays of one shape): what the rocks on the ground are placed by."""
        if self.relief == 0.0:
            return np.zeros(np.shape(longitudes))
        directions = _directions(np.asarray(longitudes, dtype=np.float64), np.asarray(latitudes, dtype=np.float64),
                                 self.radius)
        fractal = _Fractal(directions.shape[:-1])
        fractal.add_octaves(directions, self.seed, self.radius, 0, octave_count(GROUND_DETAIL))
        heights = self.relief * fractal.height(_mountain_mask(directions, self.seed, self.radius))
        if self.platforms:
            heights = _graded(heights, np.asarray(longitudes, dtype=np.float64),
                              np.asarray(latitudes, dtype=np.float64), self.platforms)
        return heights

    def grid_heights(self, x0: float, z0: float, step: float, count_x: int, count_z: int) -> np.ndarray:
        """The heights at the regular grid x0 + i * step, z0 + j * step: shape (count_x, count_z), the detail of a mesh
        of `step` metres (octaves finer than that are left out, as a mesh cannot show them)."""
        if self.relief == 0.0:
            return np.zeros((count_x, count_z))
        xs = x0 + step * np.arange(count_x)
        zs = z0 + step * np.arange(count_z)
        heights = self.relief * _natural_grid(self.seed, self.radius, xs, zs, step)
        if self.platforms and step <= PLATFORM_MAX_STEP:
            gx, gz = np.meshgrid(xs, zs, indexing="ij")
            heights = _graded(heights, gx, gz, self.platforms)
        return heights
