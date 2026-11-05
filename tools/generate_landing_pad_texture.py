"""Generate common/resources/textures/landing_pad.png, the texture of the landing pad of a size 3 outpost.

Run from the project root:  python tools/generate_landing_pad_texture.py

The pad is a platform that can sink, with the ship on it, into installations under the ground: a satin metal disc in a
ring of dark collar, separated from it by a thin gap that glows, divided by seams like the leaves of a lift, with the
landing marks painted on it (no letters or numbers) and a ring of lights. The image is square, 20 m across (Outpost.PAD_RADIUS is its
radius, 10 m), so 51.2 pixels per metre, and transparent outside the disc. The lights are painted last, as in the
outpost texture, so they stay bright.
"""

from __future__ import annotations
import math
import os
from typing import List, Tuple

import numpy as np
import pygame

import generate_outpost_texture as old

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT = os.path.join(ROOT, 'common', 'resources', 'textures', 'landing_pad.png')

SIZE = 1024
RADIUS = 10.0  # m, the edge of the image's disc
PPM = SIZE / (2.0 * RADIUS)

COLLAR_FROM = 9.5  # m: the dark collar of the pad
GAP = (9.38, 9.5)  # the glowing gap between platform and collar
HUB = 2.2  # m: the central hub
RING_MARKS = ((5.5, 5.72), (6.5, 6.6))  # painted rings
HAZARD = (8.3, 8.95)  # arcs of hazard stripes at the four cardinal points
LIGHTS_AT = 9.17  # m: the ring of lights
LIGHT_COUNT = 24

PLATE = (82, 90, 104)
PLATE_HUB = (104, 114, 130)
COLLAR = (44, 48, 56)
SEAM = (22, 26, 32)
PAINT = (226, 231, 234)
YELLOW, BLACK = old.HAZARD_A, old.HAZARD_B
CYAN = (110, 226, 255)

Colour = Tuple[int, int, int]


def px(metres: float) -> int:
    return int(round(SIZE / 2 + metres * PPM))


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    rng = np.random.default_rng(2029)

    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    dx, dy = (xx + 0.5 - SIZE / 2) / PPM, (yy + 0.5 - SIZE / 2) / PPM
    r = np.hypot(dx, dy)
    theta = np.arctan2(dy, dx)
    soft = 1.0 / PPM  # one pixel, in metres

    def band(r0: float, r1: float) -> np.ndarray:
        """Coverage 0..1 of the ring r0..r1, antialiased over a pixel."""
        return np.clip((r - r0) / soft + 0.5, 0, 1) * np.clip((r1 - r) / soft + 0.5, 0, 1)

    image = np.zeros((SIZE, SIZE, 3), np.float32)

    def paint(mask: np.ndarray, colour: Colour) -> None:
        nonlocal image
        image = image * (1.0 - mask[..., None]) + np.array(colour, np.float32) * mask[..., None]

    # Platform: satin metal, with fine brushing along the circles and a slow mottle.
    brushed = 0.97 + 0.03 * np.sin(r * 260.0 + 3.0 * old.noise(rng, SIZE, SIZE, 24, 24)) \
        + 0.04 * (old.fbm(rng, SIZE, SIZE, 6) - 0.5)
    paint(band(0.0, GAP[0]), PLATE)
    image *= brushed[..., None]
    paint(band(0.0, HUB), PLATE_HUB)
    image *= (0.98 + 0.02 * np.sin(r * 180.0))[..., None]

    # Seams: two circles and eight radial lines, like the leaves of a lift.
    for radius in (HUB, 5.0, 7.6):
        paint(band(radius - 0.025, radius + 0.025), SEAM)
        paint(band(radius + 0.025, radius + 0.05), old.shade(PLATE, 1.25))
    for k in range(8):
        angle = k * math.pi / 4.0
        across = np.abs(-dx * math.sin(angle) + dy * math.cos(angle))  # distance to the radial line
        along = dx * math.cos(angle) + dy * math.sin(angle)
        line = np.clip((0.025 - across) / soft + 0.5, 0, 1) * (along > HUB) * (r < GAP[0])
        paint(line, SEAM)

    # Painted marks: two rings, a cross in the hub, and hazard arcs at the cardinal points.
    for r0, r1 in RING_MARKS:
        paint(band(r0, r1), PAINT)
    for angle in (0.0, math.pi / 2, math.pi):
        across = np.abs(-dx * math.sin(angle) + dy * math.cos(angle))
        paint(np.clip((0.07 - across) / soft + 0.5, 0, 1) * (r < RING_MARKS[0][0]) * (r > HUB + 0.1), PAINT)
    arc_mid = (HAZARD[0] + HAZARD[1]) / 2.0
    for k in range(4):
        angle = k * math.pi / 2.0
        wrapped = np.abs((theta - angle + math.pi) % (2 * math.pi) - math.pi)
        inside = band(*HAZARD) * (wrapped * arc_mid < 1.8)
        stripe = (np.floor((theta * arc_mid + r) / 0.32) % 2).astype(np.float32)
        paint(inside * stripe, YELLOW)
        paint(inside * (1.0 - stripe), BLACK)

    # The glowing gap and the collar.
    paint(band(*GAP), (28, 120, 150))
    paint(band(GAP[0] + 0.03, GAP[1] - 0.03), CYAN)
    paint(band(COLLAR_FROM, RADIUS - 0.02), COLLAR)
    paint(band(COLLAR_FROM + 0.02, COLLAR_FROM + 0.06), old.shade(COLLAR, 1.8))
    paint(band(RADIUS - 0.08, RADIUS - 0.02), old.shade(COLLAR, 0.6))

    painted = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    painted.blit(old.to_surface(image), (0, 0))

    # Bolts in the collar and chevrons pointing in. No letters or numbers.
    for k in range(48):
        angle = k * math.tau / 48
        old.rivet(painted, px(9.76 * math.cos(angle)), px(9.76 * math.sin(angle)), 3)
    for k in range(4):
        angle = math.pi / 4.0 + k * math.pi / 2.0
        tip = (px(6.9 * math.cos(angle)), px(6.9 * math.sin(angle)))
        base_a = (px(7.7 * math.cos(angle - 0.09)), px(7.7 * math.sin(angle - 0.09)))
        base_b = (px(7.7 * math.cos(angle + 0.09)), px(7.7 * math.sin(angle + 0.09)))
        pygame.draw.polygon(painted, (150, 225, 240), [tip, base_a, base_b])

    # The light pass: a ring of lights, alternating cyan and white.
    for k in range(LIGHT_COUNT):
        angle = k * math.tau / LIGHT_COUNT
        centre = (px(LIGHTS_AT * math.cos(angle)), px(LIGHTS_AT * math.sin(angle)))
        old.lamp(centre, CYAN if k % 2 else (255, 255, 244), 5)(painted)

    # Cut the disc: transparent outside it.
    pixels_alpha = pygame.surfarray.pixels_alpha(painted)
    pixels_alpha[:, :] = (band(0.0, RADIUS) * 255).astype(np.uint8).T
    del pixels_alpha
    pygame.image.save(painted, OUTPUT)
    print(f'Wrote {OUTPUT} ({SIZE} x {SIZE})')


if __name__ == '__main__':
    main()
