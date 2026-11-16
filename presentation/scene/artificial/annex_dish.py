"""The antenna dish on the roof of a size 3 outpost's annex: a low-poly paraboloid on a mast, tilted towards the door
side, with three struts to its feed. It is plain geometry, with no GL, so that the preview in temp/ can use it too;
graphics/outposts.py draws it.

Each face costs the PyOpenGL calls of one quad, not GPU time, so the mesh is kept small (about 45 faces, as much as
the flagpole and its flag). Points are in metres from the middle of the roof, x along the width, y up from the roof,
z along the door axis, as in the outpost's frame, and the faces come with their outward normals, as the outposts are
lit face by face.
"""

from __future__ import annotations
import functools
import math
from typing import List, Literal, Tuple

Point = Tuple[float, float, float]
Face = Tuple[Literal['dish', 'steel', 'crate', 'cage'], List[Point], List[Tuple[float, float]], Point]

DISH_RADIUS = 4.0  # m
DISH_DEPTH = 1.0  # m, of the bowl at its rim
DISH_TILT = 35.0  # degrees from the vertical, towards the door side (+z)
DISH_PIVOT = 2.2  # m, height of the bowl's bottom over the roof: with the tilt, the rim stays clear of it
DISH_SEGMENTS = 12
DISH_RINGS = 2
STRUT_HALF_WIDTH = 0.06  # m
FEED_HALF_SIZE = 0.16  # m
MAST_HALF_WIDTH = 0.45  # m
PLATE_HALF_WIDTH = 1.2  # m
PLATE_HEIGHT = 0.15  # m
SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def _unit(vector: Point) -> Point:
    length = math.sqrt(sum(value * value for value in vector))
    return vector[0] / length, vector[1] / length, vector[2] / length


def _cross(a: Point, b: Point) -> Point:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


@functools.lru_cache(maxsize=None)
def dish_faces() -> Tuple[Face, ...]:
    """The faces of the plate, the mast, the bowl, its three struts and the feed."""
    tilt = math.radians(DISH_TILT)
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)
    depth_factor = DISH_DEPTH / DISH_RADIUS ** 2  # the bowl is y = depth_factor * r^2 in its own frame

    def direction(x: float, y: float, z: float) -> Point:
        """A direction of the bowl's own frame (y along its axis) in the outpost's."""
        return x, y * cos_t - z * sin_t, y * sin_t + z * cos_t

    def place(x: float, y: float, z: float) -> Point:
        dx, dy, dz = direction(x, y, z)
        return dx, DISH_PIVOT + dy, dz

    def vertex(radius: float, angle: float) -> Tuple[Point, Tuple[float, float]]:
        x, z = radius * math.cos(angle), radius * math.sin(angle)
        return (place(x, depth_factor * radius ** 2, z),
                (0.5 + x / (2.0 * DISH_RADIUS), 0.5 + z / (2.0 * DISH_RADIUS)))

    faces: List[Face] = []

    def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
        for normal, points in (
                ((0.0, 0.0, 1.0), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
                ((0.0, 0.0, -1.0), [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)]),
                ((-1.0, 0.0, 0.0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),
                ((1.0, 0.0, 0.0), [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)]),
                ((0.0, 1.0, 0.0), [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)])):
            faces.append(('steel', points, SQUARE, normal))

    box(-PLATE_HALF_WIDTH, PLATE_HALF_WIDTH, 0.0, PLATE_HEIGHT, -PLATE_HALF_WIDTH, PLATE_HALF_WIDTH)
    box(-MAST_HALF_WIDTH, MAST_HALF_WIDTH, PLATE_HEIGHT, DISH_PIVOT - 0.2, -MAST_HALF_WIDTH, MAST_HALF_WIDTH)

    # The bowl, as rings of segments; the innermost ring is made of triangles (a quad with its first two points equal).
    radii = [DISH_RADIUS * ring / DISH_RINGS for ring in range(DISH_RINGS + 1)]
    for ring in range(DISH_RINGS):
        for segment in range(DISH_SEGMENTS):
            angles = (2.0 * math.pi * segment / DISH_SEGMENTS, 2.0 * math.pi * (segment + 1) / DISH_SEGMENTS)
            corners = [vertex(radii[ring], angles[0]), vertex(radii[ring], angles[1]),
                       vertex(radii[ring + 1], angles[1]), vertex(radii[ring + 1], angles[0])]
            middle_angle = (angles[0] + angles[1]) / 2.0
            middle_radius = (radii[ring] + radii[ring + 1]) / 2.0
            slope = 2.0 * depth_factor * middle_radius  # the bowl's normal leans away from the rim
            normal = _unit(direction(-slope * math.cos(middle_angle), 1.0, -slope * math.sin(middle_angle)))
            faces.append(('dish', [point for point, _ in corners], [uv for _, uv in corners], normal))

    # Three struts from the rim to the feed at the focus, each a cross of two thin ribbons.
    focus = place(0.0, DISH_RADIUS ** 2 / (4.0 * DISH_DEPTH), 0.0)
    axis = direction(0.0, 1.0, 0.0)
    for k in range(3):
        angle = math.radians(90.0 + 120.0 * k)
        rim = vertex(DISH_RADIUS, angle)[0]
        tangent = direction(-math.sin(angle), 0.0, math.cos(angle))
        for offset in ((value * STRUT_HALF_WIDTH for value in tangent),
                       (value * STRUT_HALF_WIDTH for value in axis)):
            shift = tuple(offset)
            along = (focus[0] - rim[0], focus[1] - rim[1], focus[2] - rim[2])
            normal = _unit(_cross(along, shift))
            faces.append(('steel', [(rim[0] - shift[0], rim[1] - shift[1], rim[2] - shift[2]),
                                    (rim[0] + shift[0], rim[1] + shift[1], rim[2] + shift[2]),
                                    (focus[0] + shift[0], focus[1] + shift[1], focus[2] + shift[2]),
                                    (focus[0] - shift[0], focus[1] - shift[1], focus[2] - shift[2])],
                          SQUARE, normal))
    box(focus[0] - FEED_HALF_SIZE, focus[0] + FEED_HALF_SIZE, focus[1] - FEED_HALF_SIZE, focus[1] + FEED_HALF_SIZE,
        focus[2] - FEED_HALF_SIZE, focus[2] + FEED_HALF_SIZE)
    return tuple(faces)
