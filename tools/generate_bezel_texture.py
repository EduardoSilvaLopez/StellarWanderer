"""Generate common/resources/textures/bezel.png, the frame round a screen of the outpost (common/dialogs/outpost_screen.py).

Run from the project root:  python tools/generate_bezel_texture.py  (it reuses the wear and rivet helpers of
generate_outpost_texture.py, so it must stay in tools/).

The frame is a 128 x 128 texture with a 16 px border; the centre is transparent, the picture shows through. The
dialogs draw it nine-sliced: the corners keep their size and only the edges are stretched. So the rivets sit in the
corners, the only parts that keep their shape, and the edges have no detail that would stretch badly.

Style: the outpost's, painted steel with dust, scratches and pits, a light bevel on the top and left and a dark one on
the bottom and right, and a thin teal line, the interface's accent, just inside the outer edge.
"""

from __future__ import annotations
import os
import sys

import numpy as np
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_outpost_texture import fbm, rivet, shade, to_array, to_surface, weather  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT = os.path.join(ROOT, 'common', 'resources', 'textures', 'bezel.png')

SIZE = 128
BORDER = 16  # the frame's width in the texture; the centre inside it is transparent
STEEL = (118, 124, 132)
ACCENT_LINE = (70, 190, 172)
BEVEL = 3  # the width of the light and dark edges
RIVETS = (BORDER // 2 + 1, SIZE - BORDER // 2 - 2)  # rivet centres in the corners


def paint() -> pygame.Surface:
    rng = np.random.default_rng(2027)
    steel = pygame.Surface((SIZE, SIZE))
    steel.fill(STEEL)
    array = to_array(steel)
    array *= (0.9 + 0.2 * fbm(rng, SIZE, SIZE, 4))[..., None]
    surface = weather(to_surface(array), rng, 1.3)

    pygame.draw.rect(surface, shade(STEEL, 1.45), pygame.Rect(0, 0, SIZE, BEVEL))
    pygame.draw.rect(surface, shade(STEEL, 1.45), pygame.Rect(0, 0, BEVEL, SIZE))
    pygame.draw.rect(surface, shade(STEEL, 0.45), pygame.Rect(0, SIZE - BEVEL, SIZE, BEVEL))
    pygame.draw.rect(surface, shade(STEEL, 0.45), pygame.Rect(SIZE - BEVEL, 0, BEVEL, SIZE))
    pygame.draw.rect(surface, shade(STEEL, 0.35), pygame.Rect(BORDER - 1, BORDER - 1, SIZE - 2 * BORDER + 2,
                                                              SIZE - 2 * BORDER + 2), 1)  # the groove at the opening
    pygame.draw.rect(surface, ACCENT_LINE, pygame.Rect(4, 4, SIZE - 8, SIZE - 8), 1)

    for x in RIVETS:
        for y in RIVETS:
            rivet(surface, x, y, 2)

    frame = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    frame.blit(surface, (0, 0))
    pygame.draw.rect(frame, (0, 0, 0, 0), pygame.Rect(BORDER, BORDER, SIZE - 2 * BORDER, SIZE - 2 * BORDER))
    return frame


def main() -> None:
    pygame.init()
    frame = paint()
    pygame.image.save(frame, OUTPUT)
    print(f'Wrote {OUTPUT} ({SIZE} x {SIZE}, border {BORDER})')


if __name__ == '__main__':
    main()
