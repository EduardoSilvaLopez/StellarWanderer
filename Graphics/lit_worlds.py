"""Worlds (planets and moons) drawn as spheres lit by their star."""

from __future__ import annotations
from typing import Tuple, TYPE_CHECKING
import math
import numpy as np
import pygame
from .Constants import (
    WORLD_ALBEDO, WORLD_AMBIENT_LIGHT, WORLD_LIGHT_TINT_MIX, WORLD_MIN_RADIUS_PX, LIT_WORLD_PIXEL_BUDGET,
)
from Vector3 import Vector3

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment
    from Galaxies.world import World


class LitWorlds:
    """Ray-traced sphere shading: every pixel's view ray is intersected with the world's sphere, so
    the silhouette is exact (an ellipse when the world is off-axis) and the shade is the cosine
    between the surface normal and the direction to the star (the star is far, so its light is
    treated as parallel). Cost depends on the size of the disc on screen, not on the world."""

    @staticmethod
    def light_tint(star_color: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Albedo times the star's colour (mixed towards white), as a 0..255 multiplier per channel."""
        return tuple(
            WORLD_ALBEDO[i] * ((1.0 - WORLD_LIGHT_TINT_MIX) + WORLD_LIGHT_TINT_MIX * star_color[i] / 255.0)
            for i in range(3)
        )

    @staticmethod
    def _screen_box(centre: Vector3, angular_radius: float, w: int, view_h: int, horizon_y: int, focal: float
                    ) -> Tuple[int, int, int, int]:
        """Screen rectangle (x0, y0, x1, y1), clipped to the view, that contains the world's disc.

        The silhouette is the projection of the cone of directions within `angular_radius` of the
        centre, so project 64 directions on its rim. If part of the rim is at or behind the camera
        plane the disc reaches the edges and the whole view is returned."""
        helper = Vector3(1.0, 0.0, 0.0) if abs(centre.x) < 0.9 else Vector3(0.0, 1.0, 0.0)
        e1 = Vector3(
            centre.y * helper.z - centre.z * helper.y,
            centre.z * helper.x - centre.x * helper.z,
            centre.x * helper.y - centre.y * helper.x,
        ).normalized()
        e2 = Vector3(
            centre.y * e1.z - centre.z * e1.y,
            centre.z * e1.x - centre.x * e1.z,
            centre.x * e1.y - centre.y * e1.x,
        )
        angles = np.linspace(0.0, math.tau, 64, endpoint=False)
        cos_a, sin_a = math.cos(angular_radius), math.sin(angular_radius)
        rim_x = cos_a * centre.x + sin_a * (np.cos(angles) * e1.x + np.sin(angles) * e2.x)
        rim_y = cos_a * centre.y + sin_a * (np.cos(angles) * e1.y + np.sin(angles) * e2.y)
        rim_z = cos_a * centre.z + sin_a * (np.cos(angles) * e1.z + np.sin(angles) * e2.z)
        if rim_z.min() <= 0.02:
            return 0, 0, w, view_h
        screen_x = w / 2 + focal * rim_x / rim_z
        screen_y = horizon_y - focal * rim_y / rim_z
        return (
            max(0, int(screen_x.min()) - 2), max(0, int(screen_y.min()) - 2),
            min(w, int(screen_x.max()) + 3), min(view_h, int(screen_y.max()) + 3),
        )

    @staticmethod
    def draw_world(
            surface: pygame.Surface, w: int, h: int, to_world: Vector3, to_star: Vector3, radius: float,
            star_color: Tuple[int, int, int], player: Player
            ) -> None:
        """Draw one world as seen from the ship, lit by the star.

        to_world and to_star are the vectors from the ship to the world's centre and to the star, in
        the active frame (as returned by Player.direction_to_world / direction_to_star)."""
        from Graphics.Instruments.common import view_geometry
        view_h, horizon_y, focal = view_geometry(h)

        distance = to_world.length()
        if distance <= radius:
            return
        centre = player.camera_components(to_world) * (1.0 / distance)   # unit vector, camera frame
        light = player.camera_components(to_star - to_world).normalized()  # from the world to the star
        cx, cy, cz = centre.x, centre.y, centre.z

        # A world too small to see is drawn as a small lit disc: inflate it to a minimum angular size.
        rho = max(radius / distance, WORLD_MIN_RADIUS_PX / focal)        # sin of the angular radius
        rho = min(rho, 0.999)
        angular_radius = math.asin(rho)

        # Cull what cannot reach the view, and find the screen box that can contain the disc.
        max_angle = math.atan(math.hypot(w / 2, max(horizon_y, view_h - horizon_y)) / focal)
        if math.acos(max(-1.0, min(1.0, cz))) - angular_radius > max_angle:
            return
        x0, y0, x1, y1 = LitWorlds._screen_box(centre, angular_radius, w, view_h, horizon_y, focal)
        box_w, box_h = x1 - x0, y1 - y0
        if box_w <= 0 or box_h <= 0:
            return

        # Big discs are shaded on a coarser grid and scaled up (the shade is smooth).
        step = 1 if box_w * box_h <= LIT_WORLD_PIXEL_BUDGET else math.ceil(math.sqrt(box_w * box_h / LIT_WORLD_PIXEL_BUDGET))
        grid_w, grid_h = -(-box_w // step), -(-box_h // step)
        xs = ((x0 + (np.arange(grid_w, dtype=np.float32) + 0.5) * step - w / 2) / focal).astype(np.float32)
        ys = ((horizon_y - (y0 + (np.arange(grid_h, dtype=np.float32) + 0.5) * step)) / focal).astype(np.float32)
        x, y = np.meshgrid(xs, ys)                                       # ray (x, y, 1), not normalised
        norm_sq = x * x + y * y + 1.0
        norm = np.sqrt(norm_sq)

        # sin^2 of the angle between each ray and the world's centre, from a cross product (no cancellation).
        cross_x = y * cz - cy
        cross_y = cx - x * cz
        cross_z = x * cy - y * cx
        sin_sq = (cross_x ** 2 + cross_y ** 2 + cross_z ** 2) / norm_sq
        disc = rho * rho - sin_sq                                        # >= 0 where the ray hits the sphere
        along = (x * cx + y * cy + cz) / norm                            # cos of that angle
        hit_distance = along - np.sqrt(np.clip(disc, 0.0, None))         # in units of the distance to the centre

        ray_dot_light = (x * light.x + y * light.y + light.z) / norm
        shade = np.clip((hit_distance * ray_dot_light - (cx * light.x + cy * light.y + cz * light.z)) / rho, 0.0, 1.0)

        # Coverage: anti-aliased edge from the angular distance to the limb (in pixels).
        denominator = max(2.0 * rho * math.sqrt(1.0 - rho * rho), 1e-3)
        pixels_inside = disc / denominator * focal * norm_sq / step
        coverage = np.clip(0.5 + pixels_inside, 0.0, 1.0) * (along > 0.0)
        if not coverage.any():
            return

        tint = np.array(LitWorlds.light_tint(star_color), dtype=np.float32)
        intensity = WORLD_AMBIENT_LIGHT + (1.0 - WORLD_AMBIENT_LIGHT) * shade
        rgb = np.clip(intensity[..., None] * tint, 0, 255).astype(np.uint8)

        layer = pygame.Surface((grid_w, grid_h), pygame.SRCALPHA)
        pixels = pygame.surfarray.pixels3d(layer)
        pixels[:] = rgb.transpose(1, 0, 2)
        del pixels
        alpha = pygame.surfarray.pixels_alpha(layer)
        alpha[:] = (coverage * 255).astype(np.uint8).T
        del alpha
        if step > 1:
            layer = pygame.transform.smoothscale(layer, (grid_w * step, grid_h * step))
        surface.blit(layer, (x0, y0), area=pygame.Rect(0, 0, box_w, box_h))

    @staticmethod
    def draw_nearest(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """The nearest world, lit by the star (used while unbound)."""
        world = environment.nearest_world
        star = world.parent_orbit.parent_stellar_system
        to_world = player.direction_to_world(world, environment.date_time)
        to_star = player.direction_to_star(world, environment.date_time)
        LitWorlds.draw_world(surface, w, h, to_world, to_star, world.radius, star.color, player)
