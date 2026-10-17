"""The local star (sun): its image, where it is on the screen, and the hole it leaves in the sky.

The image is a limb-darkened disc and its corona, computed as an RGBA array (star_rgba). The disc follows the
limb-darkening law I(mu) = 1 - u (1 - mu), where mu is the cosine of the angle between the line of sight and the star's
surface normal (1 at the centre, 0 at the rim) and u is STAR_LIMB_DARKENING. The corona falls off as
(R / r) ** STAR_CORONA_FALLOFF and fades out at STAR_CORONA_EXTENT radii; its radius on screen is never below
STAR_GLOW_MIN_PX, so a distant star is a glowing point.

The OpenGL pass draws the image (graphics/star_gl.py) under the sky. The sky is drawn with a hole where the star is
(erase), so the worlds in front of the star cover it and the worlds behind it are not seen there.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, NamedTuple, Optional, Tuple
import math
import numpy as np
import pygame
from .constants import (
    STAR_LIMB_DARKENING, STAR_CORE_WHITENESS, STAR_CORONA_EXTENT, STAR_CORONA_FALLOFF, STAR_CORONA_ALPHA,
    STAR_GLOW_MIN_PX,
)

if TYPE_CHECKING:
    from galaxies.star import Star
    from spaceships.ship import Ship
    from game_environment import GameEnvironment

STAR_EDGE_PX = 1.5  # width of the disc's rim, blended into the corona, in pixels of the disc
PROFILE_SAMPLES_PER_PX = 4  # the radial profile's resolution: entries per pixel of distance

Colour = Tuple[int, int, int]


class StarView(NamedTuple):
    """Where the star is on the screen: its centre, the disc's radius and the corona's outer radius, in pixels."""
    star: Star
    x: float
    y: float
    disc_px: float
    corona_px: float


def star_profile(disc_px: float, corona_px: float, colour: Colour) -> np.ndarray:
    """The star's colour and opacity by distance from its centre: an (n, 4) uint8 table of RGBA, PROFILE_SAMPLES_PER_PX
    entries per pixel, out to the corona's edge; the last entry is transparent (beyond the corona)."""
    count = int(math.ceil(corona_px * PROFILE_SAMPLES_PER_PX)) + 2
    distance = (np.arange(count, dtype=np.float32) + 0.5) / PROFILE_SAMPLES_PER_PX / max(disc_px, 1e-3)  # disc radii
    base = np.array(colour, dtype=np.float32)
    core = base + (255.0 - base) * STAR_CORE_WHITENESS
    rim = base * (1.0 - STAR_LIMB_DARKENING)

    # The disc: linear in mu, from the rim's colour to the core's.
    mu = np.sqrt(np.clip(1.0 - distance * distance, 0.0, 1.0))[:, None]
    disc_rgb = rim + (core - rim) * mu

    # The corona: (1 / r) ** falloff, shifted and scaled to 1 at the rim and 0 at its outer edge. In the star's colour.
    extent = max(corona_px / max(disc_px, 1e-3), 1.0001)
    floor = extent ** -STAR_CORONA_FALLOFF
    falloff = np.power(np.maximum(distance, 1.0), -STAR_CORONA_FALLOFF)
    corona = np.clip((falloff - floor) / (1.0 - floor), 0.0, 1.0)
    corona_rgb = np.broadcast_to(base, disc_rgb.shape)

    # Disc to corona over STAR_EDGE_PX pixels, so the rim is smooth at any size (also scaled up from a small image).
    disc_share = np.clip((1.0 - distance) * max(disc_px, 1e-3) / STAR_EDGE_PX + 0.5, 0.0, 1.0)
    table = np.empty((count, 4), dtype=np.uint8)
    rgb = corona_rgb + (disc_rgb - corona_rgb) * disc_share[:, None]
    alpha = corona * STAR_CORONA_ALPHA + (255.0 - corona * STAR_CORONA_ALPHA) * disc_share
    table[:, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    table[:, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    table[-1] = 0
    return table


def star_rgba(width: int, height: int, centre_x: float, centre_y: float, disc_px: float, corona_px: float,
              colour: Colour) -> np.ndarray:
    """The star's image on a transparent array of `height` x `width` RGBA pixels (rows first, as pygame and OpenGL
    read them), centred at (centre_x, centre_y), with the disc's radius and the corona's outer radius in pixels."""
    table = star_profile(disc_px, corona_px, colour)
    dx = np.arange(width, dtype=np.float32) + 0.5 - centre_x
    dy = np.arange(height, dtype=np.float32) + 0.5 - centre_y
    distance = np.sqrt(dy[:, None] * dy[:, None] + dx[None, :] * dx[None, :])
    index = np.minimum(distance * PROFILE_SAMPLES_PER_PX, len(table) - 1).astype(np.int32)
    pixels = table.view(np.uint32).ravel()[index]  # each RGBA entry as one 32-bit value: a much faster lookup
    return pixels.view(np.uint8).reshape(height, width, 4)


def view_of(environment: GameEnvironment, ship: Ship, width: int, height: int) -> Optional[StarView]:
    """Where the targeted body's star is on the screen, or None when it is not in front of the ship."""
    from graphics.instruments.common import view_geometry, project_to_camera
    body = environment.targeted_body
    star = body.stellar_system.star
    star_vector = ship.navigation.direction_to_star(body, environment.date_time)
    _, horizon_y, focal_length_px = view_geometry(height)
    projected = project_to_camera(ship, star_vector, width, horizon_y, focal_length_px)
    if projected is None:
        return None
    disc_px = focal_length_px * math.atan(star.radius / star_vector.length())
    corona_px = max(disc_px * STAR_CORONA_EXTENT, STAR_GLOW_MIN_PX)
    return StarView(star, projected[0], projected[1], disc_px, corona_px)


def erase(surface: pygame.Surface, view: StarView, width: int, height: int) -> None:
    """Make the sky transparent where the star is (its disc and corona), so the star drawn under the sky shows there.
    `surface` must have per-pixel alpha."""
    radius = min(int(math.ceil(view.corona_px)), 2 * max(width, height))
    pygame.draw.circle(surface, (0, 0, 0, 0), (int(view.x), int(view.y)), radius)
