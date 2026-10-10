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
        player_x, player_y = WorldMap._map_point(player.position.x, player.position.z, radius, inner_area)

        # Outposts of this world (planets only; moons have none), as small white dots with their names.
        WorldMap._draw_outposts(surface, fonts, h, world, radius, inner_area)

        # Draw player position as a brilliant dot
        dot_radius = max(2, int(h * 0.003))
        pygame.draw.circle(surface, ACCENT, (player_x, player_y), dot_radius)
        pygame.draw.circle(surface, (255, 255, 255), (player_x, player_y), max(1, dot_radius - 1))

    @staticmethod
    def _map_point(lon: float, lat: float, radius: float, area: pygame.Rect) -> tuple:
        """Pixel position of a surface point (longitude, latitude in metres) inside the map area."""
        lon_min = -math.pi * radius
        lon_max = math.pi * radius
        lat_min = -math.pi * radius / 2
        lat_max = math.pi * radius / 2
        # Normalize to [0, 1], clamped in case of floating point errors.
        norm_lon = max(0, min(1, (lon - lon_min) / (lon_max - lon_min)))
        norm_lat = max(0, min(1, (lat - lat_min) / (lat_max - lat_min)))
        # Top of the map is the maximum latitude.
        return int(area.left + norm_lon * area.width), int(area.top + (1 - norm_lat) * area.height)

    @staticmethod
    def _draw_outposts(surface: pygame.Surface, fonts: Any, h: int, world, radius: float, area: pygame.Rect) -> None:
        """White dot per outpost, with its name beside it. The label goes towards the middle of the map
        (left when the dot is in the right half, above when in the lower half), and is kept inside the map."""
        if world.parent_planet is not None or not world.outposts:
            return
        font = fonts.get(max(9, int(h * 0.014)))
        gap_x, gap_y = 6, 4
        centre_x, centre_y = area.centerx, area.centery
        for outpost in world.outposts.values():
            x, y = WorldMap._map_point(outpost.longitude, outpost.latitude, radius, area)
            text = font.render(outpost.name, True, (255, 255, 255))
            rect = text.get_rect()
            if x > centre_x:
                rect.right = x - gap_x     # right half: label on the left
            else:
                rect.left = x + gap_x      # left half: label on the right
            if y > centre_y:
                rect.bottom = y - gap_y    # lower half: label above
            else:
                rect.top = y + gap_y       # upper half: label below
            rect.clamp_ip(area)
            surface.blit(text, rect)
            pygame.draw.circle(surface, (255, 255, 255), (x, y), 2)

