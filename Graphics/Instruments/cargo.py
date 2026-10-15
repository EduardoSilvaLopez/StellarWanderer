"""Cargo hold contents display."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM
from .common import draw_beveled_panel, bezel_depth

if TYPE_CHECKING:
    from Spaceships.ship import Ship


def format_quantity(value: float) -> str:
    """At most two decimals, without trailing zeros: 5 -> '5', 2.5 -> '2.5', 0.333 -> '0.33'."""
    # + 0.0 turns a rounded -0.0 into 0.0, so a tiny negative value does not show as '-0'.
    return f'{round(value, 2) + 0.0:.2f}'.rstrip('0').rstrip('.')


class Cargo:
    """Draw the CARGO list: one line per hold element, name and quantity."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, rect: pygame.Rect) -> None:
        """Draw the cargo hold contents."""
        label_font = fonts.get(max(9, int(h * 0.017)))
        label = label_font.render('CARGO', True, ACCENT_DIM)
        surface.blit(label, label.get_rect(midbottom=(rect.centerx, rect.top - 12)))

        draw_beveled_panel(surface, rect, depth=bezel_depth(h))

        line_font = fonts.get(max(9, int(h * 0.017)))
        pad = max(6, rect.width // 16)
        line_spacing = line_font.get_height() + max(2, int(h * 0.006))
        line_y = rect.top + pad
        for element, quantity in ship.cargo_hold.serialize().items():
            line = line_font.render(f'{element.upper()}: {format_quantity(quantity)}', True, ACCENT)
            surface.blit(line, (rect.left + pad, line_y))
            line_y += line_spacing
