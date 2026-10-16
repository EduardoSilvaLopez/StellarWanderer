"""Generate Resources/textures/outpost.png, the texture of the outpost building and its flag.

Run from the project root:  python Tools/generate_outpost_texture.py

The building is 24 m x 12 m x 6 m, two levels of 3 m. Atlas 2048 x 1024, 40 pixels per metre on every face:
    front wall (door side, 24 x 6 m)   x 0..960,      y 0..240
    back wall  (24 x 6 m)              x 0..960,      y 248..488
    roof       (24 x 12 m)             x 0..960,      y 496..976
    left side  (12 x 6 m)              x 976..1456,   y 0..240
    right side (12 x 6 m)              x 976..1456,   y 248..488
    flag       (3:2, any size on the quad)  x 1472..1856, y 0..256
    steel      (plain patch, for the flagpole)  x 1472..1504, y 264..296
Keep this layout when replacing the PNG by hand (Graphics/outposts.py has the same rectangles).

It is a building for a world without air or water: sealed hatches and a docking collar, round portholes, thermal
radiator panels, gold insulation foil, thruster clusters with soot, EVA handrails, a sensor dome and beacons. No
vents, fans or drain pipes. The wear is dust, micrometeorite pits, sun-bleaching and a few scratches; there is no rain
and no rust. Each face is painted flat, weathered lightly, and last the light is added (lit windows, lamps), so that
stays bright.
"""

from __future__ import annotations
import math
import os
from typing import Callable, List, Tuple

import numpy as np
import pygame

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT = os.path.join(ROOT, 'Resources', 'textures', 'outpost.png')
EMBLEM = os.path.join(ROOT, 'Resources', 'textures', 'PoliticalEntity.1.png')
STENCIL_FONT = os.path.join(ROOT, 'Resources', 'fonts', 'Orbitron.ttf')

ATLAS_W, ATLAS_H = 2048, 1024

FRONT = (0, 0, 960, 240)
BACK = (0, 248, 960, 240)
ROOF = (0, 496, 960, 480)
LEFT = (976, 0, 480, 240)
RIGHT = (976, 248, 480, 240)
FLAG = (1472, 0, 384, 256)
METAL = (1472, 264, 32, 32)

Colour = Tuple[int, int, int]
Emissive = Callable[[pygame.Surface], None]

# Hull: light composite panels on a dark frame, with the entity's red as the only accent.
PANEL_LIGHT = (200, 202, 202)
PANEL = (178, 181, 184)
FRAME = (62, 66, 74)
FRAME_LIGHT = (126, 132, 142)
FRAME_DARK = (40, 43, 50)
PLINTH = (70, 72, 78)
RED = (176, 30, 34)
GOLD_FOIL = (192, 142, 52)
RADIATOR = (34, 38, 46)
SOLAR = (24, 38, 68)
ROOF_BASE = (104, 108, 114)
HAZARD_A = (226, 180, 36)
HAZARD_B = (28, 28, 28)
CLOTH_RED = (220, 6, 10)
GOLD = (238, 192, 56)
DUST = (128, 118, 104)

LEVEL_SPLIT = 120  # y of the ledge between the two levels, on a 240 px tall wall


# ---------------------------------------------------------------------------------------------------------------
# Noise and array helpers

def noise(rng: np.random.Generator, w: int, h: int, cells_x: int, cells_y: int) -> np.ndarray:
    """Smooth random values 0..1 as an (h, w) array: random cells, scaled up with smoothing."""
    cells_x, cells_y = max(2, cells_x), max(2, cells_y)
    small = (rng.random((cells_x, cells_y)) * 255).astype(np.uint8)
    surface = pygame.Surface((cells_x, cells_y), 0, 24)
    pygame.surfarray.blit_array(surface, np.repeat(small[:, :, None], 3, axis=2))
    big = pygame.transform.smoothscale(surface, (w, h))
    return pygame.surfarray.array3d(big)[:, :, 0].astype(np.float32).T / 255.0


def fbm(rng: np.random.Generator, w: int, h: int, cells: int, octaves: int = 4) -> np.ndarray:
    """Layered noise 0..1: big blotches plus finer and finer detail."""
    total = np.zeros((h, w), np.float32)
    amplitude, weight = 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * noise(rng, w, h, cells * 2 ** octave, max(2, cells * 2 ** octave * h // w))
        weight += amplitude
        amplitude *= 0.5
    return total / weight


def to_array(surface: pygame.Surface) -> np.ndarray:
    return pygame.surfarray.array3d(surface).transpose(1, 0, 2).astype(np.float32)


def to_surface(array: np.ndarray) -> pygame.Surface:
    return pygame.surfarray.make_surface(np.clip(array, 0, 255).astype(np.uint8).transpose(1, 0, 2))


def shade(colour: Colour, factor: float) -> Colour:
    return tuple(max(0, min(255, int(value * factor))) for value in colour)  # type: ignore[return-value]


# ---------------------------------------------------------------------------------------------------------------
# Wear: dust, micrometeorite pits, sun-bleaching, a few scratches. No rain, no rust.

def weather(surface: pygame.Surface, rng: np.random.Generator, strength: float = 1.0) -> pygame.Surface:
    width, height = surface.get_size()
    array = to_array(surface)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]

    mottle = fbm(rng, width, height, 4)
    grain = noise(rng, width, height, width // 2, height // 2)
    array *= (0.93 + 0.14 * mottle + 0.05 * (grain - 0.5))[..., None]

    # Dust thrown up at the foot of the walls, in patches.
    foot = np.clip((y - 0.55) / 0.45, 0.0, 1.0) ** 1.4 * (0.45 + 0.55 * mottle) * 0.55 * strength
    array = array * (1.0 - foot)[..., None] + np.array(DUST, np.float32) * foot[..., None]

    # Sun-bleaching: the upper part is a little paler.
    array *= (1.0 + 0.05 * strength * (1.0 - y))[..., None]

    # Micrometeorite pits: sparse dark specks with a pale rim.
    pits = noise(rng, width, height, width, height)
    array *= (1.0 - 0.35 * strength * (pits > 0.965))[..., None]
    array *= (1.0 + 0.12 * strength * ((pits > 0.94) & (pits <= 0.945)))[..., None]

    from_left_right = np.minimum(np.arange(width), np.arange(width - 1, -1, -1)).astype(np.float32)[None, :]
    from_top_bottom = np.minimum(np.arange(height), np.arange(height - 1, -1, -1)).astype(np.float32)[:, None]
    edge = np.minimum(from_left_right, from_top_bottom)
    array *= (0.88 + 0.12 * np.clip(edge / 6.0, 0.0, 1.0))[..., None]

    result = to_surface(array)
    scratches = pygame.Surface((width, height), pygame.SRCALPHA)
    for _ in range(int(width * height // 12000 * strength)):
        x0, y0 = int(rng.integers(0, width)), int(rng.integers(0, height))
        angle = float(rng.uniform(0.0, math.tau))
        length = int(rng.integers(5, 28))
        end = (x0 + int(math.cos(angle) * length), y0 + int(math.sin(angle) * length))
        colour = (240, 240, 236, int(rng.integers(14, 34))) if rng.random() < 0.6 else (0, 0, 0, int(rng.integers(16, 36)))
        pygame.draw.line(scratches, colour, (x0, y0), end, 1)
    result.blit(scratches, (0, 0))
    return result


# ---------------------------------------------------------------------------------------------------------------
# Painting helpers

def rivet(surface: pygame.Surface, x: int, y: int, radius: int = 2) -> None:
    pygame.draw.circle(surface, (40, 42, 46), (x + 1, y + 1), radius)
    pygame.draw.circle(surface, (150, 152, 158), (x, y), radius)
    pygame.draw.circle(surface, (214, 216, 220), (x - 1, y - 1), max(1, radius - 1))


def circle_bolts(surface: pygame.Surface, centre: Tuple[int, int], radius: int, count: int, size: int = 2) -> None:
    for k in range(count):
        angle = k * math.tau / count
        rivet(surface, centre[0] + int(math.cos(angle) * radius), centre[1] + int(math.sin(angle) * radius), size)


def trim(surface: pygame.Surface, rect: pygame.Rect, colour: Colour, rivets_every: int = 0) -> None:
    """A raised strip: light edge on top, dark edge below, optional rivets along its middle."""
    pygame.draw.rect(surface, colour, rect)
    pygame.draw.line(surface, shade(colour, 1.35), rect.topleft, (rect.right - 1, rect.top))
    pygame.draw.line(surface, shade(colour, 0.55), (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
    if rivets_every:
        for x in range(rect.left + rivets_every // 2, rect.right, rivets_every):
            rivet(surface, x, rect.centery, 2)


def panel_grid(surface: pygame.Surface, rect: pygame.Rect, panel_w: int, panel_h: int, base: Colour,
               rng: np.random.Generator) -> None:
    """Composite cladding panels, each a little different, with bevelled seams and corner bolts."""
    for row, y in enumerate(range(rect.top, rect.bottom, panel_h)):
        offset = (panel_w // 2) if row % 2 else 0
        for x in range(rect.left - offset, rect.right, panel_w):
            cell = pygame.Rect(x, y, panel_w, min(panel_h, rect.bottom - y)).clip(rect)
            if cell.width <= 0 or cell.height <= 0:
                continue
            pygame.draw.rect(surface, shade(base, 1.0 + float(rng.uniform(-0.05, 0.05))), cell)
            pygame.draw.line(surface, shade(base, 0.66), cell.topleft, (cell.right - 1, cell.top), 2)
            pygame.draw.line(surface, shade(base, 0.66), cell.topleft, (cell.left, cell.bottom - 1), 2)
            pygame.draw.line(surface, shade(base, 1.10), (cell.left + 2, cell.top + 2), (cell.right - 1, cell.top + 2))
            if cell.width >= panel_w and cell.height >= panel_h:
                for rx, ry in ((6, 6), (panel_w - 7, 6), (6, panel_h - 7), (panel_w - 7, panel_h - 7)):
                    rivet(surface, cell.left + rx, cell.top + ry, 1)


def hazard(surface: pygame.Surface, rect: pygame.Rect, step: int = 14) -> None:
    previous_clip = surface.get_clip()
    surface.set_clip(rect)
    surface.fill(HAZARD_A, rect)
    for x in range(rect.left - rect.height, rect.right + rect.height, step * 2):
        pygame.draw.polygon(surface, HAZARD_B, [
            (x, rect.bottom), (x + step, rect.bottom), (x + step + rect.height, rect.top), (x + rect.height, rect.top)])
    surface.set_clip(previous_clip)


def stencil(surface: pygame.Surface, text: str, center: Tuple[int, int], size: int,
            colour: Colour = (46, 50, 58), rotation: int = 0) -> None:
    font = pygame.font.Font(STENCIL_FONT, size)
    label = pygame.transform.rotate(font.render(text, True, colour), rotation)
    surface.blit(label, label.get_rect(center=center))


def handrail(surface: pygame.Surface, x0: int, x1: int, y: int) -> None:
    """An EVA handrail: a yellow bar on two stand-offs per metre."""
    for x in range(x0, x1, 40):
        pygame.draw.rect(surface, FRAME_DARK, (x, y, 3, 7))
        pygame.draw.rect(surface, FRAME_DARK, (x + 30, y, 3, 7))
        pygame.draw.rect(surface, HAZARD_A, (x, y - 2, 33, 4))
        pygame.draw.line(surface, (252, 232, 150), (x, y - 2), (x + 32, y - 2))


def radiator(surface: pygame.Surface, rect: pygame.Rect, label: str = '') -> None:
    """A thermal radiator panel: dark plates with a fine grid of coolant lines and manifold bands."""
    pygame.draw.rect(surface, FRAME, rect.inflate(8, 8))
    pygame.draw.rect(surface, FRAME_LIGHT, rect.inflate(8, 8), 1)
    pygame.draw.rect(surface, RADIATOR, rect)
    for x in range(rect.left + 6, rect.right, 9):
        pygame.draw.line(surface, (58, 64, 76), (x, rect.top + 2), (x, rect.bottom - 3))
    for y in (rect.top + rect.height // 4, rect.centery, rect.bottom - rect.height // 4):
        pygame.draw.rect(surface, FRAME, (rect.left, y - 2, rect.width, 5))
        pygame.draw.line(surface, FRAME_LIGHT, (rect.left, y - 2), (rect.right - 1, y - 2))
    pygame.draw.line(surface, (92, 100, 116), rect.topleft, (rect.right - 1, rect.top))
    if label:
        stencil(surface, label, (rect.centerx, rect.bottom + 12), 8, (46, 50, 58))


def mli_patch(surface: pygame.Surface, rect: pygame.Rect, rng: np.random.Generator) -> None:
    """Gold insulation foil: crinkled ridges that catch the light, taped at the edges."""
    w, h = rect.size
    crumple = fbm(rng, w, h, max(2, w // 10), 3)                 # soft crumpled relief
    fine = noise(rng, w, h, w // 2, h // 2)
    slope = np.gradient(crumple, axis=1) + 0.7 * np.gradient(crumple, axis=0)   # facets facing the light are brighter
    lightness = np.clip(0.92 + 5.5 * slope + 0.08 * (fine - 0.5), 0.5, 1.45)
    foil = np.array(GOLD_FOIL, np.float32)[None, None, :] * lightness[..., None]
    patch = to_surface(foil)
    pygame.draw.rect(patch, (70, 70, 74), patch.get_rect(), 3)
    surface.blit(patch, rect.topleft)


def docking_collar(surface: pygame.Surface, centre: Tuple[int, int], radius: int) -> None:
    """A round docking hatch: bolted flange, seal ring, cross-seamed door and a lock hub."""
    pygame.draw.circle(surface, FRAME_DARK, centre, radius + 11)
    pygame.draw.circle(surface, FRAME_LIGHT, centre, radius + 9)
    pygame.draw.circle(surface, FRAME, centre, radius + 3)
    pygame.draw.circle(surface, (22, 24, 28), centre, radius)
    pygame.draw.circle(surface, (150, 154, 160), centre, radius - 4)
    pygame.draw.line(surface, FRAME_DARK, (centre[0] - radius + 4, centre[1]), (centre[0] + radius - 4, centre[1]), 3)
    pygame.draw.line(surface, FRAME_DARK, (centre[0], centre[1] - radius + 4), (centre[0], centre[1] + radius - 4), 3)
    pygame.draw.circle(surface, FRAME, centre, 10)
    pygame.draw.circle(surface, FRAME_LIGHT, centre, 10, 2)
    circle_bolts(surface, centre, radius + 6, 14, 2)


def porthole(surface: pygame.Surface, centre: Tuple[int, int], radius: int) -> None:
    pygame.draw.circle(surface, FRAME_DARK, centre, radius + 10)
    pygame.draw.circle(surface, FRAME_LIGHT, centre, radius + 8)
    pygame.draw.circle(surface, FRAME, centre, radius + 3)
    circle_bolts(surface, centre, radius + 6, 8, 1)
    pygame.draw.circle(surface, (10, 12, 16), centre, radius)


def sensor_dome(surface: pygame.Surface, centre: Tuple[int, int], radius: int) -> None:
    pygame.draw.circle(surface, FRAME_DARK, centre, radius + 5)
    pygame.draw.circle(surface, FRAME_LIGHT, centre, radius + 5, 2)
    for r in range(radius, 0, -1):
        t = r / radius
        pygame.draw.circle(surface, (int(20 + 90 * (1 - t)), int(28 + 100 * (1 - t)), int(40 + 120 * (1 - t))), centre, r)
    pygame.draw.ellipse(surface, (190, 214, 236), (centre[0] - radius // 2, centre[1] - radius + 3, radius // 2, radius // 3))


def thruster_cluster(surface: pygame.Surface, centre: Tuple[int, int]) -> None:
    """Four attitude thrusters, with soot streaked away from the nozzles."""
    soot = pygame.Surface((70, 80), pygame.SRCALPHA)
    pygame.draw.ellipse(soot, (10, 10, 12, 36), (8, 4, 54, 74))
    pygame.draw.ellipse(soot, (10, 10, 12, 34), (20, 18, 30, 60))
    surface.blit(soot, (centre[0] - 35, centre[1] - 66))
    for dx, dy in ((-11, -11), (11, -11), (-11, 11), (11, 11)):
        pygame.draw.circle(surface, FRAME_DARK, (centre[0] + dx, centre[1] + dy), 10)
        pygame.draw.circle(surface, FRAME_LIGHT, (centre[0] + dx, centre[1] + dy), 10, 1)
        pygame.draw.circle(surface, (8, 8, 10), (centre[0] + dx, centre[1] + dy), 6)
        pygame.draw.circle(surface, (74, 50, 36), (centre[0] + dx, centre[1] + dy), 3)


def airlock_door(surface: pygame.Surface, door: pygame.Rect, label: str) -> None:
    """A sealed airlock: heavy frame, hatch leaf, round viewport, seals, keypad and hazard feet."""
    pygame.draw.rect(surface, FRAME_LIGHT, door.inflate(18, 12))
    pygame.draw.rect(surface, FRAME_DARK, door.inflate(18, 12), 3)
    pygame.draw.rect(surface, FRAME, door)
    pygame.draw.rect(surface, FRAME_DARK, door.inflate(-12, -12), 2)
    pygame.draw.line(surface, FRAME_DARK, (door.centerx, door.top), (door.centerx, door.bottom), 4)
    for y in (door.top + 8, door.bottom - 8):
        for x in (door.left + 8, door.right - 8):
            rivet(surface, x, y, 2)
    pygame.draw.circle(surface, FRAME_DARK, (door.centerx, door.top + 28), 16)
    pygame.draw.circle(surface, FRAME_LIGHT, (door.centerx, door.top + 28), 16, 2)
    pygame.draw.circle(surface, (16, 22, 28), (door.centerx, door.top + 28), 12)
    pygame.draw.rect(surface, (20, 22, 26), (door.right + 16, door.centery - 6, 12, 24))
    for k in range(6):
        pygame.draw.rect(surface, (96, 102, 110), (door.right + 18 + (k % 2) * 5, door.centery - 3 + (k // 2) * 6, 3, 3))
    hazard(surface, pygame.Rect(door.left - 14, door.bottom - 12, door.width + 28, 12))
    stencil(surface, label, (door.centerx, door.top + 62), 8, (214, 214, 206))


def window_socket(surface: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, FRAME_DARK, rect.inflate(12, 12))
    pygame.draw.rect(surface, FRAME_LIGHT, rect.inflate(12, 12), 1)
    pygame.draw.rect(surface, FRAME, rect.inflate(6, 6))
    pygame.draw.rect(surface, (10, 12, 16), rect)


LIT_TONES = (((206, 224, 230), (128, 160, 178)), ((248, 214, 158), (206, 142, 78)))   # cool white, warm amber


def glass_fill(size: Tuple[int, int], lit: bool, tone: int, rng: np.random.Generator) -> pygame.Surface:
    """The look of a pane: an interior light with dark shapes in it, or a dull reflection of the sky."""
    w, h = size
    glass = pygame.Surface(size, pygame.SRCALPHA)
    top, bottom = LIT_TONES[tone]
    for row in range(h):
        t = row / max(1, h - 1)
        if lit:
            colour = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        else:
            colour = (int(44 - 24 * t), int(60 - 30 * t), int(80 - 40 * t))
        pygame.draw.line(glass, colour, (0, row), (w, row))
    if lit:
        pygame.draw.rect(glass, (255, 255, 250, 200), (2, 1, w - 4, 2))   # the ceiling light strip
        for _ in range(max(1, w // 45)):   # consoles, as a few low dark shapes
            bx, bw = int(rng.integers(0, max(1, w - 10))), int(rng.integers(8, 20))
            pygame.draw.rect(glass, (50, 62, 74, int(rng.integers(50, 100))), (bx, h - int(rng.integers(5, 10)), bw, 12))
    else:
        pygame.draw.polygon(glass, (200, 220, 240, 34), [(w // 4, 0), (w // 2, 0), (w // 4, h), (0, h)])
    return glass


def window_glass(rect: pygame.Rect, lit: bool, tone: int, seed: int) -> Emissive:
    def paint(surface: pygame.Surface) -> None:
        surface.blit(glass_fill(rect.size, lit, tone, np.random.default_rng(seed)), rect.topleft)
        if lit:
            bloom(surface, rect, LIT_TONES[tone][0])
        pygame.draw.rect(surface, (0, 0, 0), (rect.left, rect.top, rect.width, 2))
    return paint


def porthole_glass(centre: Tuple[int, int], radius: int, lit: bool, tone: int) -> Emissive:
    def paint(surface: pygame.Surface) -> None:
        top, bottom = LIT_TONES[tone]
        for r in range(radius, 0, -1):
            t = r / radius
            if lit:
                colour = tuple(int(bottom[i] + (top[i] - bottom[i]) * (1.0 - t)) for i in range(3))
            else:
                colour = (int(18 + 30 * (1 - t)), int(26 + 36 * (1 - t)), int(36 + 46 * (1 - t)))
            pygame.draw.circle(surface, colour, centre, r)
        if lit:
            bloom(surface, pygame.Rect(centre[0] - radius, centre[1] - radius, 2 * radius, 2 * radius), top, 3)
    return paint


def bloom(surface: pygame.Surface, rect: pygame.Rect, colour: Colour, layers: int = 4) -> None:
    """A soft glow around a light, as stacked translucent rectangles."""
    glow = pygame.Surface((rect.width + 40, rect.height + 40), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        pygame.draw.rect(glow, (*colour, 11), pygame.Rect(20, 20, rect.width, rect.height).inflate(i * 6, i * 6),
                         border_radius=i * 3)
    surface.blit(glow, (rect.left - 20, rect.top - 20))


def lamp(centre: Tuple[int, int], colour: Colour, radius: int = 4) -> Emissive:
    def paint(surface: pygame.Surface) -> None:
        bloom(surface, pygame.Rect(centre[0] - radius, centre[1] - radius, 2 * radius, 2 * radius), colour, 3)
        pygame.draw.circle(surface, shade(colour, 0.7), centre, radius)
        pygame.draw.circle(surface, (255, 255, 244), centre, max(1, radius - 2))
    return paint


def lit_choice(rng: np.random.Generator, probability: float) -> Tuple[bool, int]:
    return bool(rng.random() < probability), int(rng.random() < 0.2)


# ---------------------------------------------------------------------------------------------------------------
# Faces. Each returns the painted face and the painters of its light pass.

def base_wall(rng: np.random.Generator, w: int = 960, h: int = 240) -> pygame.Surface:
    """The shared two-level shell: parapet, upper cladding, ledge with the red band, lower cladding, plinth."""
    surface = pygame.Surface((w, h))
    surface.fill(PANEL)
    panel_grid(surface, pygame.Rect(0, 14, w, LEVEL_SPLIT - 14), 80, 60, PANEL_LIGHT, rng)
    panel_grid(surface, pygame.Rect(0, LEVEL_SPLIT + 8, w, h - LEVEL_SPLIT - 8 - 16), 80, 60, PANEL, rng)
    trim(surface, pygame.Rect(0, 0, w, 14), FRAME, 40)                                    # parapet
    trim(surface, pygame.Rect(0, LEVEL_SPLIT - 8, w, 16), FRAME_DARK)                     # ledge between the levels
    pygame.draw.rect(surface, RED, (0, LEVEL_SPLIT - 2, w, 4))                            # the entity's red band
    shadow = pygame.Surface((w, 12), pygame.SRCALPHA)
    for i in range(12):
        pygame.draw.line(shadow, (0, 0, 0, 64 - i * 5), (0, i), (w, i))
    surface.blit(shadow, (0, LEVEL_SPLIT + 8))
    trim(surface, pygame.Rect(0, h - 16, w, 16), PLINTH)                                   # plinth
    return surface


def paint_front(rng: np.random.Generator) -> Tuple[pygame.Surface, List[Emissive]]:
    w, h = 960, 240
    surface = base_wall(rng)
    light: List[Emissive] = []
    floor = h - 16

    # Upper level: foil, observation windows, handrail, radiator, sensor dome.
    mli_patch(surface, pygame.Rect(30, 32, 100, 58), rng)
    for i in range(5):
        rect = pygame.Rect(172 + i * 112, 42, 92, 38)
        window_socket(surface, rect)
        lit, tone = lit_choice(rng, 0.78)
        light.append(window_glass(rect, lit, tone, int(rng.integers(0, 10 ** 6))))
    handrail(surface, 172, 700, 100)
    radiator(surface, pygame.Rect(748, 30, 130, 60), 'THERMAL')
    sensor_dome(surface, (924, 62), 18)
    stencil(surface, 'TWS / OP-03', (452, 26), 9)
    light.append(lamp((8, 7), (255, 70, 60), 3))

    # Lower level: docking collar on the left, the airlock in the middle, portholes and thrusters on the right.
    docking_collar(surface, (190, 176), 36)
    stencil(surface, 'DOCK A', (190, 134), 9)
    door = pygame.Rect(432, 134, 96, floor - 134)
    airlock_door(surface, door, 'PRESSURE LOCK')
    light += [lamp((door.centerx, 143), (80, 230, 110), 3), lamp((door.centerx, door.top + 28), (90, 220, 230), 8),
              lamp((door.left - 28, 150), (255, 170, 60), 4), lamp((door.right + 36, 150), (255, 170, 60), 4)]
    handrail(surface, 330, 400, 190)
    handrail(surface, 560, 630, 190)
    for i in range(3):
        centre = (676 + i * 82, 176)
        porthole(surface, centre, 18)
        lit, tone = lit_choice(rng, 0.8)
        light.append(porthole_glass(centre, 18, lit, tone))
    thruster_cluster(surface, (916, 178))
    stencil(surface, 'EVA ACCESS', (door.centerx, 128), 8)
    return surface, light


def paint_back(rng: np.random.Generator) -> Tuple[pygame.Surface, List[Emissive]]:
    w, h = 960, 240
    surface = base_wall(rng)
    light: List[Emissive] = []
    floor = h - 16

    mli_patch(surface, pygame.Rect(40, 34, 120, 56), rng)
    for i in range(5):
        rect = pygame.Rect(190 + i * 66, 48, 40, 28)
        window_socket(surface, rect)
        lit, tone = lit_choice(rng, 0.25)
        light.append(window_glass(rect, lit, tone, int(rng.integers(0, 10 ** 6))))
    radiator(surface, pygame.Rect(540, 28, 180, 62), 'THERMAL A')
    radiator(surface, pygame.Rect(750, 28, 180, 62), 'THERMAL B')

    radiator(surface, pygame.Rect(150, 142, 230, 56), 'THERMAL C')
    docking_collar(surface, (560, 176), 36)
    stencil(surface, 'DOCK B', (560, 134), 9)
    thruster_cluster(surface, (80, 178))
    thruster_cluster(surface, (700, 178))
    service = pygame.Rect(830, 136, 52, floor - 136)
    pygame.draw.rect(surface, FRAME_DARK, service.inflate(12, 8))
    pygame.draw.rect(surface, FRAME, service)
    pygame.draw.line(surface, FRAME_DARK, (service.centerx, service.top), (service.centerx, service.bottom), 3)
    hazard(surface, pygame.Rect(service.left - 8, floor - 10, service.width + 16, 10))
    stencil(surface, 'SERVICE', (service.centerx, 128), 8)
    light += [lamp((service.centerx, 142), (255, 170, 60), 4), lamp((952, 8), (255, 70, 60), 3)]
    handrail(surface, 410, 490, 186)
    return surface, light


def paint_side(rng: np.random.Generator, number: str, door_x: int, ports_x: int) -> Tuple[pygame.Surface, List[Emissive]]:
    w, h = 480, 240
    surface = base_wall(rng, w, h)
    light: List[Emissive] = []
    floor = h - 16

    door = pygame.Rect(door_x, 136, 62, floor - 136)
    airlock_door_small(surface, door, number)
    light.append(lamp((door.centerx, door.top + 10), (255, 170, 60), 4))
    for i in range(2):
        centre = (ports_x + i * 70, 176)
        porthole(surface, centre, 16)
        lit, tone = lit_choice(rng, 0.7)
        light.append(porthole_glass(centre, 16, lit, tone))
    for i in range(3):
        rect = pygame.Rect(60 + i * 140, 44, 90, 36)
        window_socket(surface, rect)
        lit, tone = lit_choice(rng, 0.7)
        light.append(window_glass(rect, lit, tone, int(rng.integers(0, 10 ** 6))))
    handrail(surface, 60, 420, 100)
    return surface, light


def airlock_door_small(surface: pygame.Surface, door: pygame.Rect, label: str) -> None:
    pygame.draw.rect(surface, FRAME_LIGHT, door.inflate(14, 8))
    pygame.draw.rect(surface, FRAME_DARK, door.inflate(14, 8), 3)
    pygame.draw.rect(surface, FRAME, door)
    pygame.draw.line(surface, FRAME_DARK, (door.centerx, door.top), (door.centerx, door.bottom), 3)
    pygame.draw.circle(surface, FRAME_DARK, (door.centerx, door.top + 30), 12)
    pygame.draw.circle(surface, (16, 22, 28), (door.centerx, door.top + 30), 8)
    hazard(surface, pygame.Rect(door.left - 8, door.bottom - 10, door.width + 16, 10))
    stencil(surface, label, (door.centerx, door.top + 58), 14, (214, 214, 206))


def paint_roof(rng: np.random.Generator) -> Tuple[pygame.Surface, List[Emissive]]:
    w, h = 960, 480
    surface = pygame.Surface((w, h))
    surface.fill(ROOF_BASE)
    light: List[Emissive] = []

    for x in range(60, w, 120):
        pygame.draw.line(surface, shade(ROOF_BASE, 0.75), (x, 20), (x, h - 20), 2)
    trim(surface, pygame.Rect(0, 0, w, 20), FRAME)
    trim(surface, pygame.Rect(0, h - 20, w, 20), FRAME)
    pygame.draw.rect(surface, FRAME, pygame.Rect(0, 0, 20, h))
    pygame.draw.rect(surface, FRAME, pygame.Rect(w - 20, 0, 20, h))
    pygame.draw.rect(surface, FRAME_DARK, pygame.Rect(20, 20, w - 40, h - 40), 3)

    # Solar array: two rows of panels with silver frames.
    for row in range(2):
        for col in range(5):
            panel = pygame.Rect(50 + col * 112, 50 + row * 150, 104, 134)
            pygame.draw.rect(surface, FRAME_LIGHT, panel)
            inner = panel.inflate(-6, -6)
            pygame.draw.rect(surface, SOLAR, inner)
            for x in range(inner.left + 26, inner.right, 26):
                pygame.draw.line(surface, (46, 66, 106), (x, inner.top), (x, inner.bottom))
            for y in range(inner.top + 22, inner.bottom, 22):
                pygame.draw.line(surface, (46, 66, 106), (inner.left, y), (inner.right, y))
            pygame.draw.polygon(surface, (80, 110, 160), [
                (inner.left, inner.bottom), (inner.left + 24, inner.top), (inner.left + 40, inner.top), (inner.left + 16, inner.bottom)])

    # Radiators, a sensor dome, the comms dish, a sealed hatch.
    radiator(surface, pygame.Rect(650, 50, 110, 96), 'THERMAL')
    radiator(surface, pygame.Rect(790, 50, 110, 96), 'THERMAL')
    sensor_dome(surface, (710, 214), 22)
    dish = (800, 330)
    for radius, colour in ((74, FRAME_LIGHT), (68, (186, 190, 196)), (48, (164, 168, 174)), (28, (140, 144, 150)), (8, FRAME_DARK)):
        pygame.draw.circle(surface, colour, dish, radius)
    pygame.draw.line(surface, FRAME_DARK, dish, (dish[0] + 58, dish[1] - 34), 6)
    hatch = pygame.Rect(610, 290, 96, 70)
    pygame.draw.rect(surface, FRAME_DARK, hatch.inflate(10, 10))
    pygame.draw.rect(surface, FRAME, hatch)
    pygame.draw.line(surface, FRAME_DARK, hatch.midleft, hatch.midright, 3)
    pygame.draw.line(surface, FRAME_DARK, hatch.midtop, hatch.midbottom, 3)
    hazard(surface, pygame.Rect(hatch.left - 8, hatch.bottom + 8, hatch.width + 16, 8))
    # The top of this image is the front edge of the roof, so the lettering is turned to read from the door side.
    stencil(surface, 'OP-03', (300, 440), 28, (200, 202, 204), rotation=180)
    for centre in ((36, 36), (924, 36), (36, 444), (924, 444)):
        light.append(lamp(centre, (255, 70, 60), 5))
    light.append(lamp((dish[0] + 58, dish[1] - 34), (255, 70, 60), 4))
    return surface, light


def paint_flag(emblem: pygame.Surface, rng: np.random.Generator) -> pygame.Surface:
    """The flag: red cloth edged in gold, the emblem in the middle. A stiff flag, so no folds, only the weave."""
    w, h = FLAG[2], FLAG[3]
    cloth = pygame.Surface((w, h))
    cloth.fill(CLOTH_RED)
    size = h - 24
    cloth.blit(pygame.transform.smoothscale(emblem, (size, size)), ((w - size) // 2, 12))
    pygame.draw.rect(cloth, GOLD, cloth.get_rect(), 6)
    pygame.draw.rect(cloth, shade(GOLD, 0.7), cloth.get_rect().inflate(-12, -12), 1)
    array = to_array(cloth)
    weave = noise(rng, w, h, w // 2, h // 2)
    array *= (0.94 + 0.12 * weave)[..., None]
    array *= (1.03 - 0.10 * np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :])[..., None]
    return to_surface(array)


def paint_metal(rng: np.random.Generator) -> pygame.Surface:
    patch = pygame.Surface((METAL[2], METAL[3]))
    patch.fill((150, 156, 164))
    array = to_array(patch)
    array *= (0.92 + 0.16 * noise(rng, METAL[2], METAL[3], 8, 8))[..., None]
    return to_surface(array)


# ---------------------------------------------------------------------------------------------------------------

def finish(painted: Tuple[pygame.Surface, List[Emissive]], rng: np.random.Generator, strength: float = 1.0) -> pygame.Surface:
    surface, light = painted
    surface = weather(surface, rng, strength)
    for paint in light:
        paint(surface)
    return surface


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    rng = np.random.default_rng(2027)
    emblem = pygame.image.load(EMBLEM).convert_alpha()

    atlas = pygame.Surface((ATLAS_W, ATLAS_H))
    atlas.fill((26, 28, 32))
    faces = (
        (FRONT, finish(paint_front(rng), rng)),
        (BACK, finish(paint_back(rng), rng)),
        (ROOF, finish(paint_roof(rng), rng, 0.8)),
        (LEFT, finish(paint_side(rng, '1A', 70, 230), rng)),
        (RIGHT, finish(paint_side(rng, '1B', 348, 100), rng)),
        (FLAG, paint_flag(emblem, rng)),
        (METAL, paint_metal(rng)),
    )
    for region, face in faces:
        atlas.blit(face, region[:2])
    pygame.image.save(atlas, OUTPUT)
    print(f'Wrote {OUTPUT} ({ATLAS_W} x {ATLAS_H})')


if __name__ == '__main__':
    main()
