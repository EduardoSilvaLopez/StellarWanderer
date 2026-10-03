"""Cargo hold contents display."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..Constants import ACCENT, ACCENT_DIM
from .common import draw_beveled_panel

if TYPE_CHECKING:
    from Player import Player


class Cargo:
    """Draw the CARGO list: one line per hold element, name and quantity."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, player: Player, rect: pygame.Rect) -> None:
        """Draw the cargo hold contents."""
        label_font = fonts.get(max(9, int(h * 0.017)))
        label = label_font.render('CARGO', True, ACCENT_DIM)
        surface.blit(label, label.get_rect(midbottom=(rect.centerx, rect.top - 12)))

        draw_beveled_panel(surface, rect, depth=4)

        line_font = fonts.get(max(9, int(h * 0.017)))
        pad = max(6, rect.width // 16)
        line_spacing = line_font.get_height() + max(2, int(h * 0.006))
        line_y = rect.top + pad
        for element, quantity in player.ship.cargo_hold.content.items():
            line = line_font.render(f'{element.name}: {quantity}', True, ACCENT)
            surface.blit(line, (rect.left + pad, line_y))
            line_y += line_spacing
