"""Cockpit instrumentation: canopy, console, and clock."""

import math
import pygame
from .Constants import (
    CONSOLE_TOP, CANOPY_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET,
    HULL, HULL_DARK, HULL_EDGE, STRUT, CONSOLE, CONSOLE_EDGE,
    ACCENT, ACCENT_DIM, AMBER, READOUT_BG
)


class Cockpit:
    """Renders cockpit instrumentation: hull, console, and clock."""

    @staticmethod
    def draw(surface, fonts, w, h, player, date_time, time_scale):
        """Draw all cockpit elements.

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            w: Window width
            h: Window height
            player: Player object
            date_time: Player's ship time
            time_scale: Time acceleration factor
        """
        Cockpit.draw_canopy(surface, w, h)
        Cockpit.draw_console(surface, fonts, w, h, player)
        Cockpit.draw_ship_clock(surface, fonts, date_time, time_scale, w, h)

    @staticmethod
    def draw_canopy(surface, w, h):
        """Draw hull frame: top rail, two A-pillars, and struts between panes."""
        top = int(h * CANOPY_TOP)
        bottom = int(h * CONSOLE_TOP)
        top_inset = w * CANOPY_TOP_INSET
        bottom_inset = w * CANOPY_BOTTOM_INSET

        # Top rail.
        pygame.draw.rect(surface, HULL, (0, 0, w, top))
        pygame.draw.line(surface, HULL_EDGE, (0, top - 1), (w, top - 1), 2)

        # A-pillars, angling inward as they rise.
        left = [(0, 0), (top_inset, top), (bottom_inset, bottom), (0, bottom)]
        right = [(w, 0), (w - top_inset, top), (w - bottom_inset, bottom), (w, bottom)]
        for pillar in (left, right):
            points = [(int(x), int(y)) for x, y in pillar]
            pygame.draw.polygon(surface, HULL, points)
            pygame.draw.lines(surface, HULL_EDGE, False, points[1:3], 2)

        # Two vertical struts splitting the windshield into three panes.
        for frac in (1 / 3, 2 / 3):
            half = max(2, int(w * 0.004))
            x_top = top_inset + (w - 2 * top_inset) * frac
            x_bottom = bottom_inset + (w - 2 * bottom_inset) * frac
            strut = [
                (int(x_top - half), top), (int(x_top + half), top),
                (int(x_bottom + half), bottom), (int(x_bottom - half), bottom),
            ]
            pygame.draw.polygon(surface, STRUT, strut)
            pygame.draw.line(surface, HULL_EDGE, strut[0], strut[3], 1)

    @staticmethod
    def draw_console(surface, fonts, w, h, player):
        """Draw instrument panel below the windshield."""
        top = int(h * CONSOLE_TOP)
        height = h - top

        pygame.draw.rect(surface, CONSOLE, (0, top, w, height))
        pygame.draw.line(surface, CONSOLE_EDGE, (0, top), (w, top), 2)
        # Shadowed lip under the windshield, so the console reads as tilted away.
        pygame.draw.rect(surface, HULL_DARK, (0, top + 2, w, max(3, int(height * 0.06))))

        label_font = fonts.get(max(9, int(h * 0.017)))

        # Left cluster: altitude bar and position coordinates.
        cluster_left = int(w * 0.02)
        cluster_top = top + int(height * 0.24)
        cluster_height = int(height * 0.46)

        # Altitude bar (vertical level indicator)
        bar_w = int(w * 0.028)
        bar_h = cluster_height
        pygame.draw.rect(surface, READOUT_BG, (cluster_left, cluster_top, bar_w, bar_h))

        # Calculate altitude fraction (0-1) based on player position
        from Player import Player
        max_altitude = Player.MAX_ALTITUDE
        min_altitude = Player.MIN_ALTITUDE
        altitude_range = max_altitude - min_altitude
        altitude_fraction = (player.position.y - min_altitude) / altitude_range
        altitude_fraction = min(1.0, max(0.0, altitude_fraction))

        filled = int(bar_h * altitude_fraction)
        pygame.draw.rect(
            surface, ACCENT, (cluster_left, cluster_top + bar_h - filled, bar_w, filled)
        )
        pygame.draw.rect(surface, CONSOLE_EDGE, (cluster_left, cluster_top, bar_w, bar_h), 2)

        # Altitude label
        alt_label = label_font.render('ALT', True, ACCENT_DIM)
        surface.blit(alt_label, alt_label.get_rect(midtop=(cluster_left + bar_w // 2, cluster_top - 12)))

        # Position coordinates (X and Z) displayed as numbers
        coord_x = cluster_left + bar_w + int(w * 0.035)
        coord_y = cluster_top + int(height * 0.05)

        x_text = label_font.render(f'X: {int(player.position.x)}', True, ACCENT)
        z_text = label_font.render(f'Z: {int(player.position.z)}', True, ACCENT)

        surface.blit(x_text, (coord_x, coord_y))
        surface.blit(z_text, (coord_x, coord_y + int(height * 0.06)))

        # Centre multi-function display.
        mfd = pygame.Rect(0, 0, int(w * 0.24), int(height * 0.56))
        mfd.center = (w // 2, top + int(height * 0.44))
        pygame.draw.rect(surface, READOUT_BG, mfd)
        pygame.draw.rect(surface, CONSOLE_EDGE, mfd, 2)

        nav = fonts.render_to_fit(
            'NAV — NO CONTACT', ACCENT, mfd.width - 12, max(9, int(h * 0.017))
        )
        surface.blit(nav, nav.get_rect(midtop=(mfd.centerx, mfd.top + 5)))

        # Grid sits below the header band so the two never collide.
        grid = mfd.inflate(-8, 0)
        grid.top = mfd.top + nav.get_height() + 9
        grid.height = mfd.bottom - 5 - grid.top
        pygame.draw.line(surface, CONSOLE_EDGE, (grid.left, grid.top - 4),
                         (grid.right, grid.top - 4), 1)
        for i in range(1, 5):
            y = grid.top + grid.height * i // 5
            pygame.draw.line(surface, ACCENT_DIM, (grid.left, y), (grid.right, y), 1)
        for i in range(1, 6):
            x = grid.left + grid.width * i // 6
            pygame.draw.line(surface, ACCENT_DIM, (x, grid.top), (x, grid.bottom), 1)

        # Right cluster: vertical level bars.
        bar_w = int(w * 0.018)
        bar_h = int(height * 0.46)
        bar_top = top + int(height * 0.24)
        for i, level in enumerate((0.72, 0.51, 0.88, 0.34)):
            x = int(w * 0.70 + i * bar_w * 2.1)
            pygame.draw.rect(surface, READOUT_BG, (x, bar_top, bar_w, bar_h))
            filled = int(bar_h * level)
            pygame.draw.rect(
                surface, ACCENT, (x, bar_top + bar_h - filled, bar_w, filled)
            )
            pygame.draw.rect(surface, CONSOLE_EDGE, (x, bar_top, bar_w, bar_h), 1)

        # Indicator lights along the bottom.
        light = max(4, int(height * 0.045))
        for i in range(10):
            x = int(w * 0.06 + i * light * 2.2)
            color = AMBER if i in (3, 7) else ACCENT_DIM
            pygame.draw.rect(surface, color, (x, h - light * 2, light, light))

    @staticmethod
    def draw_ship_clock(surface, fonts, date_time, time_scale, w, h):
        """Draw clock panel mounted on the upper right of the cockpit."""
        digit_font = fonts.get(max(14, int(h * 0.030)), bold=True)
        label_font = fonts.get(max(9, int(h * 0.016)))

        # Format the time display
        text = Cockpit.format_ship_time(date_time)

        digits = digit_font.render(text, True, ACCENT)
        label = label_font.render('SHIP TIME', True, ACCENT_DIM)

        # Highlight the rate whenever time is compressed
        from Player import Player
        rate_color = ACCENT_DIM if time_scale == Player.TIME_SCALE_MIN else AMBER
        rate = label_font.render(Cockpit.format_time_scale(time_scale), True, rate_color)

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
        pygame.draw.rect(surface, CONSOLE_EDGE, panel, 2)

        surface.blit(label, (panel.left + pad, panel.top + pad))
        surface.blit(rate, rate.get_rect(topright=(panel.right - pad, panel.top + pad)))
        surface.blit(digits, (panel.left + pad, panel.top + pad + label.get_height()))

    @staticmethod
    def format_ship_time(moment):
        """Format ISO 8601 layout without zero-padding the year, e.g. '500-01-01 00:00:00'."""
        return (f'{moment.year}-{moment.month:02d}-{moment.day:02d} '
                f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}')

    @staticmethod
    def format_time_scale(scale):
        """Compression rate as a compact multiplier, e.g. 'x1' or 'x1 000 000'."""
        return f'x{scale:,}'.replace(',', ' ')
