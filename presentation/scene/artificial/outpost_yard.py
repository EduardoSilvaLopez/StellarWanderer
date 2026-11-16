"""What a size 4 outpost has around its pads and on its old roof, as plain geometry (no GL, so the preview in
temp/ uses it too; graphics/outposts.py draws it): piles of small metal crates and cages on the concrete, antenna masts on the old
building's roof, and the stand of the propaganda billboard.

Points are in the outpost's frame, in metres: x along the width, y up from the ground, z on the door axis. Every face
comes with its outward normal, as the outposts are lit face by face. Each face costs the PyOpenGL calls of one quad,
so the counts are kept low (about 45 faces of crates, 45 of masts and 16 of billboard).
"""

from __future__ import annotations
import functools
import math
import random
from typing import List, Tuple

from .annex_dish import SQUARE, Face, Point

BILLBOARD_HEIGHT = 8.0  # m, of the poster
BILLBOARD_BASE = 2.0  # m, from the ground to the poster's lower edge
BILLBOARD_THICKNESS = 0.4  # m
BILLBOARD_BORDER = 0.25  # m, of frame around the poster
POST_SIZE = 0.5  # m
MAST_SIZE = 0.14  # m
BAR_SIZE = 0.07  # m


def box_faces(kind: str, cx: float, cz: float, size: Tuple[float, float, float], yaw: float = 0.0,
              base: float = 0.0) -> List[Face]:
    """The four sides and the top of a box standing at `base`, centred on (cx, cz), turned by `yaw` degrees."""
    sx, sy, sz = size[0] / 2.0, size[1], size[2] / 2.0
    cos_y, sin_y = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def turn(x: float, z: float) -> Tuple[float, float]:
        return cx + x * cos_y + z * sin_y, cz - x * sin_y + z * cos_y

    def point(x: float, y: float, z: float) -> Point:
        px, pz = turn(x, z)
        return px, base + y, pz

    def normal(x: float, y: float, z: float) -> Point:
        return x * cos_y + z * sin_y, y, -x * sin_y + z * cos_y

    sides = (
        ((0.0, 0.0, 1.0), [(-sx, 0, sz), (sx, 0, sz), (sx, sy, sz), (-sx, sy, sz)]),
        ((0.0, 0.0, -1.0), [(sx, 0, -sz), (-sx, 0, -sz), (-sx, sy, -sz), (sx, sy, -sz)]),
        ((-1.0, 0.0, 0.0), [(-sx, 0, -sz), (-sx, 0, sz), (-sx, sy, sz), (-sx, sy, -sz)]),
        ((1.0, 0.0, 0.0), [(sx, 0, sz), (sx, 0, -sz), (sx, sy, -sz), (sx, sy, sz)]),
        ((0.0, 1.0, 0.0), [(-sx, sy, sz), (sx, sy, sz), (sx, sy, -sz), (-sx, sy, -sz)]),
    )
    return [(kind, [point(*corner) for corner in corners], SQUARE, normal(*n)) for n, corners in sides]  # type: ignore


@functools.lru_cache(maxsize=None)
def yard_faces(seed: int, x_min: float, x_max: float, z_min: float, z_max: float) -> Tuple[Face, ...]:
    """Two groups of crates and cages on the edges of the concrete: a pile at the far back corner and a few scattered
    ones in the front corner on the other side. The same seed always gives the same yard."""
    rng = random.Random(seed)
    faces: List[Face] = []

    def put(cx: float, cz: float, size: Tuple[float, float, float], yaw: float, base: float = 0.0) -> None:
        faces.extend(box_faces('cage' if rng.random() < 0.4 else 'crate', cx, cz, size, yaw, base))

    pile_x, pile_z = x_max - 5.0, z_min + 9.0
    for i in range(3):  # bottom row
        put(pile_x + (i - 1) * 1.75 + rng.uniform(-0.1, 0.1), pile_z + rng.uniform(-0.15, 0.15),
            (1.6, 1.2, 1.2), rng.uniform(-7.0, 7.0))
    for i in range(2):  # second row
        put(pile_x + (i - 0.5) * 1.75 + rng.uniform(-0.1, 0.1), pile_z + rng.uniform(-0.1, 0.1),
            (1.6, 1.2, 1.2), rng.uniform(-9.0, 9.0), 1.2)
    put(pile_x + rng.uniform(-0.2, 0.2), pile_z, (1.4, 1.0, 1.1), rng.uniform(-12.0, 12.0), 2.4)

    scatter_x, scatter_z = x_min + 9.0, z_max - 8.0
    for _ in range(3):
        put(scatter_x + rng.uniform(-5.0, 5.0), scatter_z + rng.uniform(-4.0, 4.0),
            (rng.uniform(1.0, 1.8), rng.uniform(0.9, 1.4), rng.uniform(1.0, 1.5)), rng.uniform(0.0, 180.0))
    return tuple(faces)


# The masts on the old roof: (x, z, height above the roof, yaw of its bars), near the back, where the annex rises.
MASTS = ((-8.0, -1.8, 5.5, 20.0), (1.0, 1.0, 8.5, -35.0), (9.0, -1.2, 6.5, 70.0))


@functools.lru_cache(maxsize=None)
def mast_faces(roof_height: float) -> Tuple[Face, ...]:
    """Three antenna masts with two crossbars each, the upper bar shorter, like a yagi's directors."""
    faces: List[Face] = []
    for x, z, height, yaw in MASTS:
        faces += box_faces('steel', x, z, (MAST_SIZE, height, MAST_SIZE), yaw, roof_height)
        for fraction, length in ((0.62, 2.6), (0.88, 1.5)):
            faces += box_faces('steel', x, z, (length, BAR_SIZE, BAR_SIZE), yaw,
                               roof_height + height * fraction)
    return tuple(faces)


def billboard_faces(x: float, z: float, width: float) -> Tuple[Face, ...]:
    """The stand of the billboard: two posts and the frame behind the poster, which faces +z (towards the pads)."""
    faces: List[Face] = []
    for side in (-1.0, 1.0):
        faces += box_faces('steel', x + side * (width / 2.0 - 1.0), z, (POST_SIZE, BILLBOARD_BASE, POST_SIZE))
    faces += box_faces('steel', x, z, (width + 2 * BILLBOARD_BORDER, BILLBOARD_HEIGHT + 2 * BILLBOARD_BORDER,
                                       BILLBOARD_THICKNESS), base=BILLBOARD_BASE - BILLBOARD_BORDER)
    return tuple(faces)


def poster_quad(x: float, z: float, width: float) -> Tuple[List[Point], List[Tuple[float, float]], Point]:
    """The poster: a quad a hair in front of the frame. The world is left-handed (x east, z north), so seen from the
    front the image runs from the right to the left in x: u is flipped."""
    front = z + BILLBOARD_THICKNESS / 2.0 + 0.01
    left, right = x - width / 2.0, x + width / 2.0
    bottom, top = BILLBOARD_BASE, BILLBOARD_BASE + BILLBOARD_HEIGHT
    return ([(left, bottom, front), (right, bottom, front), (right, top, front), (left, top, front)],
            [(1.0, 1.0), (0.0, 1.0), (0.0, 0.0), (1.0, 0.0)], (0.0, 0.0, 1.0))
