"""Ship time display."""

from __future__ import annotations
from typing import Any
from datetime import datetime
import pygame
from ..Constants import ACCENT, ACCENT_DIM, AMBER, READOUT_BG, CONSOLE_EDGE_COLOR, HULL_DARK

if __name__ == '__main__':
    from Player import Player
else:
    import sys
    sys.path.insert(0, '../..')
    try:
        from Player import Player
    except ImportError:
        Player = None


class Clock:
    """Draw clock panel mounted on the upper right of the cockpit."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, date_time: datetime, time_scale: int, w: int, h: int) -> None:
        """Draw the ship time display."""
        digit_font = fonts.get(max(14, int(h * 0.030)), bold=True)
        label_font = fonts.get(max(9, int(h * 0.016)))

        # Format the time display
        text = Clock.format_ship_time(date_time)

        digits = digit_font.render(text, True, ACCENT)
        label = label_font.render('SHIP TIME', True, ACCENT_DIM)

        # Highlight the rate whenever time is compressed
        if Player is not None:
            rate_color = ACCENT_DIM if time_scale == Player.TIME_SCALE_MIN else AMBER
        else:
            rate_color = ACCENT_DIM
        rate = label_font.render(Clock.format_time_scale(time_scale), True, rate_color)

        pad = max(8, int(h * 0.014))
        gap = max(10, int(w * 0.012))
        header_w = label.get_width() + gap + rate.get_width()
        panel = pygame.Rect(
            0, 0,
            max(digits.get_width(), header_w) + pad * 2,
            digits.get_height() + label.get_height() + pad * 2,
        )
        panel.topright = (int(w * 0.975), int(h * 0.075))

        pygame.draw.rect(surface, HULL_DARK, panel.inflate(6, 6))
        pygame.draw.rect(surface, READOUT_BG, panel)
        pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, panel, 2)

        surface.blit(label, (panel.left + pad, panel.top + pad))
        surface.blit(rate, rate.get_rect(topright=(panel.right - pad, panel.top + pad)))
        surface.blit(digits, (panel.left + pad, panel.top + pad + label.get_height()))

    @staticmethod
    def format_ship_time(moment: datetime) -> str:
        """Format ISO 8601 layout without zero-padding the year, e.g. '700-01-01 00:00:00'."""
        return (f'{moment.year}-{moment.month:02d}-{moment.day:02d} '
                f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}')

    @staticmethod
    def format_time_scale(scale: int) -> str:
        """Compression rate as a compact multiplier, e.g. 'x1' or 'x1 000 000'."""
        return f'x{scale:,}'.replace(',', ' ')
