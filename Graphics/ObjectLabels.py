"""Labels for visible objects (star and world) showing name and compact distance."""

from __future__ import annotations
from typing import TYPE_CHECKING
import math
import pygame
from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, ACCENT
from Galaxies.World import World

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment


class ObjectLabels:
    """Render name and distance labels for visible objects (star and nearest world)."""

    LABEL_OFFSET_X = 20  # pixels right of object center
    LABEL_OFFSET_Y = -20  # pixels above object center

    @staticmethod
    def draw(surface: pygame.Surface, fonts, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """Draw labels for visible objects while unbound."""
        if player.is_bound:
            return

        from Graphics.Instruments.common import format_compact_distance
        view_h = int(h * CONSOLE_TOP)
        focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
        horizon_y = int(view_h * 0.5)
        world = environment.nearest_world
        star = world.parent_orbit.parent_stellar_system

        label_font = fonts.get(max(9, int(h * 0.017)))

        # Draw star label
        star_vector = player.direction_to_star(world, environment.date_time)
        right, cam_up, cam_forward = player.camera_components(star_vector)
        if cam_forward > NEAR_CLIP:
            screen_x = w / 2 + focal_length_px * right / cam_forward
            screen_y = horizon_y - focal_length_px * cam_up / cam_forward
            distance = math.hypot(*star_vector)
            ObjectLabels._draw_label(
                surface, label_font, star.name, format_compact_distance(distance),
                int(screen_x), int(screen_y)
            )

        # Draw world label
        world_vector = (
            world.calculate_stellar_position(environment.date_time)[0] - player.position.x,
            world.calculate_stellar_position(environment.date_time)[1] - player.position.y,
            world.calculate_stellar_position(environment.date_time)[2] - player.position.z,
        )
        right, cam_up, cam_forward = player.camera_components(world_vector)
        if cam_forward > NEAR_CLIP:
            screen_x = w / 2 + focal_length_px * right / cam_forward
            screen_y = horizon_y - focal_length_px * cam_up / cam_forward
            distance = math.hypot(*world_vector)
            ObjectLabels._draw_label(
                surface, label_font, world.name, format_compact_distance(distance),
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
