"""Main console instrument panel orchestration."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from datetime import datetime
from ..Constants import (
    CONSOLE_TOP, CONSOLE_EDGE_COLOR, HULL_DARK, ACCENT, ACCENT_DIM, AMBER, ACCENT_DIM,
)
from .common import get_cockpit_background, draw_beveled_panel
from .compass import Compass
from .world_map import WorldMap
from .scanner import Scanner
from .cargo import Cargo
from .notification import Notification

if TYPE_CHECKING:
    from Player import Player


class Console:
    """Draw instrument panel below the windshield with all component displays."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, date_time: datetime) -> None:
        """Draw the main console with all instruments."""
        top = int(h * CONSOLE_TOP)
        height = h - top

        # Draw textured background
        background = get_cockpit_background(w, h)
        console_scaled = pygame.transform.scale(background, (w, height))
        surface.blit(console_scaled, (0, top))

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
        if player.is_bound:
            Console._draw_altitude_bar(surface, fonts, w, h, player, cluster_left, cluster_top, cluster_height)
        Console._draw_location_info(surface, fonts, w, h, player, cluster_left, cluster_top, cluster_height)

        bar_w = int(w * 0.028)
        compass_left_bound = cluster_left + bar_w + int(w * 0.15)
        mfd = pygame.Rect(0, 0, int(layout_w * 0.24), int(height * 0.56))
        mfd.centerx = layout_w // 2 + mfd.width // 3
        mfd.centery = top + int(height * 0.44)

        if player.is_bound:
            Compass.draw(surface, fonts, layout_w, h, player, cluster_top, cluster_height, compass_left_bound)
            draw_beveled_panel(surface, mfd, w=w, h=h)
            WorldMap.draw(surface, fonts, mfd, h, player, date_time)

        # Scanner
        Scanner.draw(surface, fonts, layout_w, h, player, cluster_top, cluster_height, mfd.right)

        # Cargo
        cargo_rect = pygame.Rect(0, 0, cargo_width, cluster_height)
        cargo_rect.top = cluster_top
        cargo_rect.right = w - cargo_margin
        Cargo.draw(surface, fonts, h, player, cargo_rect)

        # Notification bar
        light = max(4, int(height * 0.045))
        notification_height = int(height * 0.12)
        notification_y = h - light * 2 - notification_height
        Notification.draw(surface, fonts, w, notification_y, notification_height, player)

        # Indicator lights
        for i in range(10):
            x = int(w * 0.06 + i * light * 2.2)
            color = AMBER if i in (3, 7) else ACCENT_DIM
            pygame.draw.rect(surface, color, (x, h - light * 2, light, light))

    @staticmethod
    def _draw_altitude_bar(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        """Draw the altitude level indicator bar."""
        bar_w = int(w * 0.028)
        bar_h = cluster_height
        bar_rect = pygame.Rect(cluster_left, cluster_top, bar_w, bar_h)
        draw_beveled_panel(surface, bar_rect)

        import GameEnvironment as gem
        max_altitude = gem.current_environment.nearest_world.radius
        min_altitude = player.ship.HEIGHT
        altitude_range = max_altitude - min_altitude
        altitude_fraction = (player.position.y - min_altitude) / altitude_range
        altitude_fraction = min(1.0, max(0.0, altitude_fraction))

        fill_pad = 3
        filled = int((bar_h - fill_pad * 2) * altitude_fraction)
        pygame.draw.rect(
            surface, ACCENT,
            (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_w - fill_pad * 2, filled)
        )

        label_font = fonts.get(max(9, int(h * 0.017)))
        alt_label = label_font.render('ALT', True, ACCENT_DIM)
        surface.blit(alt_label, alt_label.get_rect(midtop=(cluster_left + bar_w // 2, cluster_top - 30)))

    @staticmethod
    def _draw_location_info(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        """Draw location information: world/system labels and position readouts."""
        top = int(h * CONSOLE_TOP)
        height = h - top

        label_font = fonts.get(max(9, int(h * 0.017)))
        world_font = fonts.get(max(12, int(h * 0.024)))

        bar_w = int(w * 0.028)
        coord_x = cluster_left + bar_w + int(w * 0.012)
        world_y = cluster_top - 40

        # World and system labels
        import GameEnvironment as gem
        stellar_system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        world_name = gem.current_environment.nearest_world.name
        star_name = stellar_system.name
        stellar_label = world_name + ", " + star_name + " System"
        world_text = world_font.render(stellar_label, True, ACCENT)
        surface.blit(world_text, (coord_x, world_y))

        entity_text = world_font.render(stellar_system.entity_name, True, ACCENT)
        entity_y = world_y + world_text.get_height() + int(height * 0.005)
        surface.blit(entity_text, (coord_x, entity_y))

        # Position readouts
        coord_y = entity_y + entity_text.get_height() + int(height * 0.04)
        line_spacing = int(height * 0.06)

        if player.is_bound:
            axis_lines = [
                ('Altitude', player.position.y, player.velocity.y),
                ('Longitude', player.position.x, player.velocity.x),
                ('Latitude', player.position.z, player.velocity.z),
            ]
        else:
            axis_lines = [
                ('x', player.position.x, player.velocity.x),
                ('y', player.position.y, player.velocity.y),
                ('z', player.position.z, player.velocity.z),
            ]

        for label, position, velocity in axis_lines:
            line_text = label_font.render(f'{label}: {int(position)} Δ{int(velocity)}', True, ACCENT)
            surface.blit(line_text, (coord_x, coord_y))
            coord_y += line_spacing

        yaw_text = label_font.render(f'Yaw: {int(player.yaw)}° Δ{int(player.velocity.yaw)}', True, ACCENT)
        surface.blit(yaw_text, (coord_x, coord_y))
