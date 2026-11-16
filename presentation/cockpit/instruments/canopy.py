"""Windshield frame and hull rendering."""

from __future__ import annotations
from typing import Dict, Tuple

import pygame
from ..constants import CANOPY_TOP, CONSOLE_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET, HULL_EDGE_COLOR
from .common import get_windshield_frame_texture

_frame_bytes: Dict[Tuple[str, int, int], bytes] = {}   # the frame's memory, for the window size in use


class Canopy:
    """Draw hull frame: top rail, two A-pillars, and struts between panes."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, texture: str) -> None:
        """Draw the windshield canopy, its frame in the cockpit texture file `texture`. It starts the cockpit's layer:
        the rows above the console are replaced, by a plain copy of the frame's memory where the two surfaces share
        their layout (blending it over a cleared layer, as before, was one of the largest costs of a frame). The rows
        of the console are left as they are: the console is drawn on its own schedule."""
        top = int(h * CANOPY_TOP)
        bottom = int(h * CONSOLE_TOP)
        top_inset = w * CANOPY_TOP_INSET
        bottom_inset = w * CANOPY_BOTTOM_INSET

        # Hull frame shapes (rail, pillars, struts), filled with the cockpit
        # texture masked to their silhouette — the glass panes between them
        # are left untouched so the 3D scene shows through.
        frame_texture = get_windshield_frame_texture(w, h, texture)
        layout = (surface.get_size(), surface.get_pitch(), surface.get_masks())
        if (frame_texture.get_size(), frame_texture.get_pitch(), frame_texture.get_masks()) == layout:
            key = (texture, w, h)
            if key not in _frame_bytes:
                _frame_bytes.clear()
                _frame_bytes[key] = frame_texture.get_buffer().raw[:bottom * frame_texture.get_pitch()]
            surface.get_buffer().write(_frame_bytes[key])
        else:
            surface.fill((0, 0, 0, 0), pygame.Rect(0, 0, w, bottom))
            surface.blit(frame_texture, (0, 0))

        # Top rail edge.
        pygame.draw.line(surface, HULL_EDGE_COLOR, (0, top - 1), (w, top - 1), 2)

        # A-pillars, angling inward as they rise.
        left = [(0, 0), (top_inset, top), (bottom_inset, bottom), (0, bottom)]
        right = [(w, 0), (w - top_inset, top), (w - bottom_inset, bottom), (w, bottom)]
        for pillar in (left, right):
            points = [(int(x), int(y)) for x, y in pillar]
            pygame.draw.lines(surface, HULL_EDGE_COLOR, False, points[1:3], 2)

        # Two vertical struts splitting the windshield into three panes.
        for frac in (1 / 3, 2 / 3):
            half = max(2, int(w * 0.004))
            x_top = top_inset + (w - 2 * top_inset) * frac
            x_bottom = bottom_inset + (w - 2 * bottom_inset) * frac
            strut = [
                (int(x_top - half), top), (int(x_top + half), top),
                (int(x_bottom + half), bottom), (int(x_bottom - half), bottom),
            ]
            pygame.draw.line(surface, HULL_EDGE_COLOR, strut[0], strut[3], 1)
