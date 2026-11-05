"""Generate common/resources/textures/outpost_annex.png, the texture of the annex of a size 3 outpost.

Run from the project root:  python tools/generate_annex_texture.py

The annex is a 30 m x 30 m x 15 m block behind the outpost building (Outpost.ANNEX_*). It is the newer part of the
structure: darker, cleaner and more geometric than the old building (tools/generate_outpost_texture.py, whose helpers
this reuses). Its levels are 3 m like the old building's, so the ledges at 3 m and 6 m continue the old building's
ledge and roof line, and the red band of the old ledge is at 3 m too. Between the ledges the walls are divided by
vertical seams into sections, four to a wall, and each section is made of recessed cells: mostly plain or grooved, a
few with a thin window, some with solar panels. Windows are rare, and some walls have none. The other cells are
rectangular compartments of different kinds (nested, split, gridded, stacked, with a plate or a hatch), drawn at
random from the seed. The ledges at 3 m and 9 m carry a red band.

Atlas 2048 x 2048, 32 pixels per metre on every face:
    front wall (towards the old building)  x 0..960,    y 0..480
    back wall                              x 976..1936, y 0..480
    left wall                              x 0..960,    y 496..976
    right wall                             x 976..1936, y 496..976
    roof (30 x 30 m)                       x 0..960,    y 992..1952
    dish (in plan, 8 m across)             x 976..1232, y 992..1248
    steel (plain patch)                    x 1240..1272, y 992..1024
Keep this layout when replacing the PNG by hand (graphics/outposts.py has the same rectangles).

As for the old building: a world without air or water, so no vents, fans or rain stains. The light pass (lit windows,
LED lines, beacons) is added after the weathering, so it stays bright.
"""

from __future__ import annotations
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

import generate_outpost_texture as old

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT = os.path.join(ROOT, 'common', 'resources', 'textures', 'outpost_annex.png')
EMBLEM = os.path.join(ROOT, 'common', 'resources', 'textures', 'PoliticalEntity.ThoseWhoShare.png')

ATLAS = 2048
FRONT = (0, 0, 960, 480)
BACK = (976, 0, 960, 480)
LEFT = (0, 496, 960, 480)
RIGHT = (976, 496, 960, 480)
ROOF = (0, 992, 960, 960)
DISH = (976, 992, 256, 256)  # the dish, in plan
STEEL = (1240, 992, 32, 32)  # plain steel, for the dish's mast, struts and feed

BODY = (146, 151, 160)  # between the old building's cladding (180) and the first version of this one (115)
CELL = (122, 128, 138)
SEAM = (46, 50, 58)
LEDGE = (62, 67, 76)
EDGE = (178, 186, 198)
GRAPHITE = (46, 50, 58)
CYAN = (110, 226, 255)
RED = old.RED
SOLAR = (16, 30, 62)

LEVEL = 96  # px: 3 m
SECTION = 240  # px: 7.5 m, four sections on a 30 m wall
WIDTH, HEIGHT = 960, 480

# What a cell holds, by (section, level) with level 0 at the top (12 m to 15 m) and 4 at the foot (0 m to 3 m).
Plan = Dict[Tuple[int, int], str]


# region Cells
def recess(surface: pygame.Surface, rect: pygame.Rect, fill: old.Colour) -> None:
    """A recessed cell: shadowed on its top and left edges, lit on the others."""
    pygame.draw.rect(surface, fill, rect)
    pygame.draw.line(surface, old.shade(fill, 0.5), rect.topleft, (rect.right - 1, rect.top), 3)
    pygame.draw.line(surface, old.shade(fill, 0.5), rect.topleft, (rect.left, rect.bottom - 1), 3)
    pygame.draw.line(surface, old.shade(fill, 1.4), (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 2)
    pygame.draw.line(surface, old.shade(fill, 1.4), (rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1), 2)


def compartments(surface: pygame.Surface, rect: pygame.Rect, kind: str) -> None:
    """The rectangular compartments a wall cell is made of: nested, split, gridded, or with a plate or a hatch."""
    deep, raised = old.shade(CELL, 0.86), old.shade(CELL, 1.1)
    if kind == 'inset':
        recess(surface, rect.inflate(-26, -22), deep)
    elif kind == 'split':  # two halves, as the leaves of a big door
        half = rect.width // 2
        recess(surface, pygame.Rect(rect.left + 8, rect.top + 8, half - 12, rect.height - 16), deep)
        recess(surface, pygame.Rect(rect.left + half + 4, rect.top + 8, half - 12, rect.height - 16), deep)
    elif kind == 'grid':  # four
        half_w, half_h = rect.width // 2, rect.height // 2
        for column in range(2):
            for row in range(2):
                recess(surface, pygame.Rect(rect.left + 8 + column * half_w, rect.top + 7 + row * half_h,
                                            half_w - 12, half_h - 10), deep if (column + row) % 2 else raised)
    elif kind == 'triple':  # three tall and narrow
        third = rect.width // 3
        for column in range(3):
            recess(surface, pygame.Rect(rect.left + 8 + column * third, rect.top + 8, third - 12, rect.height - 16),
                   deep if column == 1 else raised)
    elif kind == 'plate':  # a small raised plate with its bolts
        plate = pygame.Rect(0, 0, 64, 44)
        plate.center = rect.center
        pygame.draw.rect(surface, raised, plate)
        pygame.draw.rect(surface, EDGE, plate, 1)
        for x in (plate.left + 6, plate.right - 7):
            for y in (plate.top + 6, plate.bottom - 7):
                old.rivet(surface, x, y, 2)
    elif kind == 'hatch':  # a sealed service hatch, with its handle
        hatch = pygame.Rect(0, 0, 84, 50)
        hatch.center = rect.center
        recess(surface, hatch.inflate(14, 12), deep)
        pygame.draw.rect(surface, GRAPHITE, hatch)
        pygame.draw.rect(surface, EDGE, hatch, 1)
        pygame.draw.rect(surface, EDGE, (hatch.right - 18, hatch.centery - 10, 6, 20))
        old.hazard(surface, pygame.Rect(hatch.left, hatch.bottom - 7, hatch.width, 7), 7)
    elif kind == 'stacked':  # a big compartment over a low one
        split = rect.top + int(rect.height * 0.62)
        recess(surface, pygame.Rect(rect.left + 8, rect.top + 8, rect.width - 16, split - rect.top - 10), deep)
        recess(surface, pygame.Rect(rect.left + 8, split + 3, rect.width - 16, rect.bottom - split - 11), raised)
    elif kind == 'offset':  # a wide compartment beside a narrow one
        wide = rect.width * 2 // 3
        recess(surface, pygame.Rect(rect.left + 8, rect.top + 8, wide - 10, rect.height - 16), deep)
        recess(surface, pygame.Rect(rect.left + wide + 2, rect.top + 8, rect.width - wide - 10, rect.height - 16),
               raised)


COMPARTMENT_KINDS = ('plain', 'inset', 'split', 'grid', 'triple', 'plate', 'hatch', 'stacked', 'offset')
COMPARTMENT_WEIGHTS = (0.22, 0.14, 0.11, 0.1, 0.09, 0.07, 0.07, 0.11, 0.09)


def solar_cell(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """A field of photovoltaic glass in a silver frame: deep blue, a fine grid, a faint sheen."""
    pygame.draw.rect(surface, EDGE, rect.inflate(-10, -10))
    inner = rect.inflate(-20, -20)
    panel = pygame.Surface(inner.size)
    for y in range(inner.height):
        t = y / inner.height
        pygame.draw.line(panel, (int(SOLAR[0] + 12 * (1 - t)), int(SOLAR[1] + 20 * (1 - t)),
                                 int(SOLAR[2] + 36 * (1 - t))), (0, y), (inner.width, y))
    for x in range(0, inner.width, 24):
        pygame.draw.line(panel, (66, 92, 136), (x, 0), (x, inner.height))
    for y in range(0, inner.height, 24):
        pygame.draw.line(panel, (66, 92, 136), (0, y), (inner.width, y))
    pygame.draw.polygon(panel, (38, 58, 104), [(0, inner.height), (70, 0), (100, 0), (30, inner.height)])
    surface.blit(panel, inner.topleft)


def window_slit(surface: pygame.Surface, rect: pygame.Rect, lit: bool, tone: int, light: List[old.Emissive],
                rng: np.random.Generator) -> None:
    """A thin horizontal window in the middle of a cell."""
    slit = pygame.Rect(0, 0, 124, 14)
    slit.center = rect.center
    pygame.draw.rect(surface, GRAPHITE, slit.inflate(10, 10))
    pygame.draw.rect(surface, EDGE, slit.inflate(10, 10), 1)
    pygame.draw.rect(surface, (10, 14, 20), slit)
    if lit:
        top, bottom = old.LIT_TONES[tone]

        def paint(target: pygame.Surface, slit: pygame.Rect = slit) -> None:
            for row in range(slit.height):
                t = row / max(1, slit.height - 1)
                pygame.draw.line(target, tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
                                 (slit.left, slit.top + row), (slit.right - 1, slit.top + row))
            old.bloom(target, slit, top, 3)
        light.append(paint)
    else:
        glare = pygame.Surface(slit.size, pygame.SRCALPHA)
        shift = int(rng.integers(0, 60))
        pygame.draw.polygon(glare, (200, 225, 250, 70), [(shift, 0), (shift + 22, 0), (shift + 10, slit.height),
                                                          (shift - 12, slit.height)])
        surface.blit(glare, slit.topleft)


def led_line(y: int, x0: int, x1: int, colour: old.Colour = CYAN) -> old.Emissive:
    def paint(surface: pygame.Surface) -> None:
        old.bloom(surface, pygame.Rect(x0, y, x1 - x0, 2), colour, 3)
        pygame.draw.rect(surface, (230, 250, 255), (x0, y, x1 - x0, 2))
    return paint
# endregion


# region Faces
def panelled(size: Tuple[int, int], rng: np.random.Generator) -> pygame.Surface:
    """The body colour, with a faint difference from one 120 px panel to the next."""
    surface = pygame.Surface(size)
    surface.fill(BODY)
    for y in range(0, size[1], 120):
        for x in range(0, size[0], 120):
            pygame.draw.rect(surface, old.shade(BODY, 1.0 + float(rng.uniform(-0.03, 0.03))), (x, y, 120, 120))
    return surface


def paint_wall(rng: np.random.Generator, plan: Plan, emblem: Optional[pygame.Surface] = None
               ) -> Tuple[pygame.Surface, List[old.Emissive]]:
    """A wall of five levels of three metres and four sections, filled as `plan` says (a cell not in it is plain)."""
    surface = panelled((WIDTH, HEIGHT), rng)
    light: List[old.Emissive] = []

    chosen: Plan = {}
    for section in range(4):
        for level in range(5):
            rect = pygame.Rect(section * SECTION + 12, level * LEVEL + 10, SECTION - 24, LEVEL - 18)
            kind = plan.get((section, level))
            while kind is None:  # not planned: a kind that differs from the neighbours on the left and above
                kind = str(rng.choice(COMPARTMENT_KINDS, p=COMPARTMENT_WEIGHTS))
                if kind != 'plain' and kind in (chosen.get((section - 1, level)), chosen.get((section, level - 1))):
                    kind = None
            chosen[(section, level)] = kind
            recess(surface, rect, CELL)
            if kind in COMPARTMENT_KINDS:
                compartments(surface, rect, kind)
            elif kind == 'solar':
                solar_cell(surface, rect)
            elif kind in ('window', 'window lit'):
                window_slit(surface, rect, kind == 'window lit', int(rng.random() < 0.3), light, rng)
            elif kind == 'emblem' and emblem is not None:
                pygame.draw.circle(surface, GRAPHITE, rect.center, 38)
                pygame.draw.circle(surface, EDGE, rect.center, 38, 2)
                surface.blit(pygame.transform.smoothscale(emblem, (56, 56)), (rect.centerx - 28, rect.centery - 28))
                light.append(lambda target, centre=rect.center: pygame.draw.circle(target, CYAN, centre, 41, 2))

    # The seams between sections, and the ledges between levels: the ledge at 3 m has the red band of the old
    # building's, the one at 6 m is its roof line, with a line of light.
    for section in range(5):
        x = min(max(section * SECTION - 3, 0), WIDTH - 6)
        pygame.draw.rect(surface, SEAM, (x, 0, 6, HEIGHT))
        pygame.draw.line(surface, EDGE, (x + 6 if section < 4 else x - 1, 0), (x + 6 if section < 4 else x - 1, HEIGHT))
    for level in range(1, 5):
        old.trim(surface, pygame.Rect(0, level * LEVEL - 5, WIDTH, 10), LEDGE)
    for level in (2, 4):  # red bands at 9 m and 3 m
        pygame.draw.rect(surface, RED, (0, level * LEVEL - 1, WIDTH, 3))
    light.append(led_line(3 * LEVEL + 3, 0, WIDTH))
    old.trim(surface, pygame.Rect(0, 0, WIDTH, 10), LEDGE)  # parapet
    old.trim(surface, pygame.Rect(0, HEIGHT - 12, WIDTH, 12), GRAPHITE)  # plinth
    return surface, light


def paint_front(rng: np.random.Generator) -> Tuple[pygame.Surface, List[old.Emissive]]:
    """Towards the old building: above its roof (the top three levels) the wall is seen."""
    plan: Plan = {(1, 0): 'solar', (2, 0): 'solar', (0, 1): 'window lit', (3, 2): 'window'}
    return paint_wall(rng, plan)


def paint_back(rng: np.random.Generator, emblem: pygame.Surface) -> Tuple[pygame.Surface, List[old.Emissive]]:
    plan: Plan = {(0, 0): 'solar', (1, 0): 'solar', (2, 0): 'solar', (3, 0): 'solar', (1, 2): 'emblem',
                  (3, 3): 'window lit', (0, 4): 'window'}
    return paint_wall(rng, plan, emblem)


def paint_left(rng: np.random.Generator) -> Tuple[pygame.Surface, List[old.Emissive]]:
    plan: Plan = {(1, 0): 'solar', (2, 0): 'solar', (1, 1): 'solar', (2, 1): 'solar', (0, 2): 'window lit',
                  (3, 3): 'window'}
    return paint_wall(rng, plan)


def paint_right(rng: np.random.Generator) -> Tuple[pygame.Surface, List[old.Emissive]]:
    """A clean wall: one window only."""
    plan: Plan = {(0, 0): 'solar', (3, 0): 'solar', (2, 3): 'window lit'}
    return paint_wall(rng, plan)


def paint_roof(rng: np.random.Generator) -> Tuple[pygame.Surface, List[old.Emissive]]:
    w = h = 960
    surface = panelled((w, h), rng)
    light: List[old.Emissive] = []

    frame = pygame.Rect(0, 0, w, h)
    pygame.draw.rect(surface, LEDGE, frame, 26)
    pygame.draw.rect(surface, EDGE, frame.inflate(-52, -52), 2)
    light.append(led_line(30, 40, w - 40))
    light.append(led_line(h - 32, 40, w - 40))

    # Four fields of photovoltaic glass, deep blue with a fine silver grid and a sheen.
    for row in range(2):
        for col in range(2):
            field = pygame.Rect(70 + col * 420, 70 + row * 420, 380, 380)
            pygame.draw.rect(surface, EDGE, field.inflate(12, 12))
            panel = pygame.Surface(field.size)
            for y in range(field.height):
                t = y / field.height
                pygame.draw.line(panel, (int(SOLAR[0] + 14 * (1 - t)), int(SOLAR[1] + 22 * (1 - t)),
                                         int(SOLAR[2] + 40 * (1 - t))), (0, y), (field.width, y))
            for x in range(0, field.width, 32):
                pygame.draw.line(panel, (70, 96, 140), (x, 0), (x, field.height))
            for y in range(0, field.height, 32):
                pygame.draw.line(panel, (70, 96, 140), (0, y), (field.width, y))
            pygame.draw.polygon(panel, (40, 62, 110), [(0, field.height), (90, 0), (130, 0), (40, field.height)])
            surface.blit(panel, field.topleft)

    # In the middle, where the fields meet: the round deck of the dish (a real 3D one, see graphics/outposts.py), which
    # takes the inner corners of the four fields.
    centre = (w // 2, h // 2)
    for radius, colour in ((152, LEDGE), (146, EDGE), (142, BODY), (118, CELL), (112, BODY)):
        pygame.draw.circle(surface, colour, centre, radius)
    for k in range(16):
        angle = k * math.tau / 16
        pygame.draw.circle(surface, GRAPHITE, (centre[0] + int(math.cos(angle) * 130),
                                               centre[1] + int(math.sin(angle) * 130)), 3)
    light.extend(old.lamp(corner, (255, 70, 60), 6) for corner in ((50, 50), (w - 50, 50), (50, h - 50),
                                                                    (w - 50, h - 50)))
    return surface, light


def paint_dish(rng: np.random.Generator) -> pygame.Surface:
    """The dish, seen from the front as a flat disc (the 3D dish takes its texture coordinates from the plan): ivory
    panels, seams that match the segments of the mesh, and the hub."""
    size, centre, radius = DISH[2], DISH[2] // 2, DISH[2] // 2 - 4
    surface = pygame.Surface((size, size))
    surface.fill((214, 218, 222))
    for ring in range(1, 3):
        pygame.draw.circle(surface, (150, 156, 166), (centre, centre), radius * ring // 2, 2)
    for k in range(12):
        angle = k * math.tau / 12
        pygame.draw.line(surface, (150, 156, 166), (centre, centre),
                         (centre + int(math.cos(angle) * radius), centre + int(math.sin(angle) * radius)), 2)
    pygame.draw.circle(surface, EDGE, (centre, centre), radius, 3)
    pygame.draw.circle(surface, GRAPHITE, (centre, centre), 12)
    pygame.draw.circle(surface, EDGE, (centre, centre), 12, 2)
    array = old.to_array(surface)
    array *= (0.96 + 0.08 * old.noise(rng, size, size, 12, 12))[..., None]
    return old.to_surface(array)


def paint_steel(rng: np.random.Generator) -> pygame.Surface:
    patch = pygame.Surface(STEEL[2:])
    patch.fill((156, 162, 172))
    array = old.to_array(patch)
    array *= (0.92 + 0.16 * old.noise(rng, STEEL[2], STEEL[3], 8, 8))[..., None]
    return old.to_surface(array)
# endregion


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    rng = np.random.default_rng(2028)
    emblem = pygame.image.load(EMBLEM).convert_alpha()

    atlas = pygame.Surface((ATLAS, ATLAS))
    atlas.fill((26, 28, 32))
    faces = (
        (FRONT, old.finish(paint_front(rng), rng, 0.2)),
        (BACK, old.finish(paint_back(rng, emblem), rng, 0.2)),
        (LEFT, old.finish(paint_left(rng), rng, 0.2)),
        (RIGHT, old.finish(paint_right(rng), rng, 0.2)),
        (ROOF, old.finish(paint_roof(rng), rng, 0.15)),
        (DISH, paint_dish(rng)),
        (STEEL, paint_steel(rng)),
    )
    for region, face in faces:
        atlas.blit(face, region[:2])
    pygame.image.save(atlas, OUTPUT)
    print(f'Wrote {OUTPUT} ({ATLAS} x {ATLAS})')


if __name__ == '__main__':
    main()
