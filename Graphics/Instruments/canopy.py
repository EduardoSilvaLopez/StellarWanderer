"""Windshield frame and hull rendering."""

from __future__ import annotations
import pygame
from ..Constants import CANOPY_TOP, CONSOLE_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET, HULL_EDGE_COLOR
from .common import get_windshield_frame_texture


class Canopy:
    """Draw hull frame: top rail, two A-pillars, and struts between panes."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int) -> None:
        """Draw the windshield canopy."""
        top = int(h * CANOPY_TOP)
        bottom = int(h * CONSOLE_TOP)
        top_inset = w * CANOPY_TOP_INSET
        bottom_inset = w * CANOPY_BOTTOM_INSET

        # Hull frame shapes (rail, pillars, struts), filled with the cockpit
        # texture masked to their silhouette — the glass panes between them
        # are left untouched so the 3D scene shows through.
        frame_texture = get_windshield_frame_texture(w, h)
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
