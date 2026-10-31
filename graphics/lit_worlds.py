"""Worlds (planets and moons) drawn as spheres lit by their star."""

from __future__ import annotations
from typing import Tuple, TYPE_CHECKING
import math
import numpy as np
import pygame
from .constants import (
    WORLD_AMBIENT_LIGHT, WORLD_LIGHT_TINT_MIX, WORLD_MIN_RADIUS_PX, LIT_WORLD_PIXEL_BUDGET, MIN_VISIBLE_PX,
    GIANT_HAZE_PIXELS, GIANT_HAZE_ALPHA,
)
from common.vector3 import Vector3

if TYPE_CHECKING:
    from galaxies.world import World
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class LitWorlds:
    """Ray-traced sphere shading: every pixel's view ray is intersected with the world's sphere, so
    the silhouette is exact (an ellipse when the world is off-axis) and the shade is the cosine
    between the surface normal and the direction to the star (the star is far, so its light is
    treated as parallel). Cost depends on the size of the disc on screen, not on the world. A giant is an
    oblate ellipsoid, intersected the same way; its cloud bands and its limb haze are added to that.

    Every world drawn in the sky (planets and moons) is lit this way. Worlds too small to see are drawn as a small
    lit disc (WORLD_MIN_RADIUS_PX), and one under MIN_VISIBLE_PX across is not drawn. While unbound, all worlds are lit this way, the targeted one too, in
    distance order (`OtherWorlds.draw`). While bound, every world except the targeted one is lit; the targeted one is
    the disc below the horizon, lit by the sun like the ground (`FixedWorld.draw_surface`, given
    `SurfaceLight.ground_colour()`)."""

    @staticmethod
    def light_tint(star_color: Tuple[int, int, int], surface_colour: Tuple[int, int,
                                                                           int]) -> Tuple[float, float, float]:
        """The world's surface colour (`World.surface_colour`) times the star's colour (mixed towards white), as a
        0..255 multiplier per channel."""
        return tuple(
            surface_colour[i] * ((1.0 - WORLD_LIGHT_TINT_MIX) + WORLD_LIGHT_TINT_MIX * star_color[i] / 255.0)
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
            surface: pygame.Surface, w: int, h: int, to_world: Vector3, to_star: Vector3, world: World,
            star_color: Tuple[int, int, int], ship: Ship
            ) -> None:
        """Draw one world as seen from the ship, lit by the star, with its surface colour.

        to_world and to_star are the vectors from the ship to the world's centre and to the star, in
        the active frame (as returned by Navigation.direction_to_body / direction_to_star). The spin axis of every
        world is the z axis of the stellar frame (see World), so its flattening alone gives the shape."""
        from graphics.instruments.common import view_geometry
        view_h, horizon_y, focal = view_geometry(h)

        radius = world.radius
        flattening = world.flattening
        equatorial = radius * (1.0 - flattening) ** (-1.0 / 3.0)
        polar = equatorial * (1.0 - flattening)
        distance = to_world.length()
        if distance <= equatorial or 2.0 * equatorial * focal / distance < MIN_VISIBLE_PX:
            return
        centre = ship.attitude.camera_components(to_world) * (1.0 / distance)  # unit vector, camera frame
        light = ship.attitude.camera_components(to_star - to_world).normalized()  # from the world to the star
        pole = ship.attitude.camera_components(Vector3(0.0, 0.0, 1.0))  # the spin axis, camera frame
        cx, cy, cz = centre.x, centre.y, centre.z

        # A world too small to see is drawn as a small lit disc: inflate it to a minimum angular size, all its axes
        # with it. The axes are sines of the angular radii, as is rho.
        rho = max(radius / distance, WORLD_MIN_RADIUS_PX / focal)
        rho = min(rho, 0.999)
        inflation = rho * distance / radius
        a = min(equatorial / distance * inflation, 0.999)  # the equatorial semi-axis, in distances
        c = polar / distance * inflation  # the polar one

        # Cull what cannot reach the view, and find the screen box that can contain the disc and its haze.
        haze_angle = GIANT_HAZE_PIXELS / focal if world.has_haze else 0.0
        outer_angle = math.asin(min(a + haze_angle, 0.999))
        max_angle = math.atan(math.hypot(w / 2, max(horizon_y, view_h - horizon_y)) / focal)
        if math.acos(max(-1.0, min(1.0, cz))) - outer_angle > max_angle:
            return
        x0, y0, x1, y1 = LitWorlds._screen_box(centre, outer_angle, w, view_h, horizon_y, focal)
        box_w, box_h = x1 - x0, y1 - y0
        if box_w <= 0 or box_h <= 0:
            return

        # Big discs are shaded on a coarser grid and scaled up (the shade is smooth).
        step = 1 if box_w * box_h <= LIT_WORLD_PIXEL_BUDGET else math.ceil(math.sqrt(box_w * box_h
                                                                                     / LIT_WORLD_PIXEL_BUDGET))
        grid_w, grid_h = -(-box_w // step), -(-box_h // step)
        xs = ((x0 + (np.arange(grid_w, dtype=np.float32) + 0.5) * step - w / 2) / focal).astype(np.float32)
        ys = ((horizon_y - (y0 + (np.arange(grid_h, dtype=np.float32) + 0.5) * step)) / focal).astype(np.float32)
        x, y = np.meshgrid(xs, ys)  # ray (x, y, 1), not normalised
        norm_sq = x * x + y * y + 1.0

        # The ellipsoid is the quadric (P - C) M (P - C) = 1, with M = I / a^2 + k p p^T, where p is the spin axis and
        # k makes the polar semi-axis c. A ray P = t (x, y, 1) meets it where t^2 A - 2 t B + D = 0, nearest first.
        a2 = a * a
        k = 1.0 / (c * c) - 1.0 / a2
        pole_on_centre = pole.x * cx + pole.y * cy + pole.z * cz
        pole_on_ray = pole.x * x + pole.y * y + pole.z
        ray_quad = norm_sq / a2 + k * pole_on_ray * pole_on_ray  # A = d M d
        mc_x = cx / a2 + k * pole_on_centre * pole.x
        mc_y = cy / a2 + k * pole_on_centre * pole.y
        mc_z = cz / a2 + k * pole_on_centre * pole.z
        ray_mc = x * mc_x + y * mc_y + mc_z  # B = d M C
        centre_quad = cx * mc_x + cy * mc_y + cz * mc_z - 1.0  # D = C M C - 1
        disc = ray_mc * ray_mc - ray_quad * centre_quad  # >= 0 where the ray meets the ellipsoid
        along = (ray_mc - np.sqrt(np.clip(disc, 0.0, None))) / ray_quad  # t: the near hit, in units of the ray
        vx, vy, vz = along * x - cx, along * y - cy, along - cz  # from the centre to the hit point

        # The normal is M (P - C): the shade is its cosine with the direction to the star.
        pv = pole.x * vx + pole.y * vy + pole.z * vz
        nx = vx / a2 + k * pv * pole.x
        ny = vy / a2 + k * pv * pole.y
        nz = vz / a2 + k * pv * pole.z
        n_len = np.sqrt(nx * nx + ny * ny + nz * nz)
        shade = np.clip((nx * light.x + ny * light.y + nz * light.z) / n_len, 0.0, 1.0)

        # Coverage: anti-aliased edge from the angular distance to the limb, as for a sphere of radius a.
        denominator = max(2.0 * a * math.sqrt(1.0 - a * a), 1e-3)
        pixels_inside = disc / ray_quad * a2 / denominator * focal * norm_sq / step
        coverage = np.clip(0.5 + pixels_inside, 0.0, 1.0) * (along > 0.0)
        if not coverage.any():
            return

        tint = np.array(LitWorlds.light_tint(star_color, world.surface_colour), dtype=np.float32)
        intensity = WORLD_AMBIENT_LIGHT + (1.0 - WORLD_AMBIENT_LIGHT) * shade
        if world.band_contrast > 0.0:
            sine_latitude = pv / np.sqrt(vx * vx + vy * vy + vz * vz)
            bands = np.sin(world.band_count * (0.5 * math.pi) * sine_latitude + world.band_phase)
            intensity = intensity * (1.0 + world.band_contrast * bands)
        rgb = np.clip(intensity[..., None] * tint, 0, 255).astype(np.uint8)

        opacity = coverage
        if world.has_haze:
            # Outside the limb the haze fades out over GIANT_HAZE_PIXELS. It is lit by the limb's own normal, which is
            # the ray's direction seen from the centre, so only the sunlit edge glows.
            haze_width = GIANT_HAZE_PIXELS / step  # in grid cells, as pixels_inside
            haze = np.clip(1.0 + pixels_inside / haze_width, 0.0, 1.0) * GIANT_HAZE_ALPHA
            opacity = np.maximum(coverage, haze)
            # Only the ring outside the limb needs the haze's shade: it is a small part of the box.
            ring = (coverage <= 0.0) & (haze > 0.0)
            ray_length = np.sqrt(norm_sq[ring])
            ux, uy, uz = x[ring] / ray_length, y[ring] / ray_length, 1.0 / ray_length
            towards_centre = ux * cx + uy * cy + uz * cz
            across = np.sqrt(np.maximum(1.0 - towards_centre * towards_centre, 1e-6))
            limb_lit = (ux * light.x + uy * light.y + uz * light.z
                        - towards_centre * (cx * light.x + cy * light.y + cz * light.z)) / across
            haze_shade = WORLD_AMBIENT_LIGHT + (1.0 - WORLD_AMBIENT_LIGHT) * np.clip(limb_lit, 0.0, 1.0)
            rgb[ring] = np.clip(haze_shade[:, None] * tint, 0, 255).astype(np.uint8)

        layer = pygame.Surface((grid_w, grid_h), pygame.SRCALPHA)
        pixels = pygame.surfarray.pixels3d(layer)
        pixels[:] = rgb.transpose(1, 0, 2)
        del pixels
        alpha = pygame.surfarray.pixels_alpha(layer)
        alpha[:] = (opacity * 255).astype(np.uint8).T
        del alpha
        if step > 1:
            layer = pygame.transform.smoothscale(layer, (grid_w * step, grid_h * step))
        surface.blit(layer, (x0, y0), area=pygame.Rect(0, 0, box_w, box_h))

    @staticmethod
    def draw_targeted(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        """The targeted body, lit by the star, for OpenGLGui while bound when there is no surface light. The star is not
        drawn here: the OpenGL pass draws it (star_gl.py)."""
        from galaxies.world import World
        body = environment.targeted_body
        if not isinstance(body, World):  # the star
            return
        star = body.stellar_system.star
        to_world = ship.navigation.direction_to_body(body, environment.date_time)
        to_star = ship.navigation.direction_to_star(body, environment.date_time)
        LitWorlds.draw_world(surface, w, h, to_world, to_star, body, star.color, ship)
