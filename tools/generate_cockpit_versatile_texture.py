"""The cockpit texture of the Versatile (ThsVersatile): one red, brighter than the THS miner's, in irregular plates with
polished separations. There are no welds and no bolts: each joint is a narrow dark groove, and each plate's edge is a
bevel that catches the light of the cabin lamps.

Writes common/resources/textures/cockpit_ths_versatile.png (1920 x 1080). Run with PYTHONPYCACHEPREFIX set to the
scratchpad.
"""

from __future__ import annotations
import math
import os
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUTPUT = os.path.join(ROOT, 'common', 'resources', 'textures', 'cockpit_ths_versatile.png')
OUT = os.path.join(ROOT, 'temp', 'cockpit_versatile')  # generated, not in git: the preview

SIZE = (1920, 1080)
U = SIZE[0] / 1280  # the pixel sizes of the shabby miner's texture, scaled to this resolution
PAINT = (178, 98, 90)  # brighter and redder than the THS miner's enamel
GROOVE = (58, 40, 40)  # the dark line of each joint
GROOVE_HALF = int(2 * U)  # half the width of a joint
BEVEL_WIDTH = int(12 * U)  # how far a plate's bevel reaches in from its edge
BEVEL_LIGHT = 1.22  # the top and left edges of a plate catch the light
BEVEL_SHADE = 0.78  # the bottom and right edges fall into shade
LAMP = (960, 180, 1200)  # a lamp above the cockpit, in pixels (as in the glossy enamel)
SHININESS = 120
INTENSITY = 0.3  # the sheen's brightness at its peak: dim
LIGHT_TINT = np.array((1.0, 0.95, 0.88), np.float32)
SCRATCHES = 8

Rect = Tuple[int, int, int, int]


def plate_rects(rng: np.random.Generator, w: int, h: int) -> List[Rect]:
    """Irregular plates: each column has its own number of plates, cut at jittered heights, so the joints do not line up.
    The jitter stays under half a cell, so the cuts keep their order and no plate is empty."""
    columns = int(rng.integers(6, 9))
    cell_w = w / columns
    xs = [0] + sorted(round(i * cell_w + rng.uniform(-0.3, 0.3) * cell_w) for i in range(1, columns)) + [w]
    rects: List[Rect] = []
    for x0, x1 in zip(xs, xs[1:]):
        rows = int(rng.integers(2, 5))
        cell_h = h / rows
        ys = [0] + sorted(round(j * cell_h + rng.uniform(-0.3, 0.3) * cell_h) for j in range(1, rows)) + [h]
        rects += [(x0, y0, x1, y1) for y0, y1 in zip(ys, ys[1:])]
    return rects


def plate_surface(rect: Rect) -> Tuple[np.ndarray, np.ndarray]:
    """For the flat part of a plate (inside its groove): the height, rising from the groove to the plate's middle,
    and the bevel's light, lit on the top and left, shaded on the bottom and right."""
    x0, y0, x1, y1 = rect
    xs = np.arange(x0 + GROOVE_HALF, x1 - GROOVE_HALF, dtype=np.float32)[None, :]
    ys = np.arange(y0 + GROOVE_HALF, y1 - GROOVE_HALF, dtype=np.float32)[:, None]
    top_left = np.minimum(xs - x0 - GROOVE_HALF, ys - y0 - GROOVE_HALF)
    bottom_right = np.minimum(x1 - GROOVE_HALF - 1 - xs, y1 - GROOVE_HALF - 1 - ys)
    ramp = np.clip(np.minimum(top_left, bottom_right) / BEVEL_WIDTH, 0, 1)
    height = ramp * ramp * (3 - 2 * ramp)  # smooth from the groove up to the flat plate
    side = np.where(top_left <= bottom_right, BEVEL_LIGHT - 1, BEVEL_SHADE - 1)  # the bevel's side, lit or shaded
    light = 1 + side * (1 - height)  # only in the bevel: the flat middle keeps the paint's colour
    return height, light.astype(np.float32)


def make_texture() -> Image.Image:
    w, h = SIZE
    rects = plate_rects(np.random.default_rng(4100), w, h)

    paint = np.broadcast_to(np.array(GROOVE, np.float32), (h, w, 3)).copy()  # the grooves, where no plate is drawn
    height = np.zeros((h, w), np.float32)
    for rect in rects:
        x0, y0, x1, y1 = rect
        inner_x0, inner_y0 = x0 + GROOVE_HALF, y0 + GROOVE_HALF
        plate_height, plate_light = plate_surface(rect)
        region = (slice(inner_y0, y1 - GROOVE_HALF), slice(inner_x0, x1 - GROOVE_HALF))
        paint[region] = np.array(PAINT, np.float32) * (0.9 + 0.1 * plate_height)[..., None] * plate_light[..., None]
        height[region] = plate_height

    marks = Image.new('L', (w, h), 0)
    draw_marks = ImageDraw.Draw(marks)
    rng = np.random.default_rng(4101)
    for _ in range(SCRATCHES):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        angle = rng.uniform(0, math.pi)
        length = rng.uniform(15, 90) * U
        draw_marks.line([(x, y), (x + length * math.cos(angle), y + length * math.sin(angle))], fill=255, width=1)
    marks = np.asarray(marks.filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32)[..., None] / 255
    paint = paint * (1 - 0.25 * marks) + np.array((170, 166, 166), np.float32) * 0.25 * marks

    slope_y, slope_x = np.gradient(height)
    k = 6.0
    nx, ny, nz = -slope_x * k, -slope_y * k, np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length

    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    lx, ly, lz = LAMP
    vx, vy, vz = lx - xs, ly - ys, np.full_like(xs, lz)
    ln = np.sqrt(vx * vx + vy * vy + vz * vz)
    hx, hy, hz = vx / ln, vy / ln, vz / ln + 1.0  # the half vector between the lamp and the eye (0, 0, 1)
    hn = np.sqrt(hx * hx + hy * hy + hz * hz)
    ndoth = np.clip((nx * hx + ny * hy + nz * hz) / hn, 0, 1)
    sheen = np.clip(ndoth ** SHININESS, 0, 1)
    out = paint + (sheen * INTENSITY * 255)[..., None] * LIGHT_TINT

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGB').convert('RGBA')


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    texture = make_texture()
    texture.save(OUTPUT)
    texture.convert('RGB').crop((0, 0, 960, 540)).save(os.path.join(OUT, 'preview_crop.png'))
    print(f'Wrote {OUTPUT}')


if __name__ == '__main__':
    main()
