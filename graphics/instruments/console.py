"""Main console instrument panel orchestration."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from datetime import datetime
from ..constants import (
    CONSOLE_TOP, CONSOLE_EDGE_COLOR, HULL_DARK, ACCENT_DIM, AMBER,
)
from .common import get_console_background, draw_beveled_panel, bezel_depth, panel_box_top
from .compass import Compass
from .location_info import LocationInfo
from .world_map import WorldMap
from .scanner import Scanner
from .cargo import Cargo
from .resource_bars import ResourceBars
from .notification import notification_bar
from .altitude_meter import AltitudeMeter
from .proximity_meter import ProximityMeter
from .radar import Radar

if TYPE_CHECKING:
    from spaceships.ship import Ship


class Console:
    """Draw instrument panel below the windshield with all component displays.

    The left cluster shows one of two meters, chosen by `Ship.is_bound`: the AltitudeMeter while bound (ALT), the
    ProximityMeter while unbound (FIXED or TARGET), whose bar and indicators are columns the height of the map's screen.
    The readouts (coordinates, attitude, speed) are beside the meter: bound beside the altitude bar, unbound between the
    proximity bar and the map. The name of the reference body is drawn in the top bar by Cockpit
    (LocationInfo.draw_name). Pitch and roll use the same body as the position box, which is the fixed body while fixed,
    else the star. Yaw, pitch and roll are shown as angle plus rate (Δ, deg/s); see Player for their meaning."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, date_time: datetime) -> None:
        """Draw the main console with all instruments."""
        top = int(h * CONSOLE_TOP)
        height = h - top

        # Draw textured background (scaled once and cached, not every frame)
        surface.blit(get_console_background(w, h, height), (0, top))

        pygame.draw.line(surface, CONSOLE_EDGE_COLOR, (0, top), (w, top), 2)
        pygame.draw.rect(surface, HULL_DARK, (0, top + 2, w, max(3, int(height * 0.06))))

        cargo_width = int(w * 0.16)
        cargo_gap = int(w * 0.02)
        cargo_margin = int(w * 0.03)
        layout_w = w - cargo_width - cargo_gap - cargo_margin

        # Resource bars sit between the scanner and the cargo hold. The compass and the map move left to make room:
        # the compass by half the bars' width, the map by less, so the compass dial clears the map's frame. The
        # scanner is laid out to the left of the bars.
        bars_w = int(w * 0.13)
        bars_left = layout_w - bars_w
        shift = bars_w // 2
        map_shift = int(w * 0.047)

        # Left cluster: altitude bar (bound) or proximity columns (unbound), and the readouts
        cluster_left = int(w * 0.02)
        cluster_top = top + int(height * 0.24)
        cluster_height = int(height * 0.46)
        bar_w = int(w * 0.028)
        line_spacing = int(height * 0.06)

        compass_left_bound = cluster_left + bar_w + int(w * 0.15) - shift // 2
        mfd = pygame.Rect(0, 0, int(layout_w * 0.24), int(height * 0.56))
        mfd.centerx = layout_w // 2 + mfd.width // 3 - map_shift
        mfd.centery = top + int(height * 0.44)

        # The MFD frame (bound: world map, unbound: radar) gets the same bezel as every other instrument.
        # The footprint stays what the old thick textured bezel gave, so the freed space goes to the screen.
        depth = bezel_depth(h)
        old_depth = max(2, mfd.width // 24)
        screen = mfd.inflate(old_depth * 2, old_depth * 2).inflate(-depth * 2, -depth * 2)
        draw_beveled_panel(surface, screen, depth=depth)

        # Left cluster, as tall as the map's screen. Bound: the altitude bar, with the readouts beside it. Unbound: the
        # target's indicators, then the proximity bar, then the readouts between the bar and the map.
        if ship.is_bound:
            AltitudeMeter.draw(surface, fonts, w, h, ship, cluster_left, cluster_top, cluster_height)
            LocationInfo.draw_readouts(surface, fonts, h, ship, cluster_left + bar_w + int(w * 0.03), cluster_top - 10,
                                       line_spacing)
        else:
            indicators_w = int(w * 0.115)
            indicators_rect = pygame.Rect(cluster_left, screen.top, indicators_w, screen.height)
            bar_rect = pygame.Rect(cluster_left + indicators_w + int(w * 0.01), screen.top, bar_w, screen.height)
            ProximityMeter.draw_bar(surface, h, ship, bar_rect)
            ProximityMeter.draw_indicators(surface, fonts, h, ship, indicators_rect)
            readouts_left = bar_rect.right + int(w * 0.015)
            LocationInfo.draw_readouts(surface, fonts, h, ship, readouts_left, screen.top + 4, line_spacing)

        if ship.is_bound:
            Compass.draw(surface, fonts, layout_w, h, ship, cluster_top, cluster_height, compass_left_bound)
            WorldMap.draw(surface, fonts, screen, h, ship, date_time)
        else:
            Radar.draw(surface, screen, ship, date_time)

        # The scanner and cargo titles sit on the top of the map's screen; their boxes, the resource bars and the
        # cargo hold all start below the titles and end at the bottom of the cluster.
        title_font = fonts.get(max(9, int(h * 0.017)))
        box_top = panel_box_top(title_font, screen.top)
        panel_bottom = cluster_top + cluster_height

        # Scanner
        Scanner.draw(surface, fonts, bars_left, h, ship, screen.top, screen.bottom, mfd.right)

        # Resource bars
        bars_rect = pygame.Rect(bars_left, box_top, bars_w, panel_bottom - box_top)
        ResourceBars.draw(surface, fonts, h, ship, bars_rect)

        # Cargo
        cargo_rect = pygame.Rect(0, 0, cargo_width, screen.bottom - box_top)
        cargo_rect.top = box_top
        cargo_rect.right = w - cargo_margin
        Cargo.draw(surface, fonts, h, ship, cargo_rect, screen.top)

        # Notification bar
        light = max(4, int(height * 0.045))
        notification_height = int(height * 0.12)
        notification_y = h - light * 2 - notification_height
        notification_bar.draw(surface, fonts, w, notification_y, notification_height, ship)

        # Indicator lights
        for i in range(10):
            x = int(w * 0.06 + i * light * 2.2)
            color = AMBER if i in (3, 7) else ACCENT_DIM
            pygame.draw.rect(surface, color, (x, h - light * 2, light, light))

