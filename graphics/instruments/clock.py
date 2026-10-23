"""Ship time display."""

from __future__ import annotations
from typing import Any, Optional, Tuple
from datetime import datetime
import pygame
from galaxies.people.player import Player
from ..constants import ACCENT, AMBER, READOUT_BG, CONSOLE_EDGE_COLOR, HULL_DARK


class Clock:
    """Draw clock panel mounted on the upper right of the cockpit."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, date_time: datetime, time_scale: int, w: int, h: int,
             topleft: Optional[Tuple[int, int]] = None) -> None:
        """Draw the ship time display: at the upper right of a w x h window, or with its top left at `topleft` when given
        (the outpost screen puts it over its name)."""
        digit_font = fonts.get(max(12, int(h * 0.024)), bold=True)
        label_font = fonts.get(max(10, int(h * 0.018)))

        # Format the time display
        text = Clock._format_ship_time(date_time)

        digits = Clock._ink(digit_font.render(text, True, ACCENT))
        label = Clock._ink(label_font.render('PosDes', True, ACCENT))

        # Highlight the rate whenever time is compressed; the normal rate is bright too, beside the label
        rate_color = ACCENT if time_scale == Player.TIME_SCALE_MIN else AMBER
        rate = Clock._ink(label_font.render(Clock._format_time_scale(time_scale), True, rate_color))

        pad = max(6, int(h * 0.011))  # beside the text, and equal above and below both lines
        gap = max(8, int(w * 0.009))  # between the label and the rate
        line_gap = max(2, int(h * 0.004))  # between the two lines
        top_line = max(label.get_height(), rate.get_height())
        panel = pygame.Rect(
            0, 0,
            max(label.get_width() + gap + rate.get_width(), digits.get_width()) + pad * 2,
            top_line + line_gap + digits.get_height() + pad * 2,
        )
        if topleft is None:
            panel.topright = (int(w * 0.985), int(h * 0.025))
        else:
            panel.topleft = topleft

        pygame.draw.rect(surface, HULL_DARK, panel.inflate(6, 6))
        pygame.draw.rect(surface, READOUT_BG, panel)
        pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, panel, 2)

        # The label on the left and the rate on the right of the top line, the digits centred under them
        top_middle = panel.top + pad + top_line // 2
        surface.blit(label, label.get_rect(midleft=(panel.left + pad, top_middle)))
        surface.blit(rate, rate.get_rect(midright=(panel.right - pad, top_middle)))
        surface.blit(digits, digits.get_rect(midtop=(panel.centerx, panel.top + pad + top_line + line_gap)))

    @staticmethod
    def _ink(text: pygame.Surface) -> pygame.Surface:
        """The part of a rendered text that has ink, without the font's empty space above and below, so the lines centre."""
        return text.subsurface(text.get_bounding_rect())

    @staticmethod
    def _format_ship_time(moment: datetime) -> str:
        """Format ISO 8601 layout without zero-padding the year, e.g. '700-01-01 00:00:00'."""
        return (f'{moment.year}-{moment.month:02d}-{moment.day:02d} '
                f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}')

    @staticmethod
    def _format_time_scale(scale: int) -> str:
        """Compression rate as a compact multiplier, e.g. 'x1' or 'x1 000 000'."""
        return f'x{scale:,}'.replace(',', ' ')
