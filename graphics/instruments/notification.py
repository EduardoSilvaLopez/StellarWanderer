"""Notification message bar."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import READOUT_BG, CONSOLE_EDGE_COLOR, BINDING_NEAR_GREEN, NOTIFICATION_BAD_ORANGE

if TYPE_CHECKING:
    from spaceships.ship import Ship

ALERT_COLOUR = (255, 64, 64)
ALERT_PREFIXES = ('CRITICAL', 'WARNING')


class notification_bar:
    """Draw a full-width notification bar at the bottom: red for a CRITICAL or WARNING message, orange for a refused or
    failed attempt (`Notification.bad`), green for the rest."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, y: int, height: int, ship: Ship) -> None:
        """Draw the notification bar."""
        # Draw background and border
        rect = pygame.Rect(0, y, w, height)
        pygame.draw.rect(surface, READOUT_BG, rect)
        pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, rect, 1)

        # Render notification text, centered vertically with left padding
        text_font = fonts.get(max(10, int(height * 0.6)))
        pad = max(8, int(w * 0.02))
        message = ship.notification.message
        if message.startswith(ALERT_PREFIXES):
            colour = ALERT_COLOUR
        else:
            colour = NOTIFICATION_BAD_ORANGE if ship.notification.bad else BINDING_NEAR_GREEN
        notification_text = text_font.render(message, True, colour)
        text_rect = notification_text.get_rect(midleft=(rect.left + pad, rect.centery))
        surface.blit(notification_text, text_rect)
