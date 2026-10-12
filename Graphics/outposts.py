"""Textured OpenGL outpost buildings: flat boxes with a door on one long wall (Resources/textures/outpost.png).

The atlas layout is described in Tools/generate_outpost_texture.py. The door faces the outpost's
orientation (degrees clockwise from north, as for rocks and mines), so local +z is the door wall.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple
import math
import logging
import os

import pygame
from OpenGL import GL, GLU

if TYPE_CHECKING:
    from Galaxies.outpost import Outpost
    from .surface_light import SurfaceLight

logger = logging.getLogger(__name__)

ATLAS_WIDTH = 1024
ATLAS_HEIGHT = 512
TEXTURE_PATH = os.path.join(os.path.dirname(__file__), '..', 'Resources', 'textures', 'outpost.png')

# Atlas regions (x, y, w, h) in pixels; must match Tools/generate_outpost_texture.py.
FRONT = (0, 0, 480, 120)
BACK = (0, 128, 480, 120)
LEFT = (512, 256, 240, 120)
RIGHT = (768, 256, 240, 120)
ROOF = (512, 0, 480, 240)

class Outposts:
    """Render outpost buildings within the camera transform set up by the caller (see Rocks.draw).
    Each face is lit by the sun from its own normal (see SurfaceLight)."""

    _texture_id: Optional[int] = None

    @staticmethod
    def draw(outposts: List[Outpost], player_x: float, player_z: float, light: SurfaceLight) -> None:
        if not outposts:
            return
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, Outposts._get_texture())
        for outpost in outposts:
            Outposts._draw_outpost(outpost, player_x, player_z, light)
        GL.glDisable(GL.GL_TEXTURE_2D)

    @staticmethod
    def _draw_outpost(outpost: Outpost, player_x: float, player_z: float, light: SurfaceLight) -> None:
        width = outpost.WIDTH / 2.0
        depth = outpost.DEPTH / 2.0
        height = outpost.HEIGHT
        angle = math.radians(outpost.orientation)
        cos_a, sin_a = math.cos(angle), math.sin(angle)  # rotation, as in corner() below
        # Double precision: subtract the camera before anything reaches glVertex3f (see Rocks.draw).
        origin_x = outpost.longitude - player_x
        origin_z = outpost.latitude - player_z

        def corner(lx: float, ly: float, lz: float) -> Tuple[float, float, float]:
            x2 = lx * cos_a + lz * sin_a
            z2 = -lx * sin_a + lz * cos_a
            return (origin_x + x2, ly, origin_z + z2)

        def quad(
                face: Tuple[int, int, int, int], normal: Tuple[float, float, float],
                points: List[Tuple[float, float, float]], uvs: List[Tuple[float, float]]
                ) -> None:
            u0, v0, u1, v1 = Outposts._uv_rect(face)
            # The outward normal of this face, in world terms, lit by the sun.
            GL.glColor3ub(*light.shade((255, 255, 255), light.brightness(*normal)))
            GL.glBegin(GL.GL_QUADS)
            for (x, y, z), (u, v) in zip(points, uvs):
                GL.glTexCoord2f(u0 + (u1 - u0) * u, v0 + (v1 - v0) * v)
                GL.glVertex3f(x, y, z)
            GL.glEnd()

        # Outward normals: local +z is (sin a, 0, cos a) in the world, with the same rotation as corner().
        door_normal = (sin_a, 0.0, cos_a)
        side_normal = (cos_a, 0.0, -sin_a)

        # Door wall: long side on local +z (the door faces `orientation`).
        quad(FRONT, door_normal,
             [corner(-width, 0, depth), corner(width, 0, depth), corner(width, height, depth), corner(-width, height, depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        # Back wall: long side on local -z, seen from outside, so mirrored in u.
        quad(BACK, (-sin_a, 0.0, -cos_a),
             [corner(width, 0, -depth), corner(-width, 0, -depth), corner(-width, height, -depth), corner(width, height, -depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        # Short walls, 6 m each.
        quad(LEFT, (-side_normal[0], 0.0, -side_normal[2]),
             [corner(-width, 0, depth), corner(-width, 0, -depth), corner(-width, height, -depth), corner(-width, height, depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        quad(RIGHT, side_normal,
             [corner(width, 0, -depth), corner(width, 0, depth), corner(width, height, depth), corner(width, height, -depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        # Flat roof.
        quad(ROOF, (0.0, 1.0, 0.0),
             [corner(-width, height, depth), corner(width, height, depth), corner(width, height, -depth), corner(-width, height, -depth)],
             [(0, 0), (1, 0), (1, 1), (0, 1)])

    @staticmethod
    def _uv_rect(region: Tuple[int, int, int, int]) -> Tuple[float, float, float, float]:
        """Texture coordinates of an atlas region: (u0, v0, u1, v1), with v = 0 at the first image row."""
        x, y, w, h = region
        return x / ATLAS_WIDTH, y / ATLAS_HEIGHT, (x + w) / ATLAS_WIDTH, (y + h) / ATLAS_HEIGHT

    @staticmethod
    def _get_texture() -> int:
        if Outposts._texture_id is None:
            if os.path.exists(TEXTURE_PATH):
                surface = pygame.image.load(TEXTURE_PATH).convert_alpha()
            else:
                logger.error(f"Outpost texture missing: {TEXTURE_PATH}. Using a plain grey texture.")
                surface = pygame.Surface((ATLAS_WIDTH, ATLAS_HEIGHT)).convert()
                surface.fill((90, 94, 102))
            width, height = surface.get_size()
            pixels = pygame.image.tostring(surface, 'RGBA', False)

            texture = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GLU.gluBuild2DMipmaps(GL.GL_TEXTURE_2D, GL.GL_RGBA, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels)
            Outposts._texture_id = texture
        return Outposts._texture_id
