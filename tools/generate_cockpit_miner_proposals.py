"""Proposals for the cockpit background of the normal miner: four looks of welded plates, brighter than the shabby
miner's, without peeling, with a dim sheen from the invisible lamps inside the cabin.

The sheen is specular light: the plates and seams form a height map, its slopes give the normals, and each lamp
(a point above the cockpit, in pixels) lights the surface where the normal bisects the lamp and the eye.

Writes into temp/cockpit_miner_proposals/: cockpit_miner_<n>.png (1920 x 1080, the window size) and mockup_<n>.png, and sheet.png.
Nothing in the game is changed. Run with PYTHONPYCACHEPREFIX set to the scratchpad.
"""

from __future__ import annotations
import math
import os
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'temp', 'cockpit_miner_proposals')  # generated, not in git
FONT = os.path.join(ROOT, 'common', 'resources', 'fonts', 'Oxanium.ttf')

SIZE = (1920, 1080)
U = SIZE[0] / 1280  # the pixel sizes of the shabby miner's texture, scaled to this resolution
HEAT = (126, 84, 58)
WELD = (84, 78, 76)
BOLT = (150, 146, 146)
SHADOW = (30, 27, 27)
SCRATCH = (170, 166, 166)
READOUT_BG = (9, 17, 21)
ACCENT = (94, 234, 212)
ACCENT_DIM = (34, 92, 92)
CANOPY_TOP = 0.055
CONSOLE_TOP = 0.66
# The bezel is the shabby miner's, for now.
BEZEL_CONSOLE = (44, 40, 38)
BEZEL_EDGE = (108, 101, 94)
BEZEL_DARK = (26, 24, 24)
BEZEL_CONSOLE_EDGE = (150, 118, 70)
LIGHT_TINT = np.array((1.0, 0.95, 0.88), np.float32)  # the cabin's light is a little warm


@dataclass
class Proposal:
    number: int
    name: str
    plates: Tuple[Tuple[int, int, int], ...]  # welded plates, brighter and more vivid than the shabby miner's
    lamps: Tuple[Tuple[float, float, float], ...]  # x, y, z in pixels: z is the height above the surface
    shininess: float  # the higher, the smaller and sharper the sheen
    intensity: float  # the sheen's brightness at its peak, 0 to 1 (kept dim)
    bump: float  # how rough the paint is: the fine height noise
    brushed: bool  # the fine noise streaked along the plates, as brushed steel
    scratches: int


# The glossy enamel, with the plates' colours closer together: the spread of each set falls from proposal 1 to 4.
GLOSSY_LAMPS = ((960, 180, 1200),)
PROPOSALS = (
    Proposal(1, 'Glossy, one colour',
             plates=((158, 96, 88), (158, 96, 88), (158, 96, 88)),
             lamps=GLOSSY_LAMPS, shininess=120, intensity=0.3, bump=0.25, brushed=False, scratches=10),
    Proposal(2, 'Glossy, slight spread',
             plates=((158, 96, 88), (150, 100, 92), (164, 98, 86)),
             lamps=GLOSSY_LAMPS, shininess=120, intensity=0.3, bump=0.25, brushed=False, scratches=10),
    Proposal(3, 'Glossy, small spread',
             plates=((156, 94, 86), (152, 98, 90), (160, 96, 88)),
             lamps=GLOSSY_LAMPS, shininess=120, intensity=0.3, bump=0.25, brushed=False, scratches=10),
    Proposal(4, 'Glossy, faint spread',
             plates=((152, 92, 84), (156, 98, 90), (150, 94, 86)),
             lamps=GLOSSY_LAMPS, shininess=120, intensity=0.3, bump=0.25, brushed=False, scratches=10),
)


# region Noise
def value_noise(rng: np.random.Generator, h: int, w: int, cell_y: int, cell_x: int) -> np.ndarray:
    """Smooth random field in 0..1, with features cell_y by cell_x pixels."""
    grid = rng.random((max(2, h // cell_y + 2), max(2, w // cell_x + 2))).astype(np.float32)
    field = np.asarray(Image.fromarray(grid, mode='F').resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32)
    return (field - field.min()) / max(1e-6, field.max() - field.min())


def fbm(rng: np.random.Generator, h: int, w: int, cell: int, octaves: int = 4) -> np.ndarray:
    total = np.zeros((h, w), np.float32)
    amplitude, norm = 1.0, 0.0
    for _ in range(octaves):
        total += amplitude * value_noise(rng, h, w, cell, cell)
        norm += amplitude
        amplitude *= 0.5
        cell = max(2, cell // 2)
    return total / norm
# endregion


# region Plates
Rect = Tuple[int, int, int, int]


def plate_grid(rng: np.random.Generator, w: int, h: int) -> List[Rect]:
    """Four columns and three rows of plates, each line moved a little so no two joints line up."""
    xs = [0] + sorted(int(w * i / 4 + rng.uniform(-0.05, 0.05) * w) for i in (1, 2, 3)) + [w]
    ys = [0] + sorted(int(h * i / 3 + rng.uniform(-0.06, 0.06) * h) for i in (1, 2)) + [h]
    return [(x0, y0, x1, y1) for y0, y1 in zip(ys, ys[1:]) for x0, x1 in zip(xs, xs[1:])]


def joints(rects: List[Rect], w: int, h: int) -> List[Tuple[int, int, int, int]]:
    """Each joint once: the top edge of every plate below the top, and its left edge if it is not on the left."""
    lines = []
    for x0, y0, x1, y1 in rects:
        if y0 > 0:
            lines.append((x0, y0, x1, y0))
        if x0 > 0:
            lines.append((x0, y0, x0, y1))
    return lines
# endregion


# region Texture
def make_texture(p: Proposal, rects: List[Rect], seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    w, h = SIZE
    lines = joints(rects, w, h)

    plates = Image.new('RGB', (w, h))
    draw_plates = ImageDraw.Draw(plates)
    for x0, y0, x1, y1 in rects:
        draw_plates.rectangle([x0, y0, x1 - 1, y1 - 1], fill=p.plates[int(rng.integers(len(p.plates)))])
    paint = np.asarray(plates, dtype=np.float32).copy()
    paint *= (0.94 + 0.12 * fbm(rng, h, w, 96))[..., None]  # soft mottling: no grime, the ship is new
    paint *= (0.96 + 0.08 * value_noise(rng, h, w, 2, 40))[..., None] if p.brushed else 1.0

    # Height: the joints are raised ridges, the rest of each plate is flat with the fine roughness of the paint.
    seam_image = Image.new('L', (w, h), 0)
    seam_draw = ImageDraw.Draw(seam_image)
    for x0, y0, x1, y1 in lines:
        seam_draw.line([(x0, y0), (x1, y1)], fill=255, width=max(2, int(4 * U)))
    ridge = np.asarray(seam_image.filter(ImageFilter.GaussianBlur(3 * U)), dtype=np.float32) / 255
    if p.brushed:
        roughness = value_noise(rng, h, w, 1, 40)
    else:
        roughness = fbm(rng, h, w, 8)
    height = ridge * 1.0 + p.bump * 0.03 * roughness

    slope_y, slope_x = np.gradient(height)
    k = 40.0
    nx, ny, nz = -slope_x * k, -slope_y * k, np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length

    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    sheen = np.zeros((h, w), np.float32)
    for lx, ly, lz in p.lamps:
        vx, vy, vz = lx - xs, ly - ys, np.full_like(xs, lz)
        ln = np.sqrt(vx * vx + vy * vy + vz * vz)
        hx, hy, hz = vx / ln, vy / ln, vz / ln + 1.0  # the half vector between the lamp and the eye (0, 0, 1)
        hn = np.sqrt(hx * hx + hy * hy + hz * hz)
        ndoth = np.clip((nx * hx + ny * hy + nz * hz) / hn, 0, 1)
        sheen += ndoth ** p.shininess
    sheen = np.clip(sheen, 0, 1)

    shading = 0.94 + 0.06 * ridge  # the seams are a little lighter, lit from above
    out = paint * shading[..., None] + (sheen * p.intensity * 255)[..., None] * LIGHT_TINT

    marks = Image.new('L', (w, h), 0)
    draw_marks = ImageDraw.Draw(marks)
    for _ in range(p.scratches):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        angle = rng.uniform(0, math.pi)
        length_px = rng.uniform(15, 90) * U
        draw_marks.line([(x, y), (x + length_px * math.cos(angle), y + length_px * math.sin(angle))],
                        fill=255, width=1)
    marks = np.asarray(marks.filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32)[..., None] / 255
    out = out * (1 - 0.3 * marks) + np.array(SCRATCH, np.float32) * 0.3 * marks

    image = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGB')
    draw_welds(image, lines, rng)
    return image.convert('RGBA')


def draw_welds(image: Image.Image, lines: List[Tuple[int, int, int, int]], rng: np.random.Generator) -> None:
    """Weld beads with their heat, along most joints, as on the shabby miner's hull."""
    w, h = SIZE
    heat = Image.new('L', (w, h), 0)
    heat_draw = ImageDraw.Draw(heat)
    welded = [line for line in lines if rng.random() < 0.7]
    for x0, y0, x1, y1 in welded:
        heat_draw.line([(x0, y0), (x1, y1)], fill=255, width=int(14 * U))
    mask = np.asarray(heat.filter(ImageFilter.GaussianBlur(6 * U)), dtype=np.float32)[..., None] / 255
    base = np.asarray(image, dtype=np.float32)
    image.paste(Image.fromarray(np.clip(base * (1 - 0.3 * mask) + np.array(HEAT, np.float32) * 0.3 * mask,
                                        0, 255).astype(np.uint8)))
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in welded:
        horizontal = y0 == y1
        length = (x1 - x0) if horizontal else (y1 - y0)
        for along in range(int(4 * U), length - int(4 * U), int(4 * U)):
            cx, cy = (x0 + along, y0) if horizontal else (x0, y0 + along)
            r = int(rng.integers(2, 4) * U)
            draw.ellipse([cx - r + 1, cy - r + 2, cx + r + 1, cy + r + 2], fill=SHADOW)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WELD)
            draw.ellipse([cx - r, cy - r, cx, cy], fill=BOLT)
# endregion


# region Mockup
def cockpit_mockup(texture: Image.Image) -> Image.Image:
    """The texture with the canopy edge, the console bar and four instruments drawn in the bezel colours, darkened on
    the left as the game does."""
    w, h = SIZE
    base = np.asarray(texture.convert('RGB'), dtype=np.float32)
    base *= ((90 + 165 * np.arange(w) / w) / 255)[None, :, None]
    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    bevel = max(2, int(h * 0.006))
    draw.line([(0, int(h * CANOPY_TOP)), (w, int(h * CANOPY_TOP))], fill=BEZEL_EDGE, width=2)
    console_top = int(h * CONSOLE_TOP)
    draw.line([(0, console_top), (w, console_top)], fill=BEZEL_CONSOLE_EDGE, width=2)
    draw.rectangle([0, console_top + 2, w, console_top + 5], fill=BEZEL_DARK)

    font = ImageFont.truetype(FONT, 30) if os.path.exists(FONT) else ImageFont.load_default()
    small = ImageFont.truetype(FONT, 22) if os.path.exists(FONT) else ImageFont.load_default()
    panels = (
        ('PROXIMITY', (120, 110, 440, 230), 'ALT 1.2 km', '  0.4 m/s'),
        ('SCANNER', (620, 390, 350, 230), 'TARGET  ROCK', 'RANGE 340 m'),
        ('CARGO', (1080, 720, 380, 150), 'ORE  42 kg', 'FULL  18 %'),
        ('CLOCK', (1350, 120, 300, 160), 'x1000', '14:02'),
    )
    for title, (x, y, pw, ph), line1, line2 in panels:
        draw.text((x, y - 40), title, font=small, fill=ACCENT)
        outer = (x - bevel, y - bevel, x + pw + bevel, y + ph + bevel)
        draw.rectangle(outer, fill=BEZEL_CONSOLE)
        draw.line([(outer[0], outer[1]), (outer[2], outer[1])], fill=BEZEL_EDGE, width=bevel)
        draw.line([(outer[0], outer[1]), (outer[0], outer[3])], fill=BEZEL_EDGE, width=bevel)
        draw.line([(outer[0], outer[3] - bevel), (outer[2], outer[3] - bevel)], fill=BEZEL_DARK, width=bevel)
        draw.line([(outer[2] - bevel, outer[1]), (outer[2] - bevel, outer[3])], fill=BEZEL_DARK, width=bevel)
        draw.rectangle([x, y, x + pw - 1, y + ph - 1], fill=READOUT_BG)
        draw.rectangle([x, y, x + pw - 1, y + ph - 1], outline=BEZEL_CONSOLE_EDGE, width=1)
        draw.text((x + 18, y + 22), line1, font=font, fill=ACCENT)
        draw.text((x + 18, y + 72), line2, font=small, fill=ACCENT_DIM)
    return image


def sheet(mockups: List[Image.Image], names: List[str]) -> Image.Image:
    tile_w, tile_h, label_h = 640, 360, 34
    out = Image.new('RGB', (tile_w * 2, (tile_h + label_h) * 2), (20, 20, 20))
    label_font = ImageFont.truetype(FONT, 20) if os.path.exists(FONT) else ImageFont.load_default()
    for i, (image, name) in enumerate(zip(mockups, names)):
        x, y = (i % 2) * tile_w, (i // 2) * (tile_h + label_h)
        out.paste(image.resize((tile_w, tile_h), Image.Resampling.LANCZOS), (x, y + label_h))
        ImageDraw.Draw(out).text((x + 10, y + 6), name, font=label_font, fill=ACCENT)
    return out
# endregion


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    mockups, names = [], []
    for p in PROPOSALS:
        rects = plate_grid(np.random.default_rng(2027), *SIZE)
        texture = make_texture(p, rects, seed=3000 + p.number)
        texture.save(os.path.join(OUT, f'cockpit_miner_{p.number}.png'))
        mockup = cockpit_mockup(texture)
        mockups.append(mockup)
        names.append(f'{p.number}: {p.name}')
        print(f'Wrote proposal {p.number} ({p.name})')
    sheet(mockups, names).save(os.path.join(OUT, 'sheet.png'))
    print('Wrote sheet.png')


if __name__ == '__main__':
    main()
