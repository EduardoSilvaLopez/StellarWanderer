"""Planets and moons other than the nearest world, drawn as discs in the sky."""

from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING
import math
import pygame
from .Constants import SKY_WORLD_COLOR, SKY_WORLD_MIN_RADIUS_PX, SKY_WORLD_MAX_RADIUS_PX

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment


class OtherWorlds:
    """Renders every world of the stellar system except the nearest one."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player,
             behind_star: bool) -> None:
        """Draw the other worlds at their true direction, bound or unbound, farthest first.

        Called twice per frame around LocalStar.draw: first with behind_star=True (worlds
        farther than the star, which the star then covers), then with behind_star=False
        (worlds nearer than the star). The nearest world's opaque disc is drawn afterwards,
        so it naturally hides the worlds below its horizon or behind it.
        """
        from Graphics.Instruments.common import view_geometry, project_to_camera
        _, horizon_y, focal_length_px = view_geometry(h)
        star_distance = player.direction_to_star(environment.nearest_world, environment.date_time).length()

        visible: List[Tuple[float, int, float, float]] = []
        for world in environment.nearest_system.get_all_worlds():
            if world is environment.nearest_world:
                continue
            vector = player.direction_to_world(world, environment.date_time)
            distance = vector.length()
            if distance <= world.radius or (distance > star_distance) != behind_star:
                continue
            projected = project_to_camera(player, vector, w, horizon_y, focal_length_px)
            if projected is None:
                continue
            angular_radius = math.asin(world.radius / distance)
            radius_px = int(focal_length_px * math.tan(angular_radius))
            radius_px = max(SKY_WORLD_MIN_RADIUS_PX, min(SKY_WORLD_MAX_RADIUS_PX, radius_px))
            visible.append((distance, radius_px, projected[0], projected[1]))

        for _, radius_px, screen_x, screen_y in sorted(visible, reverse=True):
            pygame.draw.circle(surface, SKY_WORLD_COLOR, (int(screen_x), int(screen_y)), radius_px)
