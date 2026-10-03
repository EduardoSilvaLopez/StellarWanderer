"""Notification message bar."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..Constants import READOUT_BG, CONSOLE_EDGE_COLOR

if TYPE_CHECKING:
    from Player import Player


class Notification:
    """Draw a full-width notification bar at the bottom with red text."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, y: int, height: int, player: Player) -> None:
        """Draw the notification bar."""
        # Draw background and border
        rect = pygame.Rect(0, y, w, height)
        pygame.draw.rect(surface, READOUT_BG, rect)
        pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, rect, 1)

        # Render notification text in red, centered vertically with left padding
        text_font = fonts.get(max(10, int(height * 0.6)))
        pad = max(8, int(w * 0.02))
        notification_text = text_font.render(player.ship.notification, True, (255, 64, 64))
        text_rect = notification_text.get_rect(midleft=(rect.left + pad, rect.centery))
        surface.blit(notification_text, text_rect)
