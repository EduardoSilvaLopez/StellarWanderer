"""Deep space background rendering."""

from __future__ import annotations
import pygame
from .Constants import SPACE_COLOR, CONSOLE_TOP


class DeepSpace:
    """Renders the deep space background through the canopy."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int) -> None:
        """Draw space background.

        Args:
            surface: Pygame surface to draw on
            w: Window width
            h: Window height
        """
        view_h = int(h * CONSOLE_TOP)
        surface.fill(SPACE_COLOR, (0, 0, w, view_h))
