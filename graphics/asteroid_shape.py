"""The shape of an asteroid: a subdivided icosahedron, pushed out and in by smooth lumps, pitted by craters, stretched
along three axes and, when it is small, cut by a few planes.

The shape is a pure function of a seed and of the diameter, so the same asteroid always has the same shape (the seed is
the asteroid's, or, for a cosmetic one, derived from its key). Detail grows with the size: the mesh is subdivided one
level more for each decade of diameter (80 faces for a boulder like a rock of rock_shape.py, 5,120 for a body of tens
of kilometres), and the craters that the mesh can show grow in number with it. Roundness grows with the size too: a
rubble pile of a kilometre or less is irregular and elongated, and gravity rounds a body more and more from there up to
a few hundred kilometres, where it is nearly a sphere. A body that is larger is a dwarf planet (see asteroid_sizes.py).

The craters are dents in the mesh with a raised rim, in a power law of sizes (many small, few large, as on an old
surface). The geometry has the same number of faces whatever the number of craters, so heavy cratering costs nothing
once the mesh is built (about 10 ms for the largest, once per asteroid). Crater floors are darker and their rims
lighter (`tones`), which stands for the shadow a crater's wall casts on its own floor.

It is expressed in the asteroid's own unit coordinates (its longest extent reaches 1 on some axis), and the renderers
scale it by half the diameter and turn it (see `orientation`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import numpy as np

# Mesh resolution: the level (each level quadruples the faces) by diameter, up to each of these, in metres.
LEVEL_UPPER_DIAMETERS = (10.0, 1.0e3, 1.0e4)  # levels 1, 2 and 3; above the last, MAX_LEVEL
MAX_LEVEL = 4
ICOSAHEDRON_EDGE = 1.107  # rad, the angle between two neighbouring vertices of the unsubdivided icosahedron

# Roundness: 0 below ROUND_FROM_DIAMETER (rubble), 1 at ROUND_TO_DIAMETER (and above), logarithmic in between.
ROUND_FROM_DIAMETER = 1.0e3  # m
ROUND_TO_DIAMETER = 4.0e5  # m

# Lumps: a few smooth waves along random directions (the higher frequencies weaker), as a fraction of the radius.
LUMP_WAVES = 10
LUMP_FREQUENCIES = (1.0, 6.0)
LUMP_AMPLITUDE_IRREGULAR = 0.38
LUMP_AMPLITUDE_ROUND = 0.03

# Elongation of the irregular ones: the second and third axes shrink by up to these fractions.
ELONGATION_SECOND = 0.45
ELONGATION_THIRD = 0.40

# Cuts: planes that shave off whatever lies beyond them, for the small and irregular (none for the round).
CUT_PLANES_MAX = 4
CUT_DISTANCE = (0.62, 0.90)

# Craters: dents with a raised rim. Their angular radius (rad) follows a power law with a cumulative slope of
# CRATER_SLOPE from the smallest the mesh can show (CRATER_MIN_EDGES mesh edges across the radius).
CRATER_DENSITY = 0.6  # craters of at least the smallest size, per square radian of 1 / rho_min^2
CRATER_SLOPE = 2.0
CRATER_MIN_EDGES = 1.2
CRATER_MAX_RADIUS = 0.75  # rad
CRATER_DEPTH = 0.30  # of the crater's angular radius
CRATER_RIM_HEIGHT = 0.25  # of its depth
CRATER_RIM_WIDTH = 0.35  # of its radius
FLOOR_DARKENING = 0.35  # the darkest a crater floor gets, as a fraction of the tone
FLOOR_DEPTH_FOR_DARKEST = 0.035
RIM_BRIGHTENING = 0.12
LUMP_HOLLOW_DARKENING = 0.10
TONE_JITTER = 0.03

# How smooth the shading is: flat faces for a rubble pile, smooth normals for a round body (see `roundness`).
RADIAL_MIN = 0.45  # a vertex is never pulled nearer to the centre than this fraction of the radius


@dataclass(frozen=True)
class AsteroidMesh:
    """The mesh of one asteroid, in unit coordinates."""
    corners: np.ndarray  # (faces, 3, 3): the three corners of each triangle
    normals: np.ndarray  # (faces, 3, 3): the unit normal at each corner (flat for the irregular, smoother when round)
    tones: np.ndarray  # (faces, 3): a brightness factor near 1 at each corner (crater floors darker, rims lighter)
    centres: np.ndarray  # (faces, 3): the unit direction to the middle of each face, for the surface colours


def level_of(diameter: float) -> int:
    """The subdivision level of the mesh of an asteroid of this diameter (m)."""
    for level, upper in enumerate(LEVEL_UPPER_DIAMETERS, start=1):
        if diameter <= upper:
            return level
    return MAX_LEVEL


def roundness(diameter: float) -> float:
    """0 for an irregular rubble pile (a kilometre or less) up to 1 for a body that gravity has rounded."""
    if diameter <= ROUND_FROM_DIAMETER:
        return 0.0
    return min(1.0, math.log(diameter / ROUND_FROM_DIAMETER) / math.log(ROUND_TO_DIAMETER / ROUND_FROM_DIAMETER))


@cache
def _icosphere(level: int) -> tuple[np.ndarray, np.ndarray]:
    """Unit vertices (V, 3) and triangles (F, 3) of an icosahedron subdivided `level` times, the triangles
    outward-wound."""
    t = (1.0 + 5.0 ** 0.5) / 2.0
    vertices = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
             (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
             (8, 6, 7), (9, 8, 1)]
    points = np.array(vertices, dtype=np.float64)
    triangles = np.array(faces, dtype=np.int64)
    for _ in range(level):
        points, triangles = _subdivide(points, triangles)
    points = points / np.linalg.norm(points, axis=1)[:, None]
    return points, triangles


def _subdivide(points: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Each triangle becomes four, with new vertices at the middles of its edges (shared by the neighbours)."""
    unit = points / np.linalg.norm(points, axis=1)[:, None]
    new_points = [unit]
    middle: dict[tuple[int, int], int] = {}
    count = len(unit)
    result = []
    for a, b, c in triangles:
        ids = []
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(u, v), max(u, v))
            if key not in middle:
                middle[key] = count
                count += 1
                new_points.append(((unit[u] + unit[v]) / 2.0)[None, :])
            ids.append(middle[key])
        ab, bc, ca = ids
        result += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return np.concatenate(new_points), np.array(result, dtype=np.int64)


def smooth_noise(points: np.ndarray, rng: np.random.Generator, waves: int, low: float, high: float) -> np.ndarray:
    """A value near [-1, 1] at each point (N, 3), smooth in space: a sum of sines along random directions, with
    frequencies between `low` and `high` (the higher ones weaker)."""
    directions = rng.normal(size=(waves, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    frequencies = rng.uniform(low, high, waves)
    phases = rng.uniform(0.0, math.tau, waves)
    weights = 1.0 / frequencies
    return (np.sin(points @ directions.T * frequencies + phases) * weights).sum(axis=1) / weights.sum()


def asteroid_mesh(seed: int, diameter: float) -> AsteroidMesh:
    """The mesh of the asteroid of this seed and diameter (m). Draws from its own generator, in a fixed order: lumps,
    craters (count, sizes, places), the axes, the cuts, and the tones' jitter."""
    rng = np.random.default_rng([seed, 3])
    level = level_of(diameter)
    round_ = roundness(diameter)
    vertices, faces = _icosphere(level)

    lump_amplitude = LUMP_AMPLITUDE_IRREGULAR * (1.0 - round_) + LUMP_AMPLITUDE_ROUND * round_
    lumps = lump_amplitude * smooth_noise(vertices, rng, LUMP_WAVES, *LUMP_FREQUENCIES)
    craters = _crater_displacement(vertices, rng, level)
    positions = vertices * np.maximum(1.0 + lumps + craters, RADIAL_MIN)[:, None]

    elongation = 1.0 - round_
    second = 1.0 - elongation * ELONGATION_SECOND * rng.random()
    third = second * (1.0 - elongation * ELONGATION_THIRD * rng.random())
    positions = positions * rng.permutation([1.0, second, third])

    for _ in range(int(rng.integers(0, 1 + round(CUT_PLANES_MAX * (1.0 - round_))))):
        normal = rng.normal(size=3)
        normal /= np.linalg.norm(normal)
        distance = rng.uniform(*CUT_DISTANCE)
        excess = np.maximum(positions @ normal - distance, 0.0)
        positions = positions - excess[:, None] * normal
    positions = positions / np.max(np.abs(positions))  # the longest extent reaches 1

    triangles = positions[faces]
    face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    face_normals /= np.maximum(np.linalg.norm(face_normals, axis=1), 1e-12)[:, None]
    face_normals = np.where((face_normals * triangles.mean(axis=1)).sum(axis=1)[:, None] < 0, -face_normals,
                            face_normals)
    vertex_normals = np.zeros_like(positions)
    for corner in range(3):
        np.add.at(vertex_normals, faces[:, corner], face_normals)
    vertex_normals /= np.maximum(np.linalg.norm(vertex_normals, axis=1), 1e-12)[:, None]
    corner_normals = (1.0 - round_) * face_normals[:, None, :] + round_ * vertex_normals[faces]
    corner_normals /= np.maximum(np.linalg.norm(corner_normals, axis=2), 1e-12)[..., None]

    floor = np.clip(-craters / FLOOR_DEPTH_FOR_DARKEST, 0.0, 1.0)
    rim = np.clip(craters / (FLOOR_DEPTH_FOR_DARKEST * CRATER_RIM_HEIGHT), 0.0, 1.0)
    hollow = np.clip(-lumps / lump_amplitude, 0.0, 1.0)
    vertex_tones = (1.0 - FLOOR_DARKENING * floor + RIM_BRIGHTENING * rim - LUMP_HOLLOW_DARKENING * hollow
                    + TONE_JITTER * (2.0 * rng.random(len(vertices)) - 1.0))
    return AsteroidMesh(triangles, corner_normals, vertex_tones[faces], vertices[faces].mean(axis=1))


def _crater_displacement(vertices: np.ndarray, rng: np.random.Generator, level: int) -> np.ndarray:
    """The radial displacement of each unit vertex by the craters: a bowl, and a raised rim just outside it."""
    smallest = CRATER_MIN_EDGES * ICOSAHEDRON_EDGE / 2 ** level
    count = int(CRATER_DENSITY / smallest ** 2)
    if count == 0:
        return np.zeros(len(vertices))
    radii = np.minimum(smallest * rng.random(count) ** (-1.0 / CRATER_SLOPE), CRATER_MAX_RADIUS)
    centres = rng.normal(size=(count, 3))
    centres /= np.linalg.norm(centres, axis=1)[:, None]
    angle = np.arccos(np.clip(vertices @ centres.T, -1.0, 1.0))  # (V, count)
    depth = CRATER_DEPTH * radii
    inside = angle < radii
    bowl = np.where(inside, -depth * (1.0 - (angle / radii) ** 2), 0.0)
    rim_width = CRATER_RIM_WIDTH * radii
    along = (angle - radii) / rim_width
    rim = np.where(~inside & (along < 1.0), CRATER_RIM_HEIGHT * depth * (1.0 - along) ** 2, 0.0)
    return (bowl + rim).sum(axis=1)


def orientation(seed: int) -> np.ndarray:
    """A random rotation (3, 3) for the asteroid of this seed: how it lies in the stellar frame."""
    rng = np.random.default_rng([seed, 5])
    quaternion = rng.normal(size=4)
    x, y, z, w = quaternion / np.linalg.norm(quaternion)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
