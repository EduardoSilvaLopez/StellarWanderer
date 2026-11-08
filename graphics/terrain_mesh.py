"""The meshes of the ground: chunks of the surface frame, built from the world's heights.

Plain numpy on purpose, with no OpenGL or pygame: the helper processes that build the chunks load only this module and
`galaxies.terrain`. A chunk is a node of a quadtree over the plane (x east, z north): its key is (level, ix, iz), its
side ROOT_SIZE / 2 ** level and its corner (ix, iz) times that. Every chunk is CELLS x CELLS cells, so a finer level
is a smaller chunk with finer cells, and a coarser one a larger chunk.

A vertex is its x and z from the chunk's corner (small, float32-safe: the corner is added in double precision with the
camera's offset), its height above the datum, and its normal. A skirt hangs below each edge, so that neighbours of
different levels leave no crack.
"""

from __future__ import annotations
from typing import Tuple

import numpy as np

from galaxies.terrain import Terrain

CELLS = 32                  # cells along a chunk's side; the same topology for every chunk
ROOT_SIZE = 32768.0         # m: the side of a chunk of level 0 (its cells 1 km: the far landmarks)
MAX_LEVEL = 10              # a chunk of this level is 32 m wide, its cells 1 m
SKIRT_SHARE = 0.1           # the skirt's depth as a share of the chunk's side

Key = Tuple[int, int, int]   # level, ix, iz
VERTEX_FLOATS = 6            # x, y, z, nx, ny, nz
VERTEX_COUNT = (CELLS + 1) ** 2 + 4 * (CELLS + 1)


def chunk_size(level: int) -> float:
    return ROOT_SIZE / (2 ** level)


def chunk_corner(key: Key) -> Tuple[float, float]:
    size = chunk_size(key[0])
    return key[1] * size, key[2] * size


def build_chunk(key: Key, seed: int, radius: float, relief: float, platforms: Tuple = ()) -> np.ndarray:
    """The vertices of a chunk, float32 (VERTEX_COUNT, VERTEX_FLOATS): the (CELLS + 1)^2 of its grid, then the skirt of
    each of its four edges (the first and last row, then the first and last column)."""
    size = chunk_size(key[0])
    step = size / CELLS
    x0, z0 = chunk_corner(key)
    n = CELLS + 1
    # one more row and column on each side, for the normals at the edge, which then agree with the neighbours'
    height = Terrain(seed, radius, relief, platforms).grid_heights(x0 - step, z0 - step, step, n + 2, n + 2)
    slope_x = (height[2:, 1:-1] - height[:-2, 1:-1]) / (2.0 * step)
    slope_z = (height[1:-1, 2:] - height[1:-1, :-2]) / (2.0 * step)
    normal = np.stack([-slope_x, np.ones_like(slope_x), -slope_z], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    inner = height[1:-1, 1:-1]
    gx, gz = np.meshgrid(np.arange(n) * step, np.arange(n) * step, indexing="ij")
    grid = np.concatenate([np.stack([gx, inner, gz], axis=-1), normal], axis=-1)            # (n, n, 6)
    lowered = grid.copy()
    lowered[..., 1] -= size * SKIRT_SHARE
    skirts = [lowered[0, :], lowered[-1, :], lowered[:, 0], lowered[:, -1]]
    return np.concatenate([grid.reshape(-1, VERTEX_FLOATS)] + skirts, axis=0).astype(np.float32)


def build_chunk_timed(key: Key, seed: int, radius: float, relief: float,
                      platforms: Tuple = ()) -> Tuple[Key, np.ndarray, float]:
    """build_chunk with its key and its duration in seconds: what a helper process runs."""
    import time
    started = time.perf_counter()
    vertices = build_chunk(key, seed, radius, relief, platforms)
    return key, vertices, time.perf_counter() - started


def index_buffer() -> np.ndarray:
    """The indices every chunk shares: the grid's triangles, then a strip of triangles for each skirt."""
    n = CELLS
    w = n + 1
    i, j = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    a = (i * w + j).ravel()
    b, c = a + 1, a + w
    d = c + 1
    triangles = [np.stack([a, c, b], axis=1), np.stack([b, c, d], axis=1)]
    base = w * w
    for edge, (first, step) in enumerate(((0, 1), (n * w, 1), (0, w), (n, w))):
        inner = first + step * np.arange(n)
        following = inner + step
        skirt = base + edge * w + np.arange(n)
        triangles.append(np.stack([inner, skirt, following], axis=1))
        triangles.append(np.stack([following, skirt, skirt + 1], axis=1))
    return np.concatenate(triangles, axis=0).astype(np.uint16).ravel()
