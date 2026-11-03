"""Proposals for the cockpit's background texture and instrument bezels: four looks of patched steel plates.

All four share the patched plates (three reds, welded), the bare steel under the paint, the scratches and the bezel
colours. They differ in the metal parts at the joints: bolts, rivets, weld beads, lapped edges, a repair patch.

Writes into temp/cockpit_proposals/: cockpit_background_<n>.png (the texture, 1280 x 720 so the game does not stretch it at
16:9), mockup_<n>.png (the cockpit view with the bezels drawn as the game draws them) and sheet.png (all four).
Nothing in the game is changed. Run with PYTHONPYCACHEPREFIX set to the scratchpad.
"""

from __future__ import annotations
import math
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'temp', 'cockpit_proposals')  # generated, not in git
FONT = os.path.join(ROOT, 'common', 'resources', 'fonts', 'Oxanium.ttf')

SIZE = (1280, 720)  # the texture and the mockup: 16:9, the same proportions as the window
PEEL = 0.06  # share of the surface where the paint has come off
PLATES = ((104, 76, 70), (92, 82, 76), (112, 88, 80))  # three reds, grey-brown: moderate saturation
STEEL = (104, 103, 105)  # the bare metal under the paint
SCRATCH = (150, 146, 146)
BOLT = (150, 146, 146)
BOLT_LIGHT = (198, 194, 192)
SOCKET = (52, 49, 49)
SHADOW = (30, 27, 27)
WELD = (84, 78, 76)
HEAT = (126, 84, 58)  # the discolouring round a weld
LIP_LIGHT = (150, 130, 124)
LIP_SHADE = (48, 44, 44)
READOUT_BG = (9, 17, 21)  # unchanged: the screens keep their look
ACCENT = (94, 234, 212)
ACCENT_DIM = (34, 92, 92)
CANOPY_TOP = 0.055
CONSOLE_TOP = 0.66

# The bezel: the colours of draw_beveled_panel and of the canopy's edge.
BEZEL_CONSOLE = (44, 40, 38)
BEZEL_EDGE = (108, 101, 94)
BEZEL_DARK = (26, 24, 24)
BEZEL_CONSOLE_EDGE = (150, 118, 70)  # the one muted ochre accent


@dataclass
class Proposal:
    number: int
    name: str
    lips: bool  # the plates' edges are raised: a light and a dark line along each seam
    welds: bool  # weld beads, with the discolouring of the heat, along the seams
    fastener: Optional[str]  # 'bolt' (hex socket), 'rivet' (domed), or None
    spacing: int  # px between fasteners along a seam
    patch: bool  # a repair plate, held by four bolts, on one of the plates


PROPOSALS = (
    Proposal(1, 'Bolted seams', lips=True, welds=False, fastener='bolt', spacing=110, patch=False),
    Proposal(2, 'Welded seams', lips=False, welds=True, fastener=None, spacing=0, patch=False),
    Proposal(3, 'Riveted laps', lips=True, welds=False, fastener='rivet', spacing=60, patch=False),
    Proposal(4, 'Mixed joints', lips=True, welds=True, fastener='bolt', spacing=150, patch=True),
)


# region Noise
def value_noise(rng: np.random.Generator, h: int, w: int, cell_y: int, cell_x: int) -> np.ndarray:
    """Smooth random field in 0..1, with features cell_y by cell_x pixels."""
    grid = rng.random((max(2, h // cell_y + 2), max(2, w // cell_x + 2))).astype(np.float32)
    field = np.asarray(Image.fromarray(grid, mode='F').resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32)
    return (field - field.min()) / max(1e-6, field.max() - field.min())


def fbm(rng: np.random.Generator, h: int, w: int, cell: int, octaves: int = 4) -> np.ndarray:
    """Layered value noise: each octave has half the features and half the strength of the one before."""
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
    """The plates: a grid of four columns and three rows, each line moved a little so no two joints line up."""
    xs = [0] + sorted(int(w * i / 4 + rng.uniform(-0.05, 0.05) * w) for i in (1, 2, 3)) + [w]
    ys = [0] + sorted(int(h * i / 3 + rng.uniform(-0.06, 0.06) * h) for i in (1, 2)) + [h]
    return [(x0, y0, x1, y1) for y0, y1 in zip(ys, ys[1:]) for x0, x1 in zip(xs, xs[1:])]


def paint_layer(rng: np.random.Generator, rects: List[Rect], w: int, h: int) -> np.ndarray:
    plates = Image.new('RGB', (w, h))
    draw = ImageDraw.Draw(plates)
    for x0, y0, x1, y1 in rects:
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=PLATES[int(rng.integers(len(PLATES)))])
    paint = np.asarray(plates, dtype=np.float32).copy()
    paint *= (0.9 + 0.2 * fbm(rng, h, w, 64))[..., None]  # mottling of the paint
    paint *= (0.85 + 0.2 * fbm(rng, h, w, 24))[..., None]  # grime, darker in patches
    return paint


def seams(rects: List[Rect], w: int, h: int) -> List[Tuple[int, int, int, int]]:
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
    paint = paint_layer(rng, rects, w, h)

    metal = np.broadcast_to(np.array(STEEL, np.float32), (h, w, 3)).copy()
    metal *= (0.85 + 0.3 * value_noise(rng, h, w, 2, 30))[..., None]  # rolled steel, streaked
    metal *= (0.9 + 0.2 * fbm(rng, h, w, 40))[..., None]

    # The peeled areas: low-frequency noise with some roughness, so their edges are irregular.
    field = 0.75 * fbm(rng, h, w, 48) + 0.25 * value_noise(rng, h, w, 5, 5)
    peel = field > np.quantile(field, 1 - PEEL)
    rim = np.asarray(Image.fromarray((peel * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)))
    rim = (rim > 0) & ~peel
    shadow = np.roll(peel, (2, 2), axis=(0, 1)) & ~peel  # the paint just below a peeled edge is in shade

    out = np.where(peel[..., None], metal, paint)
    out = np.where(rim[..., None], paint * 1.25, out)  # the curled, lighter lip of the paint
    out = np.where(shadow[..., None] & ~peel[..., None], out * 0.7, out)

    marks = Image.new('L', (w, h), 0)
    gouges = Image.new('L', (w, h), 0)
    draw_marks = ImageDraw.Draw(marks)
    draw_gouges = ImageDraw.Draw(gouges)
    for _ in range(130):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        angle = rng.uniform(0, math.pi)
        length = rng.uniform(15, 110)
        draw_marks.line([(x, y), (x + length * math.cos(angle), y + length * math.sin(angle))], fill=255, width=1)
    for _ in range(80):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        draw_gouges.line([(x, y), (x + rng.uniform(1, 4), y + rng.uniform(-1, 1))], fill=255, width=1)
    marks = np.asarray(marks.filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32)[..., None] / 255
    gouges = np.asarray(gouges.filter(ImageFilter.GaussianBlur(0.4)), dtype=np.float32)[..., None] / 255
    out = out * (1 - 0.4 * marks) + np.array(SCRATCH, np.float32) * 0.4 * marks  # bare metal in the paint
    out = out * (1 - 0.6 * gouges) + np.array((30, 26, 26), np.float32) * 0.6 * gouges  # dark grooves

    specks = np.zeros((h, w), bool)
    specks[rng.integers(0, h, 250), rng.integers(0, w, 250)] = True
    specks &= ~peel  # rust spots on the paint only
    out[specks] = (66, 38, 30)

    image = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGB')
    draw_joints(image, p, rects, rng)
    return image.convert('RGBA')


def draw_joints(image: Image.Image, p: Proposal, rects: List[Rect], rng: np.random.Generator) -> None:
    """The metal at the joints: lips, weld beads with their heat, fasteners, and the repair patch."""
    w, h = SIZE
    draw = ImageDraw.Draw(image)
    lines = seams(rects, w, h)

    if p.welds:
        heat = Image.new('L', (w, h), 0)
        heat_draw = ImageDraw.Draw(heat)
        for x0, y0, x1, y1 in lines:
            if rng.random() < 0.7:  # not every joint is welded, as on a real hull
                heat_draw.line([(x0, y0), (x1, y1)], fill=255, width=14)
        mask = np.asarray(heat.filter(ImageFilter.GaussianBlur(6)), dtype=np.float32)[..., None] / 255
        base = np.asarray(image, dtype=np.float32)
        image.paste(Image.fromarray(np.clip(base * (1 - 0.3 * mask) + np.array(HEAT, np.float32) * 0.3 * mask,
                                            0, 255).astype(np.uint8)))
        draw = ImageDraw.Draw(image)

    for x0, y0, x1, y1 in lines:
        if p.lips:
            if y0 == y1:
                draw.line([(x0, y0 - 1), (x1, y0 - 1)], fill=LIP_LIGHT, width=1)
                draw.line([(x0, y0 + 1), (x1, y0 + 1)], fill=LIP_SHADE, width=1)
            else:
                draw.line([(x0 - 1, y0), (x0 - 1, y1)], fill=LIP_LIGHT, width=1)
                draw.line([(x0 + 1, y0), (x0 + 1, y1)], fill=LIP_SHADE, width=1)
        if p.welds and rng.random() < 0.7:
            draw_weld(draw, (x0, y0, x1, y1), rng)
        if p.fastener:
            draw_fasteners(draw, (x0, y0, x1, y1), p, rng)

    if p.patch:
        draw_patch(draw, rects, rng)


def draw_weld(draw: ImageDraw.ImageDraw, segment: Tuple[int, int, int, int], rng: np.random.Generator) -> None:
    """A bead of weld along a joint: a row of small humps, lit from the top-left."""
    x0, y0, x1, y1 = segment
    horizontal = y0 == y1
    length = (x1 - x0) if horizontal else (y1 - y0)
    for along in range(4, length - 4, 4):
        cx, cy = (x0 + along, y0) if horizontal else (x0, y0 + along)
        r = int(rng.integers(2, 4))
        draw.ellipse([cx - r + 1, cy - r + 2, cx + r + 1, cy + r + 2], fill=SHADOW)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WELD)
        draw.ellipse([cx - r, cy - r, cx, cy], fill=BOLT)


def draw_fasteners(draw: ImageDraw.ImageDraw, segment: Tuple[int, int, int, int], p: Proposal,
                   rng: np.random.Generator) -> None:
    """Bolts or rivets along a joint, set in the lower or right plate's flange."""
    x0, y0, x1, y1 = segment
    horizontal = y0 == y1
    length = (x1 - x0) if horizontal else (y1 - y0)
    for along in range(p.spacing // 2, length - p.spacing // 4, p.spacing):
        cx, cy = (x0 + along, y0 + 4) if horizontal else (x0 + 4, y0 + along)
        if p.fastener == 'bolt':
            draw_bolt(draw, cx, cy, 5)
        else:
            draw_rivet(draw, cx, cy, 4)


def draw_bolt(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    """A hex-socket bolt head: shadow below and right, a lit top-left."""
    draw.ellipse([cx - r + 1, cy - r + 2, cx + r + 1, cy + r + 2], fill=SHADOW)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BOLT)
    draw.ellipse([cx - r + 1, cy - r + 1, cx - 1, cy - 1], fill=BOLT_LIGHT)
    s = r * 0.5
    draw.polygon([(cx - s, cy), (cx - s / 2, cy - s), (cx + s / 2, cy - s), (cx + s, cy),
                  (cx + s / 2, cy + s), (cx - s / 2, cy + s)], fill=SOCKET)


def draw_rivet(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    """A domed rivet head, with no socket."""
    draw.ellipse([cx - r + 1, cy - r + 2, cx + r + 1, cy + r + 2], fill=SHADOW)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BOLT)
    draw.ellipse([cx - r + 1, cy - r + 1, cx, cy], fill=BOLT_LIGHT)


def draw_patch(draw: ImageDraw.ImageDraw, rects: List[Rect], rng: np.random.Generator) -> None:
    """A repair plate on the plate with the most room, its edges lapped and held by four bolts at its corners."""
    x0, y0, x1, y1 = max(rects, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    pw, ph = x1 - x0, y1 - y0
    left, top = x0 + int(pw * 0.2), y0 + int(ph * 0.25)
    right, bottom = x0 + int(pw * 0.55), y0 + int(ph * 0.72)
    draw.line([(left, bottom), (left, top), (right, top)], fill=LIP_LIGHT, width=2)
    draw.line([(left, bottom), (right, bottom), (right, top)], fill=LIP_SHADE, width=2)
    for cx, cy in ((left + 9, top + 9), (right - 9, top + 9), (left + 9, bottom - 9), (right - 9, bottom - 9)):
        draw_bolt(draw, cx, cy, 4)
# endregion


# region Mockup
def cockpit_mockup(texture: Image.Image) -> Image.Image:
    """The texture as the game shows it (darkened on the left as get_cockpit_background does), with the canopy edge,
    the console bar and four instruments drawn with the bezel colours."""
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

    font = ImageFont.truetype(FONT, 22) if os.path.exists(FONT) else ImageFont.load_default()
    small = ImageFont.truetype(FONT, 16) if os.path.exists(FONT) else ImageFont.load_default()
    panels = (
        ('PROXIMITY', (90, 80, 330, 170), 'ALT 1.2 km', '  0.4 m/s'),
        ('SCANNER', (460, 280, 260, 170), 'TARGET  ROCK', 'RANGE 340 m'),
        ('CARGO', (800, 530, 280, 110), 'ORE  42 kg', 'FULL  18 %'),
        ('CLOCK', (1000, 90, 220, 120), 'x1000', '14:02'),
    )
    for title, (x, y, pw, ph), line1, line2 in panels:
        draw.text((x, y - 30), title, font=small, fill=ACCENT)
        outer = (x - bevel, y - bevel, x + pw + bevel, y + ph + bevel)
        draw.rectangle(outer, fill=BEZEL_CONSOLE)
        draw.line([(outer[0], outer[1]), (outer[2], outer[1])], fill=BEZEL_EDGE, width=bevel)
        draw.line([(outer[0], outer[1]), (outer[0], outer[3])], fill=BEZEL_EDGE, width=bevel)
        draw.line([(outer[0], outer[3] - bevel), (outer[2], outer[3] - bevel)], fill=BEZEL_DARK, width=bevel)
        draw.line([(outer[2] - bevel, outer[1]), (outer[2] - bevel, outer[3])], fill=BEZEL_DARK, width=bevel)
        draw.rectangle([x, y, x + pw - 1, y + ph - 1], fill=READOUT_BG)
        draw.line([(x, y), (x + pw - 1, y)], fill=BEZEL_DARK, width=2)
        draw.line([(x, y), (x, y + ph - 1)], fill=BEZEL_DARK, width=2)
        draw.line([(x, y + ph - 1), (x + pw - 1, y + ph - 1)], fill=BEZEL_EDGE, width=1)
        draw.line([(x + pw - 1, y), (x + pw - 1, y + ph - 1)], fill=BEZEL_EDGE, width=1)
        draw.rectangle([x, y, x + pw - 1, y + ph - 1], outline=BEZEL_CONSOLE_EDGE, width=1)
        draw.text((x + 14, y + 16), line1, font=font, fill=ACCENT)
        draw.text((x + 14, y + 52), line2, font=small, fill=ACCENT_DIM)
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
        texture = make_texture(p, rects, seed=2027 + p.number)
        texture.save(os.path.join(OUT, f'cockpit_background_{p.number}.png'))
        mockup = cockpit_mockup(texture)
        mockup.save(os.path.join(OUT, f'mockup_{p.number}.png'))
        mockups.append(mockup)
        names.append(f'{p.number}: {p.name}')
        print(f'Wrote proposal {p.number} ({p.name})')
    sheet(mockups, names).save(os.path.join(OUT, 'sheet.png'))
    print('Wrote sheet.png')


if __name__ == '__main__':
    main()
