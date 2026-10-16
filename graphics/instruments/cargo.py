"""Cargo hold contents display."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import ACCENT, BINDING_MARK_RED
from .common import draw_beveled_panel, bezel_depth, draw_panel_title

if TYPE_CHECKING:
    from spaceships.ship import Ship


def format_quantity(value: float) -> str:
    """At most two decimals, without trailing zeros: 5 -> '5', 2.5 -> '2.5', 0.333 -> '0.33'."""
    # + 0.0 turns a rounded -0.0 into 0.0, so a tiny negative value does not show as '-0'.
    return f'{round(value, 2) + 0.0:.2f}'.rstrip('0').rstrip('.')


class Cargo:
    """Draw the CARGO list: one line per hold element, name and quantity."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, rect: pygame.Rect, title_top: int) -> None:
        """Draw the cargo hold contents, in `rect`, under a title whose top is `title_top`."""
        label_font = fonts.get(max(9, int(h * 0.017)))
        draw_panel_title(surface, label_font, 'CARGO', rect.centerx, title_top)

        draw_beveled_panel(surface, rect, depth=bezel_depth(h))

        line_font = fonts.get(max(9, int(h * 0.017)))
        pad = max(6, rect.width // 16)
        line_spacing = line_font.get_height() + max(2, int(h * 0.006))
        line_y = rect.top + pad
        warning_days = ship.cargo_hold.WARNING_DAYS
        for element, quantity in ship.cargo_hold.serialize().items():
            # Red at or below the warning level, as the ship's notice says.
            warning = element in warning_days and quantity <= warning_days[element]
            colour = BINDING_MARK_RED if warning else ACCENT
            line = line_font.render(f'{element.upper()}: {format_quantity(quantity)}', True, colour)
            surface.blit(line, (rect.left + pad, line_y))
            line_y += line_spacing
