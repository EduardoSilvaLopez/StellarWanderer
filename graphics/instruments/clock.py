"""Ship time display."""

from __future__ import annotations
from typing import Any, Optional, Tuple
from datetime import datetime
import pygame
from galaxies.people.player import Player
from ..constants import ACCENT, ACCENT_DIM, AMBER, READOUT_BG, CONSOLE_EDGE_COLOR, HULL_DARK


class Clock:
    """Draw clock panel mounted on the upper right of the cockpit."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, date_time: datetime, time_scale: int, w: int, h: int,
             topleft: Optional[Tuple[int, int]] = None) -> None:
        """Draw the ship time display: at the upper right of a w x h window, or with its top left at `topleft` when given
        (the outpost screen puts it over its name)."""
        digit_font = fonts.get(max(12, int(h * 0.024)), bold=True)
        label_font = fonts.get(max(8, int(h * 0.013)))

        # Format the time display
        text = Clock._format_ship_time(date_time)

        digits = digit_font.render(text, True, ACCENT)
        label = label_font.render('SHIP TIME', True, ACCENT_DIM)

        # Highlight the rate whenever time is compressed; the normal rate stays dim
        rate_color = ACCENT_DIM if time_scale == Player.TIME_SCALE_MIN else AMBER
        rate = label_font.render(Clock._format_time_scale(time_scale), True, rate_color)

        pad = max(6, int(h * 0.011))  # beside the text
        top_pad = max(2, int(h * 0.004))  # above and below the text: tight, the panel is short
        gap = max(8, int(w * 0.009))
        header_w = label.get_width() + gap + rate.get_width()
        panel = pygame.Rect(
            0, 0,
            max(digits.get_width(), header_w) + pad * 2,
            digits.get_height() + label.get_height() + top_pad * 2,
        )
        if topleft is None:
            panel.topright = (int(w * 0.985), int(h * 0.025))
        else:
            panel.topleft = topleft

        pygame.draw.rect(surface, HULL_DARK, panel.inflate(6, 6))
        pygame.draw.rect(surface, READOUT_BG, panel)
        pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, panel, 2)

        surface.blit(label, (panel.left + pad, panel.top + top_pad))
        surface.blit(rate, rate.get_rect(topright=(panel.right - pad, panel.top + top_pad)))
        surface.blit(digits, (panel.left + pad, panel.top + top_pad + label.get_height()))

    @staticmethod
    def _format_ship_time(moment: datetime) -> str:
        """Format ISO 8601 layout without zero-padding the year, e.g. '700-01-01 00:00:00'."""
        return (f'{moment.year}-{moment.month:02d}-{moment.day:02d} '
                f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}')

    @staticmethod
    def _format_time_scale(scale: int) -> str:
        """Compression rate as a compact multiplier, e.g. 'x1' or 'x1 000 000'."""
        return f'x{scale:,}'.replace(',', ' ')
