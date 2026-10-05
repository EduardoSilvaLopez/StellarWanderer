"""Crosshair centered in the canopy to indicate forward direction."""

from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from ..Constants import CONSOLE_TOP, ACCENT

if TYPE_CHECKING:
    from Player import Player


class Crosshair:
    """A simple crosshair at the center of the canopy view."""

    SIZE = 20  # Half-length of each arm in pixels
    THICKNESS = 2  # Line width in pixels

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int) -> None:
        """Draw a crosshair at the center of the canopy.

        Args:
            surface: Pygame surface to draw on
            w: Window width
            h: Window height
        """
        center_x = w // 2
        center_y = int(h * CONSOLE_TOP / 2)

        # Horizontal line
        pygame.draw.line(
            surface, ACCENT,
            (center_x - Crosshair.SIZE, center_y),
            (center_x + Crosshair.SIZE, center_y),
            Crosshair.THICKNESS
        )

        # Vertical line
        pygame.draw.line(
            surface, ACCENT,
            (center_x, center_y - Crosshair.SIZE),
            (center_x, center_y + Crosshair.SIZE),
            Crosshair.THICKNESS
        )
