"""Generate Resources/textures/outpost.png, the texture of the outpost building.

Run from the project root:  python Tools/generate_outpost_texture.py

Atlas layout, 40 pixels per metre on every face (the building is 12 m x 6 m x 3 m):
    front wall (door side, 12 x 3 m)   x 0..480,    y 0..120
    back wall  (12 x 3 m)              x 0..480,    y 128..248
    left side  (6 x 3 m)               x 512..752,  y 256..376
    right side (6 x 3 m)               x 768..1008, y 256..376
    roof       (12 x 6 m)              x 512..992,  y 0..240

No openings are drawn: windows are lit panels painted onto the walls, and the door is a sealed airlock.
Colours follow the mine hull (Graphics/Constants.py) so the two read as the same kind of structure.
"""

from __future__ import annotations
import os
import pygame

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT = os.path.join(ROOT, 'Resources', 'textures', 'outpost.png')
EMBLEM = os.path.join(ROOT, 'Resources', 'textures', 'PoliticalEntity.1.png')

ATLAS_W, ATLAS_H = 1024, 512
PX = 40  # pixels per metre

# Colours, copied from Graphics/Constants.py (MINE_* and ACCENT).
HULL = (60, 64, 72)
HULL_DARK = (34, 37, 44)
HULL_LIGHT = (96, 101, 112)
ACCENT = (94, 234, 212)
WARNING_A = (240, 196, 40)
WARNING_B = (26, 26, 26)
WINDOW_LIT = (255, 214, 140)
WINDOW_GLOW = (255, 240, 200)
EMBLEM_PLATE = (22, 24, 30)

# Region rectangles (x, y, w, h) in atlas pixels.
FRONT = (0, 0, 480, 120)
BACK = (0, 128, 480, 120)
LEFT = (512, 256, 240, 120)
RIGHT = (768, 256, 240, 120)
ROOF = (512, 0, 480, 240)
DOOR_W, DOOR_H = 88, 96  # 2.2 m x 2.4 m airlock, bottom-aligned on the front wall


def paint_wall(surface: pygame.Surface, rect: tuple, windows: list) -> None:
    """Hull panels with seams, rivets, a hazard band at the base, and lit windows (painted, not holes)."""
    x0, y0, w, h = rect
    previous_clip = surface.get_clip()
    surface.set_clip(rect)  # nothing may spill into a neighbouring region
    surface.fill(HULL, rect)
    # Vertical panel seams every 2 m.
    for x in range(0, w, 2 * PX):
        pygame.draw.line(surface, HULL_DARK, (x0 + x, y0), (x0 + x, y0 + h - 1), 2)
    # Horizontal seam under the roof line.
    pygame.draw.line(surface, HULL_DARK, (x0, y0 + 10), (x0 + w - 1, y0 + 10), 2)
    # Rivets along the seams.
    for x in range(0, w, 2 * PX):
        for y in (20, h - 30):
            pygame.draw.circle(surface, HULL_LIGHT, (x0 + x + 6, y0 + y), 2)
    # Hazard band at the base.
    band_h = 12
    for x in range(-band_h, w + band_h, band_h * 2):
        pygame.draw.polygon(surface, WARNING_A, [
            (x0 + x, y0 + h - band_h), (x0 + x + band_h, y0 + h - band_h),
            (x0 + x + band_h - band_h, y0 + h), (x0 + x - band_h, y0 + h),
        ])
    # Windows: a frame, a glowing panel and a light strip. Drawn on the wall, never as openings.
    for wx, wy, ww, wh in windows:
        frame = pygame.Rect(x0 + wx - 3, y0 + wy - 3, ww + 6, wh + 6)
        pygame.draw.rect(surface, HULL_DARK, frame)
        pane = pygame.Rect(x0 + wx, y0 + wy, ww, wh)
        pygame.draw.rect(surface, WINDOW_LIT, pane)
        pygame.draw.rect(surface, WINDOW_GLOW, pane.inflate(-ww // 3, -wh // 3))
        pygame.draw.line(surface, WINDOW_GLOW, (pane.left + 2, pane.top + 2), (pane.right - 3, pane.top + 2), 2)
    surface.set_clip(previous_clip)


def paint_door(surface: pygame.Surface, x: int, y: int) -> None:
    """A sealed airlock: a frame, a closed leaf with a seam, and a small indicator light."""
    frame = pygame.Rect(x - 4, y - 4, DOOR_W + 8, DOOR_H + 4)
    pygame.draw.rect(surface, HULL_DARK, frame)
    leaf = pygame.Rect(x, y, DOOR_W, DOOR_H)
    pygame.draw.rect(surface, HULL_LIGHT, leaf)
    pygame.draw.line(surface, HULL_DARK, (leaf.centerx, leaf.top), (leaf.centerx, leaf.bottom - 1), 2)
    pygame.draw.circle(surface, ACCENT, (leaf.centerx, leaf.top + 14), 4)


def paint_emblem(surface: pygame.Surface, x: int, y: int, size: int) -> None:
    """The political entity's emblem on a dark plate with a stripe in its colour, beside the door."""
    plate = pygame.Rect(x, y, size + 12, size + 12)
    pygame.draw.rect(surface, EMBLEM_PLATE, plate)
    pygame.draw.rect(surface, ACCENT, plate, 2)
    if os.path.exists(EMBLEM):
        icon = pygame.image.load(EMBLEM)
        icon = pygame.transform.smoothscale(icon, (size, size))
        surface.blit(icon, (x + 6, y + 6))
    else:
        pygame.draw.rect(surface, HULL_LIGHT, (x + 6, y + 6, size, size))


def paint_roof(surface: pygame.Surface) -> None:
    """Flat roof: panel lines, a grid of solar cells, and status lights. No hatch, no openings."""
    x0, y0, w, h = ROOF
    previous_clip = surface.get_clip()
    surface.set_clip(ROOF)
    surface.fill(HULL, ROOF)
    for x in range(0, w, 3 * PX):
        pygame.draw.line(surface, HULL_DARK, (x0 + x, y0), (x0 + x, y0 + h - 1), 2)
    for y in range(0, h, 3 * PX):
        pygame.draw.line(surface, HULL_DARK, (x0, y0 + y), (x0 + w - 1, y0 + y), 2)
    # Solar cells: dark blue-grey rectangles with a thin light edge, in the panel grid.
    cell_colour = (30, 44, 60)
    for cx in range(20, w - 40, 60):
        for cy in range(20, h - 40, 52):
            cell = pygame.Rect(x0 + cx, y0 + cy, 40, 30)
            pygame.draw.rect(surface, cell_colour, cell)
            pygame.draw.rect(surface, HULL_LIGHT, cell, 1)
    # Status lights along one edge.
    for lx in range(40, w - 40, 120):
        pygame.draw.circle(surface, ACCENT, (x0 + lx, y0 + h - 16), 4)
    surface.set_clip(previous_clip)


def main() -> None:
    pygame.init()
    atlas = pygame.Surface((ATLAS_W, ATLAS_H), pygame.SRCALPHA)
    atlas.fill((0, 0, 0, 0))

    # Front wall: the door side. Windows left and right of the door, emblem between door and right windows.
    paint_wall(atlas, FRONT, windows=[
        (24, 24, 72, 40), (120, 24, 72, 40),
        (378, 24, 36, 40), (426, 24, 36, 40),
    ])
    door_x = FRONT[0] + (FRONT[2] - DOOR_W) // 2
    door_y = FRONT[1] + FRONT[3] - DOOR_H
    paint_door(atlas, door_x, door_y)
    paint_emblem(atlas, door_x + DOOR_W + 8, FRONT[1] + 16, 60)  # just right of the door, clear of the windows

    # Back wall: windows only.
    paint_wall(atlas, BACK, windows=[
        (40, 24, 80, 40), (160, 24, 80, 40), (300, 24, 80, 40), (400, 24, 40, 40),
    ])

    # Side walls: one lit window each.
    paint_wall(atlas, LEFT, windows=[(60, 24, 80, 40), (160, 24, 60, 40)])
    paint_wall(atlas, RIGHT, windows=[(40, 24, 80, 40), (140, 24, 60, 40)])

    paint_roof(atlas)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    pygame.image.save(atlas, OUTPUT)
    print(f"wrote {OUTPUT} ({ATLAS_W}x{ATLAS_H})")


if __name__ == '__main__':
    main()
