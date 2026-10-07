"""Political entity information display in the top-left corner."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from Player import Player


class PoliticalInfo:
    """Display political entity name (above) and icon (below) in the top-left corner."""

    PADDING = 20  # pixels from screen edges
    ICON_SIZE = 120  # icon size in pixels
    MAX_FONT_SIZE = 28
    GAP = 8  # pixels between name and icon

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player) -> None:
        """Draw political entity info in the top-left corner."""
        import GameEnvironment as gem

        stellar_system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        entity = stellar_system.political_entity

        if entity is None:
            return

        x = PoliticalInfo.PADDING
        y = PoliticalInfo.PADDING

        text_surface = fonts.render_to_fit(entity.name, entity.color, PoliticalInfo.ICON_SIZE, PoliticalInfo.MAX_FONT_SIZE)
        text_x = x + (PoliticalInfo.ICON_SIZE - text_surface.get_width()) // 2
        surface.blit(text_surface, (text_x, y))

        if entity.icon is not None:
            icon_y = y + text_surface.get_height() + PoliticalInfo.GAP
            scaled_icon = pygame.transform.scale(entity.icon, (PoliticalInfo.ICON_SIZE, PoliticalInfo.ICON_SIZE))
            surface.blit(scaled_icon, (x, icon_y))
