"""Local star (sun) rendering in the sky."""

from __future__ import annotations
from typing import TYPE_CHECKING
import math
import pygame
from .Constants import (
    CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, LOCAL_STAR_MIN_RADIUS_PX,
    LOCAL_STAR_HALO_WIDTH_PX, LOCAL_STAR_HALO_ALPHA,
)

from Galaxies.World import World

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment


class LocalStar:
    """Renders the parent star of the current world as seen from the cockpit."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """Draw the local star at its true position in the sky.

        Drawn before the planet surface/horizon in the frame composition, so
        the opaque planet disc naturally occludes it when it's below the
        horizon or on the far side of the planet — no explicit day/night
        check needed here.
        """
        world = environment.nearest_world
        star = world.parent_orbit.parent_stellar_system

        star_vector = player.direction_to_star(world, environment.date_time)
        right, cam_up, cam_forward = player.camera_components(star_vector)

        if cam_forward <= NEAR_CLIP:
            return

        view_h = int(h * CONSOLE_TOP)
        focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
        horizon_y = int(view_h * 0.5)

        screen_x = w / 2 + focal_length_px * right / cam_forward
        screen_y = horizon_y - focal_length_px * cam_up / cam_forward

        distance = math.sqrt(World._dot(star_vector, star_vector))
        angular_radius = math.atan(star.radius / distance)
        star_radius_px = max(LOCAL_STAR_MIN_RADIUS_PX, int(focal_length_px * angular_radius))
        halo_radius_px = star_radius_px + LOCAL_STAR_HALO_WIDTH_PX

        # Halo needs per-pixel alpha, which the main world_surface doesn't have;
        # composite it on a small offscreen surface first, then blit that.
        badge_size = halo_radius_px * 2
        badge = pygame.Surface((badge_size, badge_size), pygame.SRCALPHA)
        badge_center = (halo_radius_px, halo_radius_px)
        pygame.draw.circle(badge, (*star.color, LOCAL_STAR_HALO_ALPHA), badge_center, halo_radius_px)
        pygame.draw.circle(badge, star.color, badge_center, star_radius_px)
        surface.blit(badge, (int(screen_x) - halo_radius_px, int(screen_y) - halo_radius_px))
