"""Deep space background rendering."""

import pygame
from .Constants import SPACE, CONSOLE_TOP


class DeepSpace:
    """Renders the deep space background through the canopy."""

    @staticmethod
    def draw(surface, w, h):
        """Draw space background.

        Args:
            surface: Pygame surface to draw on
            w: Window width
            h: Window height
        """
        view_h = int(h * CONSOLE_TOP)
        surface.fill(SPACE, (0, 0, w, view_h))
