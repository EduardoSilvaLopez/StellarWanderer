"""How rocks with an adjective look: valuable minerals, such as a pilot could find in a collection (banded agate, lapis lazuli,
malachite, amethyst, gold in quartz). Nothing glows or moves: the minerals only have colours and patterns.

Such a rock has the shape of any rock (graphics/rock_shape.py), but each of its faces is cut into SPLITS * SPLITS smaller
ones, and each small face takes the colour of the mineral at its place, from a noise in the rock's own coordinates, so the
pattern turns with the rock and no two rocks are alike. Every adjective has a `Look`; one the table does not know gets
FALLBACK. Used by rock_batches.py (the 3D view) and by the scanner instrument.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from .rock_shape import rock_meshes

Colour = Tuple[int, int, int]

SPLITS = 4  # each triangle becomes SPLITS * SPLITS (16): a rock has 1280 faces
FACET_JITTER = 0.04  # share by which a small face may differ in brightness: the glint of crystal faces, fixed


@dataclass(frozen=True)
class Look:
    """The minerals of a rock. `gradient` is the body, which takes `bands` rings (concentric bands, as in agate) or, with
    `bands` of 0, irregular clouds. Veins and flecks (one colour each, or None) lie on top."""
    gradient: Sequence[Colour]
    bands: int = 0
    veins: Optional[Colour] = None
    vein_strength: float = 0.8  # how much of the vein colour shows in the middle of a vein
    vein_width: float = 0.04  # in noise units: the thinner, the finer the veins
    flecks: Optional[Colour] = None
    fleck_share: float = 0.05  # share of the surface covered by flecks


LOOKS: Dict[str, Look] = {
    # Banded agate: rings of rust, orange and cream.
    'weird': Look(gradient=((140, 55, 38), (205, 125, 68), (238, 226, 204), (125, 52, 40)), bands=4),
    # Lapis lazuli: deep blue with flecks of pyrite and a few white calcite veins.
    'mysterious': Look(gradient=((22, 42, 118), (38, 70, 152), (20, 30, 86)), veins=(205, 205, 212), vein_strength=0.4,
                       vein_width=0.04, flecks=(196, 164, 62), fleck_share=0.07),
    # Malachite: green rings, darker and lighter.
    'strange': Look(gradient=((16, 78, 48), (62, 152, 96), (12, 56, 38), (84, 168, 112)), bands=5),
    # Amethyst: violet crystal, crossed by white quartz.
    'exotic': Look(gradient=((104, 66, 146), (152, 102, 188), (82, 48, 118)), veins=(228, 222, 238), vein_strength=0.7,
                   vein_width=0.035),
    # Native gold in quartz: pale stone with gold in its cracks.
    'rare': Look(gradient=((214, 210, 200), (236, 233, 226), (196, 192, 184)), veins=(214, 170, 52), vein_strength=0.95,
                 vein_width=0.05, flecks=(222, 180, 60), fleck_share=0.04),
}
# Dark stone with white veins, like marble.
FALLBACK = Look(gradient=((66, 66, 72), (98, 98, 104), (56, 56, 62)), veins=(226, 226, 226), vein_strength=0.85, vein_width=0.04)

_cache: Dict[Tuple[int, str], Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def look_of(adjective: str) -> Look:
    return LOOKS.get(adjective, FALLBACK)


def special_mesh(shape_seed: int, adjective: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(triangles (F, 3, 3), normals (F, 3), colours (F, 3) in 0-255 floats) of a rock with an adjective, in local unit
    coordinates, F being 80 * SPLITS ** 2. Remembered: a rock's mesh is asked for in every rebuild of a batch."""
    key = (shape_seed, adjective)
    if key not in _cache:
        triangles, normals, _ = rock_meshes([shape_seed])
        triangles, normals = triangles[0], normals[0]
        for _ in range(SPLITS // 2):  # each pass cuts every triangle into four
            a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
            ab, bc, ca = (a + b) / 2.0, (b + c) / 2.0, (c + a) / 2.0
            triangles = np.concatenate([np.stack(corners, axis=1) for corners in
                                        ((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca))])
            normals = np.tile(normals, (4, 1))
        _cache[key] = (triangles, normals, _colours(triangles.mean(axis=1), shape_seed, look_of(adjective)))
    return _cache[key]


def _hash(ix: np.ndarray, iy: np.ndarray, iz: np.ndarray, seed: int) -> np.ndarray:
    """Numbers in [0, 1), one per lattice point (splitmix64 of the point and the seed)."""
    with np.errstate(over='ignore'):
        x = (ix.astype(np.uint64) * np.uint64(73856093) ^ iy.astype(np.uint64) * np.uint64(19349663)
             ^ iz.astype(np.uint64) * np.uint64(83492791) ^ np.uint64(seed) * np.uint64(2654435761))
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        x = x ^ (x >> np.uint64(31))
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def _noise(points: np.ndarray, seed: int) -> np.ndarray:
    """Smooth value noise in [0, 1) at (N, 3) points: random values on a lattice, blended between."""
    cell = np.floor(points)
    fraction = points - cell
    fraction = fraction * fraction * (3.0 - 2.0 * fraction)
    ix, iy, iz = (cell[:, k].astype(np.int64) for k in range(3))
    fx, fy, fz = fraction[:, 0], fraction[:, 1], fraction[:, 2]

    def corner(dx: int, dy: int, dz: int) -> np.ndarray:
        return _hash(ix + dx, iy + dy, iz + dz, seed)

    low = corner(0, 0, 0) * (1 - fx) + corner(1, 0, 0) * fx
    low_y = corner(0, 1, 0) * (1 - fx) + corner(1, 1, 0) * fx
    high = corner(0, 0, 1) * (1 - fx) + corner(1, 0, 1) * fx
    high_y = corner(0, 1, 1) * (1 - fx) + corner(1, 1, 1) * fx
    return (low * (1 - fy) + low_y * fy) * (1 - fz) + (high * (1 - fy) + high_y * fy) * fz


def _fractal(points: np.ndarray, seed: int) -> np.ndarray:
    """Three octaves of noise, in [0, 1): broad shapes with finer detail on them."""
    return (_noise(points, seed) * 4 + _noise(points * 2.0, seed + 1) * 2 + _noise(points * 4.0, seed + 2)) / 7.0


def _colours(centres: np.ndarray, shape_seed: int, look: Look) -> np.ndarray:
    """The colour of the mineral at each of the (N, 3) face centres, in 0-255 floats."""
    rng = np.random.default_rng(shape_seed)
    seed = int(rng.integers(1, 1 << 30))
    points = centres * 1.6 + rng.uniform(-50.0, 50.0, 3)  # the rock's own place in the noise
    if look.bands:
        # Rings around a centre of the rock's own, bent by noise so that they are not circles.
        radius = np.linalg.norm(centres - rng.uniform(-0.6, 0.6, 3), axis=1)
        t = 0.5 + 0.5 * np.sin(2.0 * np.pi * (radius * look.bands * 0.5 + 1.3 * _fractal(points, seed)))
    else:
        t = np.clip((_fractal(points * 1.4, seed) - 0.5) * 3.0 + 0.5, 0.0, 1.0)

    stops = np.array(look.gradient, dtype=np.float64)
    position = t * (len(stops) - 1)
    lower = np.minimum(position.astype(int), len(stops) - 2)
    colour = stops[lower] + (stops[lower + 1] - stops[lower]) * (position - lower)[:, None]

    if look.veins is not None:
        # A vein runs where the noise crosses its middle value: thin, branching lines.
        vein = np.clip(1.0 - np.abs(_fractal(points * 2.2, seed + 10) - 0.5) / look.vein_width, 0.0, 1.0)
        colour += (np.array(look.veins) - colour) * (look.vein_strength * vein)[:, None]
    if look.flecks is not None:
        fleck = _noise(points * 9.0, seed + 20) > 1.0 - look.fleck_share
        colour[fleck] += (np.array(look.flecks) - colour[fleck]) * 0.9
    jitter = 1.0 + FACET_JITTER * (2.0 * _hash(np.arange(len(colour)), np.zeros(len(colour), dtype=np.int64),
                                               np.zeros(len(colour), dtype=np.int64), seed) - 1.0)
    return np.clip(colour * jitter[:, None], 0.0, 255.0)
