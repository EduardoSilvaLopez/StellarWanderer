"""Generate common/resources/presentation/cargo_ship.png, the picture of the ship in the cargo section of the outpost.

Run from the project root:  python tools/generate_ship_picture.py  (it reuses the noise and wear helpers of
generate_outpost_texture.py, so it must stay in tools/).

The ship is a 3D hull drawn with one fixed isometric camera, as the game icon is: its length runs from the upper left
to the lower right, its nose (the front, with the cockpit) faces the lower right, and the side faces the lower left. The
legs are struts from the hull's bottom corners to the ground, so they are attached. Its only windows are the cockpit's,
on the sloped windscreen at the front: the view from the cockpit. Its colours and the amber of its stripes are the game
icon's, and the grit is the outpost's (dust, pits, scratches), on the ship only. It is a static picture, not a texture.
"""

from __future__ import annotations
import math
import os
import sys

import numpy as np
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_outpost_texture import fbm, noise, to_array, to_surface  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT = os.path.join(ROOT, 'common', 'resources', 'presentation', 'cargo_ship.png')

W, H = 1024, 576
SCALE = 10.5  # pixels per unit of the ship's length, width and height
LENGTH, WIDTH, HEIGHT = 34.0, 15.0, 12.0  # the hull, in units
HOOD = 4.0  # the slope of the windscreen: it takes this much of the hull's length and height
LEG = 9.0  # the legs' length, from the hull's bottom to the ground

HULL = (110, 116, 126)
HULL_LIGHT = (168, 174, 184)
HULL_DARK = (44, 48, 58)
SEAM = (30, 33, 40)
AMBER = (236, 170, 42)
AMBER_DARK = (150, 100, 26)
GLASS = (22, 36, 50)
GLASS_LIGHT = (92, 124, 146)
GLOW = (255, 226, 150)
MOON = (128, 130, 134)
SHADOW = (0, 0, 0)
STAR = (250, 226, 130)


def project(x: float, y: float, z: float) -> tuple[float, float]:
    """The isometric camera: the hull's centre is the middle of the picture, and the ground is below it."""
    cx, cy = W / 2, H * 0.50
    sx = (x - z) * math.cos(math.radians(30)) * SCALE
    sy = (x + z) * math.sin(math.radians(30)) * SCALE - y * SCALE
    centre = project_centre()
    return cx + sx - centre[0], cy + sy - centre[1]


def project_centre() -> tuple[float, float]:
    """The projection of the hull's centre, so the hull is drawn in the middle."""
    x, z = LENGTH / 2, WIDTH / 2
    sx = (x - z) * math.cos(math.radians(30)) * SCALE
    sy = (x + z) * math.sin(math.radians(30)) * SCALE - HEIGHT / 2 * SCALE
    return sx, sy


def sky(surface: pygame.Surface, rng: np.random.Generator) -> None:
    for y in range(H):
        t = y / H
        colour = (int(4 + 16 * t), int(6 + 20 * t), int(12 + 30 * t))
        pygame.draw.line(surface, colour, (0, y), (W, y))
    for _ in range(220):
        x, y = int(rng.integers(0, W)), int(rng.integers(0, int(H * 0.6)))
        level = int(rng.integers(70, 200))
        surface.set_at((x, y), (level, level, min(255, level + 18)))
    for x, y, size in ((150, 110, 15), (858, 70, 9), (760, 430, 11), (232, 470, 7)):  # the icon's sparkles
        pygame.draw.line(surface, STAR, (x - size, y), (x + size, y), 2)
        pygame.draw.line(surface, STAR, (x, y - size), (x, y + size), 2)
        pygame.draw.circle(surface, STAR, (x, y), max(2, size // 4))


def ground(surface: pygame.Surface, rng: np.random.Generator) -> None:
    """The moon: grey regolith with soft relief and a few craters, lit from the upper left, under the ship."""
    top = int(H * 0.62)
    h = H - top
    relief = fbm(rng, W, h, 6)
    grain = noise(rng, W, h, W // 2, h // 2)
    slope = np.gradient(relief, axis=1) + 0.6 * np.gradient(relief, axis=0)
    light = np.clip(1.0 + 3.0 * slope + 0.12 * (grain - 0.5), 0.62, 1.3)
    depth = np.linspace(0.8, 1.1, h, dtype=np.float32)[:, None]
    array = np.array(MOON, np.float32)[None, None, :] * (light * depth)[..., None]
    surface.blit(to_surface(array), (0, top))
    for _ in range(40):
        cx, cy = int(rng.integers(0, W)), int(rng.integers(top + 8, H - 6))
        r = int(rng.integers(5, 20 if cy > H * 0.8 else 12))
        pygame.draw.ellipse(surface, (88, 90, 96), (cx - r, cy - r // 3, 2 * r, 2 * r // 3))
        pygame.draw.ellipse(surface, (150, 152, 158), (cx - r, cy + r // 5, 2 * r, max(2, r // 3)), 1)


def quad(surface, colour, points, outline=SEAM):
    pygame.draw.polygon(surface, colour, [project(*p) for p in points])
    pygame.draw.polygon(surface, outline, [project(*p) for p in points], 2)


def line3(surface, colour, a, b, width=2):
    pygame.draw.line(surface, colour, project(*a), project(*b), width)


def hull(surface: pygame.Surface, rng: np.random.Generator) -> None:
    L, Wd, Hh, h = LENGTH, WIDTH, HEIGHT, HOOD
    # Legs first: they hang from the four bottom corners, behind the hull where they are at the back.
    legs = [(3.0, 2.0), (3.0, Wd - 2.0), (L - 4.0, 2.0), (L - 4.0, Wd - 2.0)]
    for x, z in sorted(legs, key=lambda p: p[0] + p[1]):
        top = project(x, 0.0, z)
        ground_point = project(x, -LEG, z)
        pygame.draw.line(surface, SEAM, top, ground_point, 6)
        pygame.draw.line(surface, HULL_LIGHT, (top[0] - 1, top[1]), (ground_point[0] - 1, ground_point[1]), 1)
        pad = [project(x - 1.5, -LEG, z - 1.1), project(x + 1.5, -LEG, z - 1.1),
               project(x + 1.5, -LEG - 0.4, z + 1.1), project(x - 1.5, -LEG - 0.4, z + 1.1)]
        pygame.draw.polygon(surface, SEAM, pad)
        pygame.draw.polygon(surface, AMBER_DARK, pad, 2)

    # The side (z = Wd), facing the lower left: plates, seams, a long amber stripe.
    quad(surface, HULL, [(0, 0, Wd), (L, 0, Wd), (L, Hh, Wd), (0, Hh, Wd)])
    for x in range(4, int(L), 5):
        line3(surface, SEAM, (x, 0.6, Wd), (x, Hh - 0.6, Wd), 2)
    line3(surface, HULL_LIGHT, (0.4, Hh - 1.2, Wd), (L - 0.4, Hh - 1.2, Wd), 2)
    quad(surface, AMBER, [(1, 5.2, Wd), (L - 1, 5.2, Wd), (L - 1, 6.4, Wd), (1, 6.4, Wd)], AMBER_DARK)
    for x in range(2, int(L) - 1, 2):
        rivet_point = project(x, 9.8, Wd)
        pygame.draw.circle(surface, HULL_LIGHT, (int(rivet_point[0]), int(rivet_point[1])), 1)

    # The front (x = L), facing the lower right: the lower part, with headlights and a hazard band.
    front_top = Hh - h
    quad(surface, HULL, [(L, 0, 0), (L, 0, Wd), (L, front_top, Wd), (L, front_top, 0)])
    for z in range(3, int(Wd), 4):
        line3(surface, SEAM, (L, 0.6, z), (L, front_top - 0.6, z), 2)
    quad(surface, AMBER_DARK, [(L, 0.8, 1.2), (L, 2.6, 1.2), (L, 2.6, Wd - 1.2), (L, 0.8, Wd - 1.2)], SEAM)
    for z in range(2, int(Wd) - 1, 3):
        quad(surface, AMBER, [(L, 0.8, z), (L, 1.6, z), (L, 1.6, z + 1.2), (L, 0.8, z + 1.2)], AMBER_DARK)
    for z in (2.6, Wd - 2.6):
        pt = project(L, 4.8, z)
        pygame.draw.circle(surface, GLOW, (int(pt[0]), int(pt[1])), 5)
        pygame.draw.circle(surface, (255, 255, 240), (int(pt[0]), int(pt[1])), 2)

    # The top (y = Hh), facing up: the roof plates, a row of vents, a hatch.
    quad(surface, HULL_LIGHT, [(0, Hh, 0), (L - h, Hh, 0), (L - h, Hh, Wd), (0, Hh, Wd)])
    for x in range(4, int(L - h), 6):
        line3(surface, SEAM, (x, Hh, 0.6), (x, Hh, Wd - 0.6), 2)
    for x in range(3, int(L - h) - 2, 5):
        quad(surface, (70, 74, 84), [(x, Hh, 3.2), (x + 2.6, Hh, 3.2), (x + 2.6, Hh, 5.2), (x, Hh, 5.2)], SEAM)
    hatch = [(L - h - 9, Hh, 2.8), (L - h - 2, Hh, 2.8), (L - h - 2, Hh, Wd - 2.8), (L - h - 9, Hh, Wd - 2.8)]
    quad(surface, HULL, hatch)

    # The windscreen: the sloped face between the top and the front, with the cockpit's three panes. It is the only
    # window, and it is the view from the cockpit.
    def hood_point(t: float, z: float) -> tuple[float, float, float]:
        return (L - h * (1 - t), Hh - h * t, z)
    quad(surface, HULL_DARK, [hood_point(0, 0), hood_point(0, Wd), hood_point(1, Wd), hood_point(1, 0)])
    pane_edges = [1.8, 4.6, 7.3, Wd - 1.8]
    for i in range(3):
        z0, z1 = pane_edges[i] + 0.3, pane_edges[i + 1] - 0.3
        pane = [hood_point(0.22, z0), hood_point(0.22, z1), hood_point(0.9, z1), hood_point(0.9, z0)]
        pygame.draw.polygon(surface, GLASS, [project(*p) for p in pane])
        upper = [hood_point(0.24, z0 + 0.6), hood_point(0.24, z1 - 1.4), hood_point(0.56, z1 - 1.4),
                 hood_point(0.56, z0 + 0.6)]
        pygame.draw.polygon(surface, GLASS_LIGHT, [project(*p) for p in upper])
        pygame.draw.polygon(surface, SEAM, [project(*p) for p in pane], 2)
    for t in (0.8,):
        pygame.draw.polygon(surface, GLOW, [project(*hood_point(t, 2.0)), project(*hood_point(t, 2.4)),
                                            project(*hood_point(t + 0.04, 2.4)), project(*hood_point(t + 0.04, 2.0))])


def grit(layer: pygame.Surface, rng: np.random.Generator) -> pygame.Surface:
    """Dust, pits and scratches, on the ship only: the layer's own alpha says where the ship is, and it is kept."""
    width, height = layer.get_size()
    alpha = pygame.surfarray.array_alpha(layer).copy()
    array = to_array(layer)
    worn = fbm(rng, width, height, 5)
    pits = noise(rng, width, height, width, height)
    array *= (0.86 + 0.26 * worn + 0.08 * (pits - 0.5))[..., None]
    array *= (1.0 - 0.45 * (pits > 0.97))[..., None]
    result = to_surface(array)
    scratches = pygame.Surface((width, height), pygame.SRCALPHA)
    for _ in range(900):
        x0, y0 = int(rng.integers(0, width)), int(rng.integers(0, height))
        angle = float(rng.uniform(0.0, math.tau))
        length = int(rng.integers(4, 16))
        end = (x0 + int(math.cos(angle) * length), y0 + int(math.sin(angle) * length))
        light = rng.random() < 0.6
        colour = (230, 232, 236, int(rng.integers(18, 40))) if light else (0, 0, 0, int(rng.integers(20, 44)))
        pygame.draw.line(scratches, colour, (x0, y0), end, 1)
    result.blit(scratches, (0, 0))
    out = pygame.Surface((width, height), pygame.SRCALPHA)
    out.blit(result, (0, 0))
    pygame.surfarray.pixels_alpha(out)[:, :] = alpha
    return out


def shadow(surface: pygame.Surface) -> None:
    """A soft shadow on the moon, under the hull, from the light above."""
    pad = pygame.Surface((W, H), pygame.SRCALPHA)
    points = [project(0, -LEG, 0), project(LENGTH, -LEG, 0), project(LENGTH, -LEG, WIDTH), project(0, -LEG, WIDTH)]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    rect = pygame.Rect(min(xs) - 10, min(ys) - 4, max(xs) - min(xs) + 20, max(ys) - min(ys) + 14)
    pygame.draw.ellipse(pad, (0, 0, 0, 70), rect.inflate(-rect.width // 3, -rect.height // 3))
    surface.blit(pad, (0, 0))


def main() -> None:
    pygame.init()
    rng = np.random.default_rng(2027)
    background = pygame.Surface((W, H))
    sky(background, rng)
    ground(background, rng)
    shadow(background)
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    hull(layer, rng)
    layer = grit(layer, rng)
    background.blit(layer, (0, 0))
    pygame.image.save(background, OUTPUT)
    print(f'Wrote {OUTPUT} ({W} x {H})')


if __name__ == '__main__':
    main()
