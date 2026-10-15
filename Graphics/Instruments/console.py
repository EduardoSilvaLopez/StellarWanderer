"""Main console instrument panel orchestration."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from datetime import datetime
from ..constants import (
    CONSOLE_TOP, CONSOLE_EDGE_COLOR, HULL_DARK, ACCENT, ACCENT_DIM, AMBER, ACCENT_DIM,
)
from .common import get_console_background, draw_beveled_panel, bezel_depth
from units import format_compact_distance
from .compass import Compass
from .world_map import WorldMap
from .scanner import Scanner
from .cargo import Cargo
from .notification import notification_bar
from .altitude_meter import AltitudeMeter
from .binding_meter import BindingMeter
from .radar import Radar

if TYPE_CHECKING:
    from Spaceships.ship import Ship


class Console:
    """Draw instrument panel below the windshield with all component displays.

    The left cluster shows one of two meters, chosen by `Ship.is_bound`: the AltitudeMeter while bound (ALT), the
    BindingMeter while unbound (NEAREST). The location readouts show yaw, pitch and roll as angle plus rate (Δ,
    deg/s); see Player for their meaning."""

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

        # Left cluster: altitude bar and position coordinates
        cluster_left = int(w * 0.02)
        cluster_top = top + int(height * 0.24)
        cluster_height = int(height * 0.46)

        # Draw altitude bar and location info
        if ship.is_bound:
            AltitudeMeter.draw(surface, fonts, w, h, ship, cluster_left, cluster_top, cluster_height)
        else:
            BindingMeter.draw(surface, fonts, w, h, ship, cluster_left, cluster_top, cluster_height)
        Console._draw_location_info(surface, fonts, w, h, ship, cluster_left, cluster_top, cluster_height)

        bar_w = int(w * 0.028)
        compass_left_bound = cluster_left + bar_w + int(w * 0.15)
        mfd = pygame.Rect(0, 0, int(layout_w * 0.24), int(height * 0.56))
        mfd.centerx = layout_w // 2 + mfd.width // 3
        mfd.centery = top + int(height * 0.44)

        # The MFD frame (bound: world map, unbound: radar) gets the same bezel as every other instrument.
        # The footprint stays what the old thick textured bezel gave, so the freed space goes to the screen.
        depth = bezel_depth(h)
        old_depth = max(2, mfd.width // 24)
        screen = mfd.inflate(old_depth * 2, old_depth * 2).inflate(-depth * 2, -depth * 2)
        draw_beveled_panel(surface, screen, depth=depth)

        if ship.is_bound:
            Compass.draw(surface, fonts, layout_w, h, ship, cluster_top, cluster_height, compass_left_bound)
            WorldMap.draw(surface, fonts, screen, h, ship, date_time)
        else:
            Radar.draw(surface, fonts, h, screen, ship, date_time)

        # Scanner
        Scanner.draw(surface, fonts, layout_w, h, ship, cluster_top, cluster_height, mfd.right)

        # Cargo
        cargo_rect = pygame.Rect(0, 0, cargo_width, cluster_height)
        cargo_rect.top = cluster_top
        cargo_rect.right = w - cargo_margin
        Cargo.draw(surface, fonts, h, ship, cargo_rect)

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

    @staticmethod
    def _draw_location_info(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        """Draw location information: world/system labels and position readouts."""
        top = int(h * CONSOLE_TOP)
        height = h - top

        label_font = fonts.get(max(9, int(h * 0.017)))
        world_font = fonts.get(max(12, int(h * 0.024)))

        bar_w = int(w * 0.028)
        coord_x = cluster_left + bar_w + int(w * 0.03)
        world_y = cluster_top - 40

        # World and system labels
        import game_environment as gem
        stellar_system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        world_name = gem.current_environment.nearest_world.name
        star_name = stellar_system.name
        stellar_label = world_name + ", " + star_name + " System"
        world_text = world_font.render(stellar_label, True, ACCENT)
        surface.blit(world_text, (coord_x, world_y))

        # Position readouts
        coord_y = world_y + world_text.get_height() + int(height * 0.08)
        line_spacing = int(height * 0.06)

        if ship.is_bound:
            axis_lines = [
                ('Altitude', ship.position.y, ship.velocity.y),
                ('Longitude', ship.position.x, ship.velocity.x),
                ('Latitude', ship.position.z, ship.velocity.z),
            ]
        else:
            axis_lines = [
                ('x', ship.position.x, ship.velocity.x),
                ('y', ship.position.y, ship.velocity.y),
                ('z', ship.position.z, ship.velocity.z),
            ]

        for label, position, velocity in axis_lines:
            if ship.is_bound:
                text = f'{label}: {int(position)} Δ {int(velocity)}'
            else:
                text = f'{label}: {format_compact_distance(position)}  Δ {int(velocity)}'
            line_text = label_font.render(text, True, ACCENT)
            surface.blit(line_text, (coord_x, coord_y))
            coord_y += line_spacing

        world = gem.current_environment.nearest_world
        date_time = gem.current_environment.date_time
        attitude_lines = (
            f'Yaw: {int(ship.attitude.yaw)}° Δ {int(ship.attitude.yaw_rate)}',
            f'Pitch: {int(ship.navigation.pitch_angle(world, date_time))}° Δ {int(ship.attitude.pitch_rate)}',
            f'Roll: {int(ship.navigation.roll_angle(world, date_time))}° Δ {int(ship.attitude.roll_rate)}',
        )
        for text in attitude_lines:
            surface.blit(label_font.render(text, True, ACCENT), (coord_x, coord_y))
            coord_y += line_spacing
