"""Depth-tested OpenGL ore mine rendering.

Ore mines are drawn as textured cylinders. The texture — a procedurally
generated "futuristic device" look — is built once on first use and cached
as an OpenGL texture shared by every mine, since every mine has the same fixed
shape and appearance. The only other look is a weathered texture for the external
mines that have been unused for long (`ExternalMine.is_inactive`).
"""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Tuple
import math

import pygame
from OpenGL import GL

from common.frame_watch import frame_watch
from .constants import (
    MINE_SEGMENTS, MINE_BASE_HEIGHT,
    MINE_TEXTURE_WIDTH, MINE_TEXTURE_HEIGHT,
    MINE_HULL_COLOR, MINE_HULL_DARK, MINE_HULL_LIGHT, MINE_ACCENT,
    MINE_WARNING_A, MINE_WARNING_B, MINE_CAP_COLOR,
    MINE_INACTIVE_HULL_COLOR, MINE_INACTIVE_HULL_DARK, MINE_INACTIVE_HULL_LIGHT, MINE_INACTIVE_ACCENT,
    MINE_INACTIVE_WARNING_A, MINE_INACTIVE_WARNING_B,
)

if TYPE_CHECKING:
    from galaxies.ore_mine import OreMine
    from .surface_light import SurfaceLight

# The colours of each look: hull, seams, highlights, accent band, hazard stripes (two).
_ACTIVE_PALETTE = (MINE_HULL_COLOR, MINE_HULL_DARK, MINE_HULL_LIGHT, MINE_ACCENT, MINE_WARNING_A, MINE_WARNING_B)
_INACTIVE_PALETTE = (MINE_INACTIVE_HULL_COLOR, MINE_INACTIVE_HULL_DARK, MINE_INACTIVE_HULL_LIGHT,
                     MINE_INACTIVE_ACCENT, MINE_INACTIVE_WARNING_A, MINE_INACTIVE_WARNING_B)


class OreMines:
    """Render textured cylinders marking ore mines."""

    _mine_texture_ids: Dict[bool, int] = {}  # by inactive

    @staticmethod
    def draw(mines: List[OreMine], player_x: float, player_z: float, light: SurfaceLight,
             game_date_time: datetime) -> None:
        """Draw every mine, within the camera transform set up by the caller.

        Side walls (textured, the weathered look for the mines inactive at `game_date_time`) are drawn for all mines
        first, then texturing is disabled before drawing the untextured caps, so no texture state leaks into whatever
        the caller draws next.
        """
        if not mines:
            return

        GL.glColor3ub(255, 255, 255)
        GL.glEnable(GL.GL_TEXTURE_2D)
        for inactive in (False, True):
            GL.glBindTexture(GL.GL_TEXTURE_2D, OreMines._get_mine_texture(inactive))
            for mine in mines:
                if mine.is_inactive(game_date_time) == inactive:
                    OreMines._draw_mine_side(mine, player_x, player_z, light)
        GL.glDisable(GL.GL_TEXTURE_2D)

        for mine in mines:
            OreMines._draw_mine_caps(mine, player_x, player_z, light)

    @staticmethod
    def _mine_circle_points(mine: OreMine, y: float, player_x: float,
                            player_z: float) -> List[Tuple[float, float, float, float]]:
        """Camera-relative (x, y, z, u) points around a mine's circumference.

        Rotated by the mine's orientation using the same convention as
        the rocks (graphics/rock_shape.py, rotate; no tilt term — mines stand vertical). Longitude/
        latitude are made relative to the player here, in double precision,
        before reaching glVertex3f — see the comment in Rocks.draw() for why.
        """
        orientation = math.radians(mine.orientation)
        cos_o, sin_o = math.cos(orientation), math.sin(orientation)
        relative_longitude = mine.longitude - player_x
        relative_latitude = mine.latitude - player_z
        points = []
        for i in range(MINE_SEGMENTS + 1):
            frac = i / MINE_SEGMENTS
            angle = 2.0 * math.pi * frac
            local_x = mine.MINE_RADIUS * math.cos(angle)
            local_z = mine.MINE_RADIUS * math.sin(angle)
            x2 = local_x * cos_o + local_z * sin_o
            z2 = -local_x * sin_o + local_z * cos_o
            points.append((relative_longitude + x2, y, relative_latitude + z2, frac))
        return points

    @staticmethod
    def _draw_mine_side(mine: OreMine, player_x: float, player_z: float, light: SurfaceLight) -> None:
        base_y = MINE_BASE_HEIGHT
        top_y = base_y + mine.MINE_HEIGHT
        base_pts = OreMines._mine_circle_points(mine, base_y, player_x, player_z)
        top_pts = OreMines._mine_circle_points(mine, top_y, player_x, player_z)
        relative_longitude = mine.longitude - player_x
        relative_latitude = mine.latitude - player_z

        GL.glBegin(GL.GL_QUAD_STRIP)
        for (bx, by, bz, u), (tx, ty, tz, _) in zip(base_pts, top_pts):
            # The wall's outward normal at this segment: from the axis to the point, lit by the sun.
            normal_x = (bx - relative_longitude) / mine.MINE_RADIUS
            normal_z = (bz - relative_latitude) / mine.MINE_RADIUS
            GL.glColor3ub(*light.shade((255, 255, 255), light.brightness(normal_x, 0.0, normal_z)))
            GL.glTexCoord2f(u, 0.0)
            GL.glVertex3f(bx, by, bz)
            GL.glTexCoord2f(u, 1.0)
            GL.glVertex3f(tx, ty, tz)
        GL.glEnd()

    @staticmethod
    def _draw_mine_caps(mine: OreMine, player_x: float, player_z: float, light: SurfaceLight) -> None:
        base_y = MINE_BASE_HEIGHT
        top_y = base_y + mine.MINE_HEIGHT
        relative_longitude = mine.longitude - player_x
        relative_latitude = mine.latitude - player_z

        # The top cap faces up, the base cap down (it is on the ground, so it is almost never seen).
        for y, normal_y, reverse in ((top_y, 1.0, False), (base_y, -1.0, True)):
            GL.glColor3ub(*light.shade(MINE_CAP_COLOR, light.brightness(0.0, normal_y, 0.0)))
            points = OreMines._mine_circle_points(mine, y, player_x, player_z)
            if reverse:
                points = list(reversed(points))
            GL.glBegin(GL.GL_TRIANGLE_FAN)
            GL.glVertex3f(relative_longitude, y, relative_latitude)
            for x, py, z, _ in points:
                GL.glVertex3f(x, py, z)
            GL.glEnd()

    @staticmethod
    def _build_mine_texture_surface(inactive: bool) -> pygame.Surface:
        """Procedurally paint a "futuristic device" panel onto an offscreen surface (dull and without a glowing band if
        `inactive`)."""
        hull, hull_dark, hull_light, accent, warning_a, warning_b = _INACTIVE_PALETTE if inactive else _ACTIVE_PALETTE
        w, h = MINE_TEXTURE_WIDTH, MINE_TEXTURE_HEIGHT
        surface = pygame.Surface((w, h)).convert()
        surface.fill(hull)

        # Vertical panel seams.
        panel_count = 6
        for i in range(panel_count + 1):
            x = int(w * i / panel_count)
            pygame.draw.line(surface, hull_dark, (x, 0), (x, h), 3)

        # Horizontal vent ridges, repeated down the height.
        for y in range(20, h - 20, 48):
            pygame.draw.rect(surface, hull_dark, (8, y, w - 16, 6))
            pygame.draw.rect(surface, hull_light, (8, y + 6, w - 16, 2))

        # Glowing accent band (flat saturated color, no real transparency).
        band_y = int(h * 0.42)
        pygame.draw.rect(surface, accent, (0, band_y, w, 18))

        # Diagonal hazard stripe near the base.
        stripe_y = h - 60
        stripe_h = 28
        step = 24
        for x in range(-step, w + step, step):
            color = warning_a if (x // step) % 2 == 0 else warning_b
            pygame.draw.polygon(surface, color, [
                (x, stripe_y), (x + step, stripe_y),
                (x + step - stripe_h, stripe_y + stripe_h), (x - stripe_h, stripe_y + stripe_h),
            ])

        # Rivets at each panel seam.
        for i in range(panel_count + 1):
            x = int(w * i / panel_count)
            for y in range(30, h - 30, 100):
                pygame.draw.circle(surface, hull_light, (x, y), 3)

        # Heavier edge bars at u=0/u=1 disguise the texture wrap seam as a
        # deliberate structural corner beam.
        pygame.draw.rect(surface, hull_dark, (0, 0, 4, h))
        pygame.draw.rect(surface, hull_dark, (w - 4, 0, 4, h))

        return surface

    @staticmethod
    def _get_mine_texture(inactive: bool = False) -> int:
        if inactive not in OreMines._mine_texture_ids:
            with frame_watch.timed('ore mine texture'):
                surface = OreMines._build_mine_texture_surface(inactive)
                w, h = surface.get_size()
                pixels = pygame.image.tostring(surface, 'RGBA', False)

                texture = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GL.glTexImage2D(
                    GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, w, h, 0,
                    GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels
                )
                OreMines._mine_texture_ids[inactive] = texture

        return OreMines._mine_texture_ids[inactive]
