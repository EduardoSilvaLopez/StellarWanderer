"""Political entity information display in the top-left corner."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from Player import Player


class PoliticalInfo:
    """Display political entity name and icon in the top-left corner with dynamic font sizing."""

    PADDING = 20  # pixels from screen edges
    ICON_MAX_SIZE = 120  # maximum icon size in pixels
    MIN_FONT_SIZE = 14
    MAX_FONT_SIZE = 36

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player) -> None:
        """Draw political entity info in the top-left corner."""
        import GameEnvironment as gem

        stellar_system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        entity = stellar_system.political_entity

        if entity is None or entity.name is None:
            return

        # Calculate layout
        icon_size = PoliticalInfo.ICON_MAX_SIZE
        x_base = PoliticalInfo.PADDING
        y_base = PoliticalInfo.PADDING

        # Start with max font size and reduce if needed
        font_size = PoliticalInfo.MAX_FONT_SIZE
        text_surface = None

        # Find appropriate font size that fits within reasonable bounds
        # Constrain text to be narrower than icon for visual balance
        max_text_width = icon_size + 40

        while font_size >= PoliticalInfo.MIN_FONT_SIZE:
            font = fonts.get(font_size)
            text_surface = font.render(entity.name, True, entity.color)

            if text_surface.get_width() <= max_text_width:
                break

            font_size -= 1

        # Ensure we have a valid text surface
        if text_surface is None:
            font = fonts.get(PoliticalInfo.MIN_FONT_SIZE)
            text_surface = font.render(entity.name, True, entity.color)

        # Draw text on top, centered (but don't let it go negative)
        text_x = max(x_base, x_base + (icon_size - text_surface.get_width()) // 2)
        surface.blit(text_surface, (text_x, y_base))

        # Draw icon below text
        if entity.icon is not None:
            scaled_icon = pygame.transform.scale(entity.icon, (icon_size, icon_size))
            icon_y = y_base + text_surface.get_height() + 10
            surface.blit(scaled_icon, (x_base, icon_y))
