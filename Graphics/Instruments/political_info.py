"""Political entity information display in the top-left corner."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..Constants import CANOPY_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET, CONSOLE_TOP

if TYPE_CHECKING:
    from Player import Player


class PoliticalInfo:
    """Display political entity name (above) and icon (below) in the top-left hull area,
    sized as large as the solid hull space allows without crossing into the windshield glass."""

    PADDING_X = 20  # pixels from the left edge
    PADDING_Y = 16  # pixels below the canopy's top rail
    EDGE_MARGIN = 12  # pixels of clearance kept before the A-pillar's inner edge
    GAP = 8  # pixels between name and icon
    MAX_FONT_SIZE = 72
    MIN_ICON_SIZE = 40
    MAX_ICON_SIZE = 260
    ICON_STEP = 4

    @staticmethod
    def _hull_edge_x(y: float, w: int, h: int) -> float:
        """X position of the left A-pillar's inner edge at height y: the boundary
        between solid hull (left) and windshield glass (right). Mirrors the pillar
        geometry in Canopy.draw."""
        top = h * CANOPY_TOP
        bottom = h * CONSOLE_TOP
        top_inset = w * CANOPY_TOP_INSET
        bottom_inset = w * CANOPY_BOTTOM_INSET
        if y <= top:
            return top_inset
        fraction = min(1.0, (y - top) / (bottom - top))
        return top_inset + (bottom_inset - top_inset) * fraction

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player) -> None:
        """Draw political entity info in the top-left hull area, under the canopy's top rail."""
        import GameEnvironment as gem

        stellar_system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        entity = stellar_system.political_entity

        if entity is None:
            return

        x = PoliticalInfo.PADDING_X
        y = int(h * CANOPY_TOP) + PoliticalInfo.PADDING_Y

        # Name: as large as fits the hull width at the top of the text (the pillar
        # only narrows slightly over the text's own height, so this is a safe bound).
        max_text_width = PoliticalInfo._hull_edge_x(y, w, h) - x - PoliticalInfo.EDGE_MARGIN
        text_surface = fonts.render_to_fit(entity.name, entity.color, max(1, int(max_text_width)), PoliticalInfo.MAX_FONT_SIZE)
        surface.blit(text_surface, (x, y))

        if entity.icon is None:
            return

        # Icon: the largest square that still fits the hull width at its own
        # bottom edge, the narrowest point of its vertical span.
        icon_y = y + text_surface.get_height() + PoliticalInfo.GAP
        icon_size = PoliticalInfo.MAX_ICON_SIZE
        while icon_size > PoliticalInfo.MIN_ICON_SIZE:
            available = PoliticalInfo._hull_edge_x(icon_y + icon_size, w, h) - x - PoliticalInfo.EDGE_MARGIN
            if icon_size <= available:
                break
            icon_size -= PoliticalInfo.ICON_STEP

        scaled_icon = pygame.transform.scale(entity.icon, (icon_size, icon_size))
        surface.blit(scaled_icon, (x, icon_y))
