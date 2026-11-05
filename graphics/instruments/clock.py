"""Ship time display."""

from __future__ import annotations
from typing import Any, Optional, Tuple
from datetime import datetime
import pygame
from galaxies.people.player import Player
from ..constants import ACCENT, AMBER, READOUT_BG, CONSOLE_EDGE_COLOR, HULL_DARK

DANGER_BG = (190, 30, 34)  # the box when the time compression is clearly dangerous
DANGER_INK = (255, 240, 240)


class Clock:
    """Draw clock panel: on one line in the cockpit, beside the system's name, and on two rows over the name of a
    settlement's screen."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, date_time: datetime, time_scale: int, w: int, h: int,
             topleft: Optional[Tuple[int, int]] = None, right_middle: Optional[Tuple[int, int]] = None,
             dangerous: bool = False) -> None:
        """Draw the ship time display in a w x h window. With `topleft` (the settlement screen) it is two rows, with
        its top left there. Otherwise it is one line, whose right edge and vertical centre are at `right_middle`, or at
        the upper left of the window without it. `dangerous` (see Player.is_time_scale_dangerous) paints the whole box
        red."""
        if topleft is not None:
            Clock._draw_two_rows(surface, fonts, date_time, time_scale, w, h, topleft, dangerous)
        else:
            Clock._draw_one_line(surface, fonts, date_time, time_scale, w, h, right_middle, dangerous)

    @staticmethod
    def _draw_one_line(surface: pygame.Surface, fonts: Any, date_time: datetime, time_scale: int, w: int, h: int,
                       right_middle: Optional[Tuple[int, int]], dangerous: bool) -> None:
        digit_font = fonts.get(max(12, int(h * 0.024)), bold=True)
        rate_font = fonts.get(max(10, int(h * 0.018)))
        ink, rate_color = Clock._inks(time_scale, dangerous)
        digits = Clock._ink(digit_font.render(Clock._format_ship_time(date_time), True, ink))
        rate = Clock._ink(rate_font.render(Clock._format_time_scale(time_scale), True, rate_color))

        pad = max(6, int(h * 0.011))  # beside the text, and above and below it
        gap = max(6, int(w * 0.004))  # between the time and the rate
        line = max(digits.get_height(), rate.get_height())
        panel = pygame.Rect(0, 0, digits.get_width() + gap + rate.get_width() + pad * 2, line + pad * 2)
        if right_middle is None:
            panel.topleft = (int(w * 0.015), int(h * 0.025))
        else:
            panel.midright = right_middle

        Clock._draw_box(surface, panel, dangerous)
        middle = panel.centery
        surface.blit(digits, digits.get_rect(midleft=(panel.left + pad, middle)))
        surface.blit(rate, rate.get_rect(midright=(panel.right - pad, middle)))

    @staticmethod
    def _draw_two_rows(surface: pygame.Surface, fonts: Any, date_time: datetime, time_scale: int, w: int, h: int,
                       topleft: Tuple[int, int], dangerous: bool) -> None:
        digit_font = fonts.get(max(12, int(h * 0.024)), bold=True)
        label_font = fonts.get(max(10, int(h * 0.018)))
        ink, rate_color = Clock._inks(time_scale, dangerous)
        digits = Clock._ink(digit_font.render(Clock._format_ship_time(date_time), True, ink))
        label = Clock._ink(label_font.render('PosDis', True, ink))
        rate = Clock._ink(label_font.render(Clock._format_time_scale(time_scale), True, rate_color))

        pad = max(6, int(h * 0.011))  # beside the text
        top_pad = max(8, int(h * 0.014))  # above the top line and below the digits, equal so the lines sit centred
        gap = max(8, int(w * 0.009))  # between the label and the rate
        line_gap = max(3, int(h * 0.006))  # between the two lines
        top_line = max(label.get_height(), rate.get_height())
        panel = pygame.Rect(
            0, 0,
            max(label.get_width() + gap + rate.get_width(), digits.get_width()) + pad * 2,
            top_line + line_gap + digits.get_height() + top_pad * 2,
        )
        panel.topleft = topleft

        Clock._draw_box(surface, panel, dangerous)
        # The label on the left and the rate on the right of the top line, the digits centred under them
        top_middle = panel.top + top_pad + top_line // 2
        surface.blit(label, label.get_rect(midleft=(panel.left + pad, top_middle)))
        surface.blit(rate, rate.get_rect(midright=(panel.right - pad, top_middle)))
        surface.blit(digits, digits.get_rect(midtop=(panel.centerx, panel.top + top_pad + top_line + line_gap)))

    @staticmethod
    def _inks(time_scale: int, dangerous: bool) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """The colour of the time and the colour of the rate: the rate is highlighted whenever time is compressed."""
        ink = DANGER_INK if dangerous else ACCENT
        rate_color = ink if dangerous or time_scale == Player.TIME_SCALE_MIN else AMBER
        return ink, rate_color

    @staticmethod
    def _draw_box(surface: pygame.Surface, panel: pygame.Rect, dangerous: bool) -> None:
        pygame.draw.rect(surface, HULL_DARK, panel.inflate(6, 6))
        pygame.draw.rect(surface, DANGER_BG if dangerous else READOUT_BG, panel)
        pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, panel, 2)

    @staticmethod
    def _ink(text: pygame.Surface) -> pygame.Surface:
        """The rendered text cut to its inked height, without the font's empty space above and below, so lines centre on
        it. The width is kept: the ink width changes with the glyphs (a '1' is narrower), and the box must not."""
        ink = text.get_bounding_rect()
        return text.subsurface(pygame.Rect(0, ink.top, text.get_width(), ink.height))

    @staticmethod
    def _format_ship_time(moment: datetime) -> str:
        """Format ISO 8601 layout without zero-padding the year, e.g. '700-01-01 00:00:00'."""
        return (f'{moment.year}-{moment.month:02d}-{moment.day:02d} '
                f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}')

    @staticmethod
    def _format_time_scale(scale: int) -> str:
        """Compression rate as a compact multiplier, e.g. 'x1' or 'x1 000 000'."""
        return f'x{scale:,}'.replace(',', ' ')
