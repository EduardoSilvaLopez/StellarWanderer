"""World map display (multi-function display)."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import math
import pygame
from datetime import datetime
from ..Constants import ACCENT, ACCENT_DIM

if TYPE_CHECKING:
    from Player import Player


class WorldMap:
    """Draw a world map showing player position in the MFD (multi-function display)."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, mfd: pygame.Rect, h: int, player: Player, date_time: datetime) -> None:
        """Draw the world map.

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            mfd: Rectangle for the multi-function display
            h: Window height
            player: Player object with position and world info
            date_time: Current in-game date/time, for local year/day progress
        """
        import GameEnvironment as gem
        world = gem.current_environment.nearest_world
        radius = world.radius

        # Header with world name, flanked by local year/day progress.
        world_name_text = fonts.render_to_fit(
            world.name, ACCENT, mfd.width - 12, max(9, int(h * 0.017))
        )
        name_rect = world_name_text.get_rect(midtop=(mfd.centerx, mfd.top + 5))
        surface.blit(world_name_text, name_rect)

        side_font_size = max(8, int(h * 0.013))
        side_gap = max(6, int(h * 0.008))
        year_percent = int(100 * world.local_year_fraction(date_time))
        day_percent = int(100 * world.local_day_fraction(date_time))

        year_text = fonts.render_to_fit(
            f'Local Y: {year_percent}%', ACCENT_DIM, max(20, name_rect.left - mfd.left - side_gap), side_font_size
        )
        surface.blit(year_text, year_text.get_rect(midleft=(mfd.left + side_gap, name_rect.centery)))

        day_text = fonts.render_to_fit(
            f'Local D: {day_percent}%', ACCENT_DIM, max(20, mfd.right - name_rect.right - side_gap), side_font_size
        )
        surface.blit(day_text, day_text.get_rect(midright=(mfd.right - side_gap, name_rect.centery)))

        # Map area below header — sits on the beveled mfd screen drawn by the caller.
        map_area = mfd.inflate(-8, 0)
        map_area.top = mfd.top + world_name_text.get_height() + 9
        map_area.height = mfd.bottom - 5 - map_area.top

        # World bounds rectangle (normalized to map area)
        # Longitude: -π*radius to +π*radius (horizontal)
        # Latitude: -π*radius/2 to +π*radius/2 (vertical)
        map_padding = 4
        inner_area = map_area.inflate(-map_padding * 2, -map_padding * 2)

        # Draw world rectangle
        pygame.draw.rect(surface, ACCENT_DIM, inner_area, 1)

        # Calculate player position as normalized coordinates within map
        lon_min = -math.pi * radius
        lon_max = math.pi * radius
        lat_min = -math.pi * radius / 2
        lat_max = math.pi * radius / 2

        # Normalize player position to [0, 1]
        norm_lon = (player.position.x - lon_min) / (lon_max - lon_min)
        norm_lat = (player.position.z - lat_min) / (lat_max - lat_min)

        # Clamp to [0, 1] in case of floating point errors
        norm_lon = max(0, min(1, norm_lon))
        norm_lat = max(0, min(1, norm_lat))

        # Convert to pixel coordinates within inner_area
        player_x = int(inner_area.left + norm_lon * inner_area.width)
        player_y = int(inner_area.top + (1 - norm_lat) * inner_area.height)  # Flip Y (top=max latitude)

        # Draw player position as a brilliant dot
        dot_radius = max(2, int(h * 0.003))
        pygame.draw.circle(surface, ACCENT, (player_x, player_y), dot_radius)
        pygame.draw.circle(surface, (255, 255, 255), (player_x, player_y), max(1, dot_radius - 1))
