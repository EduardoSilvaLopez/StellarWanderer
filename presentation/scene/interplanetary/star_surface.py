"""The sun's surface: granulation, sunspots and the visor that darkens the view when the sun is large.

Granulation is a fine, random mottling of the disc (the convection cells of the photosphere). It is baked, once per star
colour, into the texture that graphics/star_gl.py draws, so it costs nothing per frame and it does not turn.

Sunspots are darker patches on the star's face. Each has a fixed place on the star (a latitude and a longitude at game
time 0) and turns with the star's rotation period, so it crosses the disc, is foreshortened towards the rim and goes
round the back. They are not baked: sunspot_quads gives where each one is for a game time, and star_gl draws them
each frame. A spot on the far side is not drawn.

The visor (auto-darkening) dims the whole view by an amount that grows as the sun's disc grows on the screen, between
VISOR_START_PX and VISOR_FULL_PX. The cockpit is not dimmed: it is drawn after.
"""

from __future__ import annotations
import math
import random
from typing import List, NamedTuple
import numpy as np
import pygame
from .constants import (
    GRANULATION_STRENGTH, GRANULE_CELL_SHARE, SPOT_COUNT_MIN, SPOT_COUNT_EXTRA, SPOT_RADIUS_MIN, SPOT_RADIUS_MAX,
    VISOR_START_PX, VISOR_FULL_PX, VISOR_MAX_ALPHA,
)

SPOT_MIN_FRONT = 0.1  # a spot is not drawn when its centre is this close to the limb, or behind the disc


class Sunspot(NamedTuple):
    latitude: float  # radians, at game time 0
    longitude: float  # radians, at game time 0; it grows by 2 pi per rotation period
    radius: float  # in disc radii


class SpotQuad(NamedTuple):
    """Where a sunspot is on the disc, as offsets from the disc's centre, and its size, all in disc radii. The width
    is foreshortened as the spot turns towards the rim."""
    dx: float
    dy: float
    half_width: float
    half_height: float


def _random(star_seed: int, salt: int) -> random.Random:
    return random.Random(int(star_seed * 1000) * 7919 + salt)


def granulation(width: int, height: int, centre_x: float, centre_y: float, disc_px: float,
                star_seed: int) -> np.ndarray:
    """The granules' brightness factor (height x width, float32) for the disc: 1 outside it. Coordinates are as the
    texture of star_gl: pixels, rows first."""
    rnd = _random(star_seed, 17)
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    x = (xs + 0.5 - centre_x) / max(disc_px, 1e-3)  # in disc radii
    y = (ys + 0.5 - centre_y) / max(disc_px, 1e-3)
    on_disc = x * x + y * y < 1.0

    # Random values on a coarse grid, smoothed up to the texture's size.
    cells = max(4, int(width / max(disc_px, 1e-3) / GRANULE_CELL_SHARE))  # cells across the texture
    grid = np.array([[rnd.randrange(256) for _ in range(cells)] for _ in range(cells)], dtype=np.uint8)
    grid_surface = pygame.surfarray.make_surface(np.repeat(grid[:, :, None], 3, axis=2).transpose(1, 0, 2))
    smooth = pygame.surfarray.array3d(pygame.transform.smoothscale(grid_surface, (width, height)))[:, :, 0]
    brightness = 1.0 + GRANULATION_STRENGTH * (smooth.T.astype(np.float32) / 255.0 - 0.5)
    return np.where(on_disc, brightness, 1.0).astype(np.float32)


def sunspots(star_seed: int) -> List[Sunspot]:
    """The star's sunspots: a few, by the star's seed."""
    rnd = _random(star_seed, 29)
    count = SPOT_COUNT_MIN + rnd.randrange(SPOT_COUNT_EXTRA + 1)
    return [Sunspot(
        latitude=rnd.uniform(-0.6, 0.6),
        longitude=rnd.uniform(-math.pi / 2, math.pi / 2),
        radius=rnd.uniform(SPOT_RADIUS_MIN, SPOT_RADIUS_MAX),
    ) for _ in range(count)]


def sunspot_quads(spots: List[Sunspot], game_seconds: float, rotation_period: float) -> List[SpotQuad]:
    """Where each sunspot that faces the ship is at `game_seconds` (game time since EPOCH), the star turning once per
    rotation_period. Seen from the front, a spot's x is its longitude's sine and its y its latitude's sine; its width
    shrinks with the cosine of its longitude as it turns towards the rim."""
    turn = 2 * math.pi * game_seconds / rotation_period
    quads: List[SpotQuad] = []
    for spot in spots:
        longitude = spot.longitude + turn
        front = math.cos(spot.latitude) * math.cos(longitude)
        if front <= SPOT_MIN_FRONT:
            continue
        quads.append(SpotQuad(
            dx=math.cos(spot.latitude) * math.sin(longitude),
            dy=-math.sin(spot.latitude),
            half_width=spot.radius * front,
            half_height=spot.radius,
        ))
    return quads


def visor_strength(disc_px: float) -> float:
    """How much the view is darkened, from 0 (the sun is small) to VISOR_MAX_ALPHA (the sun fills much of the view)."""
    share = (disc_px - VISOR_START_PX) / (VISOR_FULL_PX - VISOR_START_PX)
    return VISOR_MAX_ALPHA * max(0.0, min(1.0, share))
