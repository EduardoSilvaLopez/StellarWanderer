"""The irregular shape of a rock: a lumpy, faceted boulder built from a subdivided icosahedron, then cut by a few
random planes, which leave flat fracture faces and sharp edges.

The shape is a pure function of the rock's `shape_seed` (set in Galaxies/rock.py), so the same rock always has
the same shape. It is expressed in the rock's local unit coordinates and fills the cube [-1, 1] on every axis,
so the cube the scanner tests (rock.size on a side, see Scanner.is_rock_targeted) is exactly the boulder's
bounding box. The renderers scale it by half the rock's size and rotate it (tilt, then orientation).
"""

from __future__ import annotations
from typing import List, Sequence, Tuple

import numpy as np

# Radial lumpiness: three random directions stretch or squash the rock (a potato, not a ball), each vertex is then
# pulled in a little at random, which makes the facets. Tones vary a little from face to face.
LUMP_AMPLITUDE = 0.60 # Less round as with 0.40
FACET_MIN = 0.45 # Less round as with 0.60
LUMP_MIN = 0.3   # a vertex is never pulled through the centre
TONE_RANGE = 0.08
# Planes that break the boulder: each one cuts off whatever lies beyond it, at a distance from the centre within
# these bounds (the lumpy body is about one unit across).
CUT_PLANES_MIN = 3
CUT_PLANES_MAX = 5
CUT_DISTANCE_MIN = 0.55
CUT_DISTANCE_MAX = 0.85


def _icosphere() -> Tuple[np.ndarray, np.ndarray]:
    """Unit vertices (42, 3) and triangles (80, 3) of an icosahedron subdivided once."""
    t = (1.0 + 5.0 ** 0.5) / 2.0
    vertices: List[Tuple[float, float, float]] = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
        (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
        (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
        (8, 6, 7), (9, 8, 1)]
    midpoints = {}

    def midpoint(a: int, b: int) -> int:
        key = (min(a, b), max(a, b))
        if key not in midpoints:
            midpoints[key] = len(vertices)
            vertices.append(tuple((vertices[a][i] + vertices[b][i]) / 2.0 for i in range(3)))
        return midpoints[key]

    subdivided = []
    for a, b, c in faces:
        ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
        subdivided += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    unit = np.array(vertices, dtype=np.float64)
    unit /= np.linalg.norm(unit, axis=1)[:, None]
    return unit, np.array(subdivided, dtype=np.int64)


_UNIT_VERTICES, _TRIANGLES = _icosphere()
FACES = len(_TRIANGLES)   # 80 triangles per rock


def rotate(points: np.ndarray, tilt: np.ndarray, orientation: np.ndarray) -> np.ndarray:
    """Rotate (rocks, points, 3) like the renderer: tilt about local Z, then orientation about the vertical axis.
    `tilt` and `orientation` are in degrees, one per rock. Used for vertices and normals alike."""
    cos_t, sin_t = np.cos(np.radians(tilt))[:, None], np.sin(np.radians(tilt))[:, None]
    cos_o, sin_o = np.cos(np.radians(orientation))[:, None], np.sin(np.radians(orientation))[:, None]
    x, y, z = points[..., 0], points[..., 1], points[..., 2]
    x1 = x * cos_t - y * sin_t
    y1 = x * sin_t + y * cos_t
    return np.stack((x1 * cos_o + z * sin_o, y1, -x1 * sin_o + z * cos_o), axis=-1)


_GOLDEN = np.uint64(0x9E3779B97F4A7C15)
_MIX_1 = np.uint64(0xBF58476D1CE4E5B9)
_MIX_2 = np.uint64(0x94D049BB133111EB)
_UNIFORMS_PER_ROCK = 6 + 3 + len(_UNIT_VERTICES) + FACES + 3 * CUT_PLANES_MAX + 1   # lumps, facets, tones, cuts


def _uniforms(seeds: Sequence[int], count: int) -> np.ndarray:
    """(rocks, count) numbers in [0, 1): a counter-based hash (splitmix64) of each seed and the number's index, so a
    rock's numbers depend on its own seed only, and every rock is computed at once."""
    with np.errstate(over='ignore'):
        x = np.asarray(seeds, dtype=np.uint64)[:, None] * _GOLDEN + (np.arange(count, dtype=np.uint64) + np.uint64(1))[None, :] * _MIX_1
        x = (x ^ (x >> np.uint64(30))) * _MIX_1
        x = (x ^ (x >> np.uint64(27))) * _MIX_2
        x = x ^ (x >> np.uint64(31))
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def rock_meshes(shape_seeds: Sequence[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The shapes of rocks, one per seed, in local unit coordinates.

    Returns (triangles, normals, tones):
      triangles (rocks, FACES, 3, 3): the three corners of each triangle, outward-wound;
      normals   (rocks, FACES, 3):    the unit outward normal of each triangle (flat shading);
      tones     (rocks, FACES):       a brightness factor near 1 per triangle, for colour variation.
    """
    count = len(shape_seeds)
    uniform = _uniforms(shape_seeds, _UNIFORMS_PER_ROCK)
    vertex_count = len(_UNIT_VERTICES)
    facets_start = 9
    tones_start = facets_start + vertex_count
    cut_start = tones_start + FACES

    height = 2.0 * uniform[:, 0:3] - 1.0                                   # three random directions, uniform on the sphere
    angle = 2.0 * np.pi * uniform[:, 3:6]
    radius = np.sqrt(1.0 - height ** 2)
    directions = np.stack((radius * np.cos(angle), radius * np.sin(angle), height), axis=-1)   # (count, 3, 3)
    amplitudes = LUMP_AMPLITUDE * (2.0 * uniform[:, 6:9] - 1.0)
    facets = FACET_MIN + (1.0 - FACET_MIN) * uniform[:, facets_start:tones_start]
    tones = 1.0 - TONE_RANGE + 2.0 * TONE_RANGE * uniform[:, tones_start:cut_start]

    lumps = np.maximum(LUMP_MIN, 1.0 + np.einsum('vk,ndk,nd->nv', _UNIT_VERTICES, directions, amplitudes))
    shaped = _UNIT_VERTICES[None, :, :] * (lumps * facets)[..., None]

    # Cut: each plane moves the vertices beyond it back onto it. Triangles lying wholly beyond a plane become one flat
    # face; the others are stretched along it, which gives the sharp edges.
    cut_u = uniform[:, cut_start:cut_start + 3 * CUT_PLANES_MAX].reshape(count, CUT_PLANES_MAX, 3)
    cut_height = 2.0 * cut_u[..., 0] - 1.0
    cut_angle = 2.0 * np.pi * cut_u[..., 1]
    cut_radius = np.sqrt(1.0 - cut_height ** 2)
    cut_normals = np.stack((cut_radius * np.cos(cut_angle), cut_radius * np.sin(cut_angle), cut_height), axis=-1)
    cut_offsets = CUT_DISTANCE_MIN + (CUT_DISTANCE_MAX - CUT_DISTANCE_MIN) * cut_u[..., 2]
    planes = CUT_PLANES_MIN + (uniform[:, cut_start + 3 * CUT_PLANES_MAX] * (CUT_PLANES_MAX - CUT_PLANES_MIN + 1)).astype(int)
    cut_offsets = np.where(np.arange(CUT_PLANES_MAX)[None, :] < planes[:, None], cut_offsets, np.inf)
    for k in range(CUT_PLANES_MAX):
        beyond = np.maximum(0.0, np.einsum('nvk,nk->nv', shaped, cut_normals[:, k]) - cut_offsets[:, k:k + 1])
        shaped = shaped - beyond[..., None] * cut_normals[:, k][:, None, :]

    vertices = shaped / np.abs(shaped).max(axis=1, keepdims=True)         # fill [-1, 1] on every axis

    triangles = vertices[:, _TRIANGLES]                                    # (count, FACES, 3, 3)
    normals = np.cross(triangles[:, :, 1] - triangles[:, :, 0], triangles[:, :, 2] - triangles[:, :, 0])
    inward = (normals * triangles.mean(axis=2)).sum(axis=2) < 0.0          # the shape surrounds the origin
    triangles[inward] = triangles[inward][:, [0, 2, 1]]                    # swap two corners: flips the winding
    normals[inward] *= -1.0
    normals /= np.maximum(np.linalg.norm(normals, axis=2), 1e-12)[..., None]
    return triangles, normals, tones
