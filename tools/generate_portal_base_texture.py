"""Generate the textures of the portal base: common/resources/textures/portal_base_*.png.

Run from the project root:  python tools/generate_portal_base_texture.py

Five files, all at 32 pixels per metre (graphics/portal_base_shape.py maps them in metres, so a bigger base shows more
of the same plating, not bigger plating):
    portal_base_hull.png            1024 x 1024, a tile of 32 m that repeats: dark armour plating
    portal_base_hull_glow.png       the same tile, black except what shines (windows, gun port slits, lamps)
    portal_base_interior.png        512 x 512, a tile of 16 m that repeats: the walls of the docking place
    portal_base_interior_glow.png   the same tile, only the lamps
    portal_base_marks.png           1024 x 512, with transparency: the sector numbers, the hazard stripes, the guide
                                    chevron (rectangles below, they must match graphics/portal_base_shape.py)

The hull is armour for a station that guards a portal: gunmetal plates, riveted, with hazard stripes, a red line, gun
ports that glow red, sealed hatches and rows of lit windows. The glow is a separate texture because the light on the
station is the star's alone (a face turned away from it is dark), and the windows must shine all the same. Both tiles
are made on a torus (the noise wraps) so that they have no seams.
"""

from __future__ import annotations
import os

import numpy as np
import pygame

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TEXTURES = os.path.join(ROOT, 'common', 'resources', 'textures')
FONT = os.path.join(ROOT, 'common', 'resources', 'fonts', 'Orbitron.ttf')
EMBLEM = os.path.join(ROOT, 'common', 'resources', 'textures', 'PoliticalEntity.1.png')

HULL_SIZE = 1024
INTERIOR_SIZE = 512
# The hangar's atlas (2048 x 1024, 20 pixels per metre of its faces) and the spoke's tile (256 pixels, 8 m): the
# rectangles must match graphics/portal_base_shape.py.
HANGAR_SIZE = (2048, 1024)
LEFT_SIDE = (0, 0, 880, 200)
RIGHT_SIDE = (0, 208, 880, 200)
TOP = (896, 0, 240, 880)
BOTTOM = (1152, 0, 240, 880)
CHAMFER = (1408, 0, 32, 880)  # a cut corner: across it is the 1.4 m between the two faces it joins
SPOKE_SIZE = 256
FREE_LIGHTS_FROM = 480  # on the sides, the first column of lights: the flag and the stencil are left of it
EMBLEM_SIZE = (96, 90)  # the emblem on the flag, in pixels
MARKS_SIZE = (1024, 512)

# Rectangles (x, y, w, h) of portal_base_marks.png; they must match graphics/portal_base_shape.py.
NUMBERS = [(0, 0, 256, 256), (256, 0, 256, 256), (512, 0, 256, 256), (768, 0, 256, 256)]
STRIPES = (0, 272, 768, 64)
CHEVRON = (784, 272, 224, 224)

Colour = tuple[int, int, int]

STEEL: Colour = (120, 48, 50)  # reddish gunmetal: the colour of Those-Who-Share
BEAM: Colour = (56, 32, 34)
RED: Colour = (160, 20, 24)
HAZARD_YELLOW: Colour = (226, 180, 36)
HAZARD_BLACK: Colour = (24, 24, 26)
GLASS: Colour = (16, 22, 32)
WINDOW_WARM: Colour = (255, 214, 140)
WINDOW_COOL: Colour = (176, 220, 255)
GUN_PORT_RED: Colour = (255, 48, 36)
INTERIOR_PANEL: Colour = (92, 80, 84)
LAMP: Colour = (205, 208, 204)


# region Helpers
def periodic_noise(rng: np.random.Generator, size: int, cells: int) -> np.ndarray:
    """Smooth random values 0..1 as a (size, size) array that repeats at its edges."""
    grid = rng.random((cells, cells)).astype(np.float32)
    position = np.arange(size) * cells / size
    low = np.floor(position).astype(int) % cells
    high = (low + 1) % cells
    fraction = position - np.floor(position)
    fraction = fraction * fraction * (3.0 - 2.0 * fraction)
    rows = grid[low, :] * (1.0 - fraction)[:, None] + grid[high, :] * fraction[:, None]
    return rows[:, low] * (1.0 - fraction)[None, :] + rows[:, high] * fraction[None, :]


def fbm(rng: np.random.Generator, size: int, cells: int, octaves: int) -> np.ndarray:
    """Several periodic noises, each twice as fine and half as strong as the one before, normalised to 0..1."""
    total = np.zeros((size, size), np.float32)
    strength, norm = 1.0, 0.0
    for octave in range(octaves):
        total += strength * periodic_noise(rng, size, cells * 2 ** octave)
        norm += strength
        strength *= 0.5
    return total / norm


def to_surface(rgb: np.ndarray) -> pygame.Surface:
    return pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).swapaxes(0, 1))


def to_array(surface: pygame.Surface) -> np.ndarray:
    return pygame.surfarray.array3d(surface).swapaxes(0, 1).astype(np.float32)


def with_halo(glow: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """The glow with a soft halo round what shines, from two blurs of it at different sizes."""
    height, width = glow.shape[:2]
    surface = to_surface(glow)
    halo = np.zeros_like(glow)
    for divisor, gain in ((8, 4.0), (32, 12.0)):
        small = pygame.transform.smoothscale(surface, (width // divisor, height // divisor))
        halo += to_array(pygame.transform.smoothscale(small, (width, height))) * gain
    return np.clip(glow + 0.5 * strength * halo, 0, 255)


def panels(colour: np.ndarray, rng: np.random.Generator, width: int, height: int, groove: float) -> None:
    """Panels of width x height pixels: each a little lighter or darker, with a dark groove and a light edge."""
    size = colour.shape[0]
    y, x = np.mgrid[0:size, 0:size]
    tone = rng.normal(1.0, 0.045, (size // height, size // width)).astype(np.float32)
    colour *= tone[y // height, x // width][..., None]
    px, py = x % width, y % height
    is_groove = (px < 2) | (py < 2)
    is_edge = ((px == 2) | (py == 2)) & ~is_groove
    colour[is_groove] *= groove
    colour[is_edge] *= 1.15
    for corner_x, corner_y in ((7, 7), (width - 7, 7), (7, height - 7), (width - 7, height - 7)):
        distance = np.hypot(px - corner_x, py - corner_y)
        colour[distance < 2.6] *= 1.4
        colour[(distance >= 2.6) & (distance < 3.6)] *= 0.7
# endregion


# region Hull
def make_hull(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """The armour tile and its glow."""
    size = HULL_SIZE
    y, x = np.mgrid[0:size, 0:size]
    colour = np.empty((size, size, 3), np.float32)
    colour[:] = STEEL
    panels(colour, rng, 128, 64, 0.5)

    beam = ((x % 512) < 10) | ((y % 512) < 10)  # a frame of heavier beams every 16 m
    colour[beam] = BEAM
    colour[beam & (((x % 512) == 10) | ((y % 512) == 10))] *= 1.6
    colour[84:148] *= 0.78  # the recess of the windows

    stripe = ((x + y) // 16) % 2 == 0  # diagonal hazard stripes, 1 m high, a red line over and under them
    band = (y >= 224) & (y < 256)
    colour[band & stripe] = HAZARD_YELLOW
    colour[band & ~stripe] = HAZARD_BLACK
    colour[((y >= 216) & (y < 221)) | ((y >= 259) & (y < 264))] = RED

    surface = to_surface(colour)
    glow = pygame.Surface((size, size))
    gun_ports(surface, glow)
    silo_cover(surface, 512, 624)
    hatches(surface, glow)
    lamps_row(surface, glow, 480, 128)
    lamps_row(surface, glow, 728, 64)

    font = pygame.font.Font(FONT, 26)
    for left in (40, 552):
        surface.blit(font.render('KEEP CLEAR', True, (170, 172, 178)), (left, 276))

    diffuse = to_array(surface)
    wear = fbm(rng, size, 6, 5)
    diffuse *= (0.80 + 0.32 * wear)[..., None]
    diffuse *= (1.0 + rng.normal(0.0, 0.015, (size, size)))[..., None].astype(np.float32)
    pits = rng.integers(0, size, (1600, 2))
    diffuse[pits[:, 0], pits[:, 1]] *= 0.5
    diffuse[(pits[:, 0] + 1) % size, pits[:, 1]] *= 1.25
    return np.clip(diffuse, 0, 255), with_halo(to_array(glow))


def make_side(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """The side walls of the ring, where people stand: the band of the wall is the top 10 m of the tile (the rest is not
    used), with two large windows in each 32 m, 3 m wide and 6 m high, and their lit panes in the glow."""
    size = HULL_SIZE
    colour = np.empty((size, size, 3), np.float32)
    colour[:] = STEEL
    panels(colour, rng, 128, 64, 0.5)
    surface = to_surface(colour)
    glow = pygame.Surface((size, size))
    glow.fill((0, 0, 0))
    for left in (128, 640):
        pygame.draw.rect(surface, (30, 20, 22), (left - 6, 58, 108, 204))  # the frame
        pygame.draw.rect(surface, GLASS, (left, 64, 96, 192))
        pygame.draw.rect(surface, (30, 20, 22), (left + 46, 64, 4, 192))  # a mullion, down the middle
        pane = WINDOW_WARM if rng.random() < 0.6 else WINDOW_COOL
        pygame.draw.rect(glow, pane, (left + 4, 68, 40, 184))
        pygame.draw.rect(glow, pane, (left + 52, 68, 40, 184))
        pygame.draw.rect(surface, (120, 124, 132), (left - 8, 256, 112, 6))  # the sill
    diffuse = np.clip(weather(to_array(surface), rng), 0, 255)
    return diffuse, with_halo(to_array(glow), 0.3)


def gun_ports(surface: pygame.Surface, glow: pygame.Surface) -> None:
    """Dark slots with a red light at one end."""
    for left in (128, 384, 640, 896):
        pygame.draw.rect(surface, (34, 36, 42), (left - 4, 388, 120, 36))
        pygame.draw.rect(surface, (6, 6, 8), (left, 392, 112, 28))
        pygame.draw.circle(glow, GUN_PORT_RED, (left + 10, 406), 5)
        pygame.draw.rect(glow, (120, 20, 16), (left + 22, 404, 40, 4))


def silo_cover(surface: pygame.Surface, centre_x: int, centre_y: int, size: int = 160) -> None:
    """The closed cover of a missile silo: a yellow plate, its round recess and the rim of the recess, as the cover of
    a silo in the desert."""
    left, top = centre_x - size // 2, centre_y - size // 2
    pygame.draw.rect(surface, (206, 166, 42), (left, top, size, size))
    pygame.draw.rect(surface, (150, 116, 28), (left, top, size, size), 3)
    pygame.draw.circle(surface, (224, 184, 60), (centre_x, centre_y), size // 3)
    pygame.draw.circle(surface, (176, 136, 34), (centre_x, centre_y), size // 3, 4)
    for corner_x, corner_y in ((left + 10, top + 10), (left + size - 10, top + 10),
                               (left + 10, top + size - 10), (left + size - 10, top + size - 10)):
        pygame.draw.circle(surface, (120, 92, 28), (corner_x, corner_y), 3)


def hatches(surface: pygame.Surface, glow: pygame.Surface) -> None:
    """Sealed square hatches on the hub: a frame, four bolts, a seam round the lid and a red lamp. Not vents."""
    for centre_x in (256, 768):
        left, top = centre_x - 60, 624 - 60
        pygame.draw.rect(surface, (50, 48, 54), (left, top, 120, 120))
        pygame.draw.rect(surface, (22, 20, 24), (left, top, 120, 120), 3)
        pygame.draw.rect(surface, (96, 100, 108), (left + 8, top + 8, 104, 104), 2)
        for corner_x, corner_y in ((left + 14, top + 14), (left + 106, top + 14),
                                   (left + 14, top + 106), (left + 106, top + 106)):
            pygame.draw.circle(surface, (150, 154, 160), (corner_x, corner_y), 4)
        pygame.draw.circle(glow, GUN_PORT_RED, (centre_x, top + 22), 4)


def lamps_row(surface: pygame.Surface, glow: pygame.Surface, top: int, step: int) -> None:
    """A row of small red warning lamps."""
    for left in range(step // 2, HULL_SIZE, step):
        pygame.draw.circle(surface, (60, 14, 14), (left, top), 6)
        pygame.draw.circle(glow, (255, 60, 40), (left, top), 3)
# endregion


# region Interior
def make_interior(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """The walls of the docking place: dark panels, a hazard rail along the floor, and two small lamps on the ceiling
    of each tile (few lights, so the walls stay readable)."""
    size = INTERIOR_SIZE
    colour = np.empty((size, size, 3), np.float32)
    colour[:] = INTERIOR_PANEL
    panels(colour, rng, 64, 64, 0.62)
    y, x = np.mgrid[0:size, 0:size]
    rail = (y >= 488) & (y < 504)
    stripe = ((x + y) // 16) % 2 == 0
    colour[rail & stripe] = HAZARD_YELLOW
    colour[rail & ~stripe] = HAZARD_BLACK

    surface = to_surface(colour)
    glow = pygame.Surface((size, size))
    for left in (96, 352):
        pygame.draw.rect(glow, (150, 150, 146), (left, 28, 64, 8))
    diffuse = to_array(surface)
    diffuse *= (0.9 + 0.2 * fbm(rng, size, 4, 4))[..., None]
    return np.clip(diffuse, 0, 255), with_halo(to_array(glow), 0.05)
# endregion


# region Marks
def make_marks() -> pygame.Surface:
    """The sector numbers, the hazard stripes and the guide chevron, on a transparent sheet."""
    sheet = pygame.Surface(MARKS_SIZE, pygame.SRCALPHA)
    font = pygame.font.Font(FONT, 170)
    for number, (left, top, width, height) in enumerate(NUMBERS, start=1):
        pygame.draw.rect(sheet, (150, 24, 28), (left + 8, top + 8, width - 16, height - 16), border_radius=24)
        pygame.draw.rect(sheet, (232, 232, 232), (left + 8, top + 8, width - 16, height - 16), 8, border_radius=24)
        text = font.render(str(number), True, (240, 240, 240))
        sheet.blit(text, text.get_rect(center=(left + width // 2, top + height // 2)))

    left, top, width, height = STRIPES
    for x in range(width):
        for y in range(height):
            sheet.set_at((left + x, top + y), HAZARD_YELLOW if ((x + y) // 16) % 2 == 0 else HAZARD_BLACK)

    left, top, width, height = CHEVRON
    points = [(left + width // 2, top + 8), (left + width - 8, top + height * 0.55),
              (left + width - 8, top + height - 8), (left + width // 2, top + height * 0.5),
              (left + 8, top + height - 8), (left + 8, top + height * 0.55)]
    pygame.draw.polygon(sheet, HAZARD_YELLOW, points)
    pygame.draw.polygon(sheet, HAZARD_BLACK, points, 6)
    return sheet
# endregion

def weather(diffuse: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """The wear of the metal: dust and pits, as on the hull."""
    height, width = diffuse.shape[:2]
    wear = fbm(rng, max(height, width), 6, 5)[:height, :width]
    diffuse *= (0.80 + 0.32 * wear)[..., None]
    pits = rng.integers(0, [height, width], (1600, 2))
    diffuse[pits[:, 0], pits[:, 1]] *= 0.5
    return diffuse


def hazard_band(surface: pygame.Surface, top: int, bottom: int, left: int, right: int) -> None:
    """A band of diagonal hazard stripes between two rows, with a red line above it."""
    band = bottom - top
    for x in range(left - band, right, 16):
        stripe = [(x, bottom), (x + 8, bottom), (x + 8 + band, top), (x + band, top)]
        pygame.draw.polygon(surface, HAZARD_YELLOW, stripe)
    for x in range(left - band + 8, right, 16):
        stripe = [(x, bottom), (x + 8, bottom), (x + 8 + band, top), (x + band, top)]
        pygame.draw.polygon(surface, HAZARD_BLACK, stripe)
    pygame.draw.rect(surface, RED, (left, top - 4, right - left, 4))


def paint_face(surface: pygame.Surface, glow: pygame.Surface, region: tuple[int, int, int, int], side: bool) -> None:
    """Plating of a hangar face: seams every 2 m and rivets. A side has a conduit, a warning and a row of lasers (dark
    lenses with a red point); a top or a bottom has the closed hatches of the missile launch pads, with red lamps."""
    x0, y0, width, height = region
    face = surface.subsurface(pygame.Rect(region))
    rivet = (150, 110, 112)
    for step in range(0, width, 40):
        pygame.draw.line(face, BEAM, (step, 0), (step, height), 2)
    for step in range(0, height, 40):
        pygame.draw.line(face, BEAM, (0, step), (width, step), 2)
    for column in range(0, width, 40):
        for row in range(0, height, 40):
            face.set_at((column + 4, row + 4), rivet)
            face.set_at((column + 5, row + 4), rivet)
    if side:
        hazard_band(face, height - 16, height - 4, 0, width)
        pygame.draw.line(face, (34, 20, 22), (0, 30), (width, 30), 6)
        for column in range(40, 240, 96):  # the clamps of the conduit, left of the flag's zone
            pygame.draw.rect(face, (70, 40, 42), (column - 4, 24, 8, 18))
        font = pygame.font.Font(FONT, 20)
        face.blit(font.render('KEEP CLEAR', True, (176, 170, 172)), (260, 56))
        for row in (62, 138):  # two lasers in each row, clear of the flag, the stencil and the doors
            for column in (480, 552):
                pygame.draw.circle(face, (10, 8, 12), (column, row), 9)
                pygame.draw.circle(face, (126, 36, 36), (column, row), 9, 2)
                pygame.draw.circle(glow, (255, 70, 50), (x0 + column, y0 + row), 3)
                pygame.draw.circle(glow, (120, 24, 20), (x0 + column, y0 + row), 7, 1)
        for column in range(FREE_LIGHTS_FROM, 620, 24):
            pygame.draw.circle(glow, (255, 60, 40), (x0 + column, y0 + 12), 2)
        paint_blast_door(face, glow, x0, y0, 620, 16, 160, 180)
        paint_personnel_door(face, glow, x0, y0, 800, 60, 60, 136)
    else:
        hazard_band(face, 4, 18, 0, width)
        for along in range(40, height - 60, 140):
            for across in (20, 92, 164):
                if across == 92:  # the middle column: silo covers, not hatches
                    silo_cover(face, across + 28, along + 30, 56)
                    continue
                pygame.draw.rect(face, (40, 36, 40), (across, along, 56, 60))
                pygame.draw.rect(face, (18, 14, 18), (across, along, 56, 60), 2)
                pygame.draw.line(face, (62, 54, 60), (across + 2, along + 2), (across + 54, along + 58), 2)
                pygame.draw.line(face, (62, 54, 60), (across + 54, along + 2), (across + 2, along + 58), 2)
                for corner_x, corner_y in ((6, 6), (50, 6), (6, 54), (50, 54)):
                    pygame.draw.circle(glow, (255, 50, 36), (x0 + across + corner_x, y0 + along + corner_y), 2)
                pygame.draw.rect(glow, (120, 22, 16), (x0 + across + 22, y0 + along + 26, 12, 4))


def paint_chamfer(surface: pygame.Surface, glow: pygame.Surface, region: tuple[int, int, int, int]) -> None:
    """A cut corner of the hangar, seen from afar as an outline: dark plating with a yellow stripe along each edge
    and a row of amber running lights down the middle, a dim line joining them."""
    x0, y0, width, height = region
    face = surface.subsurface(pygame.Rect(region))
    face.fill((34, 22, 24))
    for edge in (0, width - 5):
        pygame.draw.rect(face, HAZARD_YELLOW, (edge, 0, 5, height))
    pygame.draw.line(glow, (90, 52, 14), (x0 + width // 2, y0), (x0 + width // 2, y0 + height), 2)
    for row in range(12, height, 40):
        pygame.draw.circle(glow, (255, 176, 48), (x0 + width // 2, y0 + row), 4)


def bolts(surface: pygame.Surface, left: int, top: int, width: int, height: int, step: int) -> None:
    """Bolts round a rectangle, every `step` pixels."""
    for column in range(left + step // 2, left + width, step):
        for row in (top + 5, top + height - 5):
            pygame.draw.circle(surface, (150, 154, 160), (column, row), 2)
    for row in range(top + step // 2, top + height, step):
        for column in (left + 5, left + width - 5):
            pygame.draw.circle(surface, (150, 154, 160), (column, row), 2)


def paint_blast_door(face: pygame.Surface, glow: pygame.Surface, x0: int, y0: int, left: int, top: int,
                     width: int, height: int) -> None:
    """A heavy sliding blast door: two leaves with a seam, a frame, bolts, hinge plates and a handle."""
    pygame.draw.rect(face, (34, 22, 24), (left - 6, top - 6, width + 12, height + 12))
    pygame.draw.rect(face, (70, 48, 50), (left, top, width, height))
    middle = left + width // 2
    pygame.draw.line(face, (22, 14, 16), (middle, top), (middle, top + height), 4)
    for hinge in (top + 24, top + height - 40):
        pygame.draw.rect(face, (92, 64, 66), (left - 6, hinge, 6, 16))
    pygame.draw.rect(face, (120, 90, 92), (middle + 14, top + height // 2 - 14, 8, 28))  # the handle
    bolts(face, left, top, width, height, 22)
    pygame.draw.circle(glow, (255, 60, 40), (x0 + left + 6, y0 + top + 6), 2)  # a status lamp at the corner


def paint_personnel_door(face: pygame.Surface, glow: pygame.Surface, x0: int, y0: int, left: int, top: int,
                         width: int, height: int) -> None:
    """A small door set into the big one's side: a frame, a porthole with a red ring of light, a handle and a latch."""
    pygame.draw.rect(face, (34, 22, 24), (left - 4, top - 4, width + 8, height + 8))
    pygame.draw.rect(face, (84, 58, 60), (left, top, width, height))
    pygame.draw.rect(face, (22, 14, 16), (left, top, width, height), 2)
    centre = (left + width // 2, top + 30)
    pygame.draw.circle(face, (12, 14, 18), centre, 11)
    pygame.draw.circle(face, (120, 124, 130), centre, 11, 2)
    pygame.draw.circle(glow, (150, 40, 30), (x0 + centre[0], y0 + centre[1]), 9, 2)
    pygame.draw.rect(face, (150, 154, 160), (left + width - 14, top + height // 2 - 10, 4, 22))  # the handle
    pygame.draw.rect(face, (120, 124, 130), (left + 6, top + height - 26, width - 12, 8))  # the latch plate
    bolts(face, left, top, width, height, 18)


def paint_flag(surface: pygame.Surface, region: tuple[int, int, int, int]) -> None:
    """The flag of Those-Who-Share on the side of the hangar: the emblem on a red field, with a gold border."""
    x0, y0, _, _ = region
    left, top, width, height = x0 + 60, y0 + 24, 160, 100
    pygame.draw.rect(surface, (200, 22, 26), (left, top, width, height))
    emblem = pygame.transform.smoothscale(pygame.image.load(EMBLEM), EMBLEM_SIZE)
    surface.blit(emblem, emblem.get_rect(center=(left + width // 2, top + height // 2)))
    pygame.draw.rect(surface, HAZARD_YELLOW, (left, top, width, height), 3)


def make_hangar(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """The atlas of the hangar's outer sides: plating, the flag on the right side, the launch pads on the top and the
    bottom, the lasers on the sides and the lights of the cut corners. The lamps are in the glow."""
    surface = pygame.Surface(HANGAR_SIZE)
    surface.fill(STEEL)
    glow = pygame.Surface(HANGAR_SIZE)
    glow.fill((0, 0, 0))
    paint_face(surface, glow, LEFT_SIDE, True)
    paint_face(surface, glow, RIGHT_SIDE, True)
    paint_face(surface, glow, TOP, False)
    paint_face(surface, glow, BOTTOM, False)
    paint_flag(surface, RIGHT_SIDE)
    paint_chamfer(surface, glow, CHAMFER)
    diffuse = to_array(surface)
    diffuse = np.clip(weather(diffuse, rng), 0, 255)
    return diffuse, with_halo(to_array(glow), 0.25)


def make_spoke(rng: np.random.Generator) -> np.ndarray:
    """The tile of the spokes: plain plating with a dark conduit along it, and no lights."""
    colour = np.empty((SPOKE_SIZE, SPOKE_SIZE, 3), np.float32)
    colour[:] = STEEL
    tone = rng.normal(1.0, 0.04, (SPOKE_SIZE // 32, SPOKE_SIZE // 64)).astype(np.float32)
    rows, columns = np.mgrid[0:SPOKE_SIZE, 0:SPOKE_SIZE]
    colour *= tone[rows // 32, columns // 64][..., None]
    colour[(rows % 32 < 2) | (columns % 64 < 2)] *= 0.6  # the seams
    colour[SPOKE_SIZE // 2 - 3:SPOKE_SIZE // 2 + 3] *= 0.45  # a dark conduit along it
    for top in range(16, SPOKE_SIZE, 64):  # hatches: dark plates with a lighter frame, no lights
        for left in (24, 150):
            colour[top:top + 22, left:left + 40] *= 0.55
            colour[top:top + 2, left:left + 40] *= 1.3
            colour[top:top + 22, left:left + 2] *= 1.3
    return np.clip(weather(colour, rng), 0, 255)


def save_array(rgb: np.ndarray, name: str) -> None:
    pygame.image.save(to_surface(rgb), os.path.join(TEXTURES, name))


def save_array_of_size(rgb: np.ndarray, name: str) -> None:
    """save_array for an image that is not square: its array is (height, width, 3)."""
    surface = pygame.Surface((rgb.shape[1], rgb.shape[0]))
    pygame.surfarray.blit_array(surface, np.clip(rgb, 0, 255).astype(np.uint8).swapaxes(0, 1))
    pygame.image.save(surface, os.path.join(TEXTURES, name))


def main() -> None:
    pygame.font.init()
    rng = np.random.default_rng(20271)
    hull, hull_glow = make_hull(rng)
    save_array(hull, 'portal_base_hull.png')
    save_array(hull_glow, 'portal_base_hull_glow.png')
    interior, interior_glow = make_interior(rng)
    save_array(interior, 'portal_base_interior.png')
    save_array(interior_glow, 'portal_base_interior_glow.png')
    pygame.image.save(make_marks(), os.path.join(TEXTURES, 'portal_base_marks.png'))
    hangar, hangar_glow = make_hangar(rng)
    save_array_of_size(hangar, 'portal_base_hangar.png')
    save_array_of_size(hangar_glow, 'portal_base_hangar_glow.png')
    save_array(make_spoke(rng), 'portal_base_spoke.png')
    side, side_glow = make_side(rng)
    save_array_of_size(side, 'portal_base_side.png')
    save_array_of_size(side_glow, 'portal_base_side_glow.png')
    print('Portal base textures written to', os.path.normpath(TEXTURES))


if __name__ == '__main__':
    main()
