"""Labels for visible objects (star and all worlds) showing name and compact distance."""

from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from .Constants import ACCENT

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment


class ObjectLabels:
    """Render name and distance labels for visible objects (star and all worlds in the stellar system)."""

    LABEL_OFFSET_X = 20  # pixels right of object center
    LABEL_OFFSET_Y = -20  # pixels above object center

    @staticmethod
    def draw(surface: pygame.Surface, fonts, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """Draw labels for visible objects while unbound."""
        if player.is_bound:
            return

        from Graphics.Instruments.common import format_compact_distance, view_geometry, project_to_camera
        _, horizon_y, focal_length_px = view_geometry(h)
        world = environment.nearest_world
        star = world.parent_orbit.parent_stellar_system

        label_font = fonts.get(max(9, int(h * 0.017)))

        # Draw star label
        star_vector = player.direction_to_star(world, environment.date_time)
        projected = project_to_camera(player, star_vector, w, horizon_y, focal_length_px)
        if projected is not None:
            screen_x, screen_y = projected
            ObjectLabels._draw_label(
                surface, label_font, star.name, format_compact_distance(star_vector.length()),
                int(screen_x), int(screen_y)
            )

        # Draw labels for all worlds in the stellar system
        for orbit in star.orbits:
            for world_obj in orbit.worlds:
                world_vector = world_obj.calculate_stellar_position(environment.date_time) - player.position.as_vector()
                projected = project_to_camera(player, world_vector, w, horizon_y, focal_length_px)
                if projected is not None:
                    screen_x, screen_y = projected
                    ObjectLabels._draw_label(
                        surface, label_font, world_obj.name, format_compact_distance(world_vector.length()),
                        int(screen_x), int(screen_y)
                    )

    @staticmethod
    def _draw_label(surface: pygame.Surface, font, name: str, distance: str, center_x: int, center_y: int) -> None:
        """Draw a single object label at the given screen center."""
        text = f'{name} {distance}'
        label_surf = font.render(text, True, ACCENT)
        rect = label_surf.get_rect(
            topleft=(center_x + ObjectLabels.LABEL_OFFSET_X, center_y + ObjectLabels.LABEL_OFFSET_Y)
        )
        surface.blit(label_surf, rect)
