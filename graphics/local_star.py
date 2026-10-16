"""Local star (sun) rendering in the sky."""

from __future__ import annotations
from typing import TYPE_CHECKING
import math
import pygame
from .constants import (
    LOCAL_STAR_MIN_RADIUS_PX, LOCAL_STAR_MAX_RADIUS_PX, LOCAL_STAR_HALO_WIDTH_PX, LOCAL_STAR_HALO_ALPHA,
)

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class LocalStar:
    """Renders the parent star of the current world as seen from the cockpit."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        """Draw the local star at its true position in the sky.

        Drawn before the planet surface/horizon in the frame composition, so
        the opaque planet disc naturally occludes it when it's below the
        horizon or on the far side of the planet — no explicit day/night
        check needed here.
        """
        body = environment.nearest_body
        star = body.stellar_system.star

        from graphics.instruments.common import view_geometry, project_to_camera
        star_vector = ship.navigation.direction_to_star(body, environment.date_time)
        _, horizon_y, focal_length_px = view_geometry(h)
        projected = project_to_camera(ship, star_vector, w, horizon_y, focal_length_px)
        if projected is None:
            return
        screen_x, screen_y = projected

        distance = star_vector.length()
        angular_radius = math.atan(star.radius / distance)
        # Clamped: close to the star its disc fills the screen, and the glow's offscreen surface must stay small.
        star_radius_px = min(LOCAL_STAR_MAX_RADIUS_PX, max(LOCAL_STAR_MIN_RADIUS_PX, int(focal_length_px * angular_radius)))
        halo_radius_px = star_radius_px + LOCAL_STAR_HALO_WIDTH_PX

        # Halo needs per-pixel alpha, which the main world_surface doesn't have;
        # composite it on a small offscreen surface first, then blit that.
        badge_size = halo_radius_px * 2
        badge = pygame.Surface((badge_size, badge_size), pygame.SRCALPHA)
        badge_center = (halo_radius_px, halo_radius_px)
        pygame.draw.circle(badge, (*star.color, LOCAL_STAR_HALO_ALPHA), badge_center, halo_radius_px)
        pygame.draw.circle(badge, star.color, badge_center, star_radius_px)
        surface.blit(badge, (int(screen_x) - halo_radius_px, int(screen_y) - halo_radius_px))
