"""Textured OpenGL ore field rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List
import math
import os

import pygame
from OpenGL import GL

if TYPE_CHECKING:
    from Galaxies.OreField import OreField


class OreFields:
    """Render textured ore fields on the ground."""

    ORE_FIELD_HEIGHT = 0.05  # Small offset above the ground to avoid z-fighting.
    _ore_field_texture_id: Optional[int] = None

    @staticmethod
    def draw(ore_fields: List[OreField], player_x: float, player_z: float) -> None:
        """Draw every ore field, within the camera transform set up by the caller."""
        if not ore_fields:
            return

        # Save GL state
        GL.glPushAttrib(GL.GL_ALL_ATTRIB_BITS)

        # Enable texturing and blending for transparent areas
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glColor3f(1.0, 1.0, 1.0)  # White = no color modulation
        GL.glBindTexture(GL.GL_TEXTURE_2D, OreFields._get_ore_field_texture())

        for ore_field in ore_fields:
            OreFields._draw_ore_field(ore_field, player_x, player_z)

        # Restore GL state
        GL.glPopAttrib()

    @staticmethod
    def _draw_ore_field(ore_field: OreField, player_x: float, player_z: float) -> None:
        """Draw a textured quad on the ground for an ore field.

        Vertices are made camera-relative in Python (double precision) before
        reaching glVertex3f, which truncates to float32 — see the matching
        comment in Rocks.draw() for why this matters at large coordinates.

        The texture is rotated by ore_field.orientation (in degrees, clockwise).
        Color is applied via vertex color modulation.
        """
        y = OreFields.ORE_FIELD_HEIGHT
        relative_longitude = ore_field.longitude - player_x
        relative_latitude = ore_field.latitude - player_z
        radius = ore_field.radius

        # Set color for texture modulation (white leaves texture unchanged)
        GL.glColor3ub(*ore_field.color)

        # Rotation angle in radians (clockwise, so negate for standard math)
        angle = math.radians(ore_field.orientation)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Four corners of the quad, rotated around center
        corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]  # local coordinates
        uv_coords = [(0, 1), (1, 1), (1, 0), (0, 0)]    # UV for quad

        GL.glBegin(GL.GL_QUADS)
        for (local_x, local_z), (u, v) in zip(corners, uv_coords):
            # Scale by radius and apply rotation
            rotated_x = (local_x * cos_a - local_z * sin_a) * radius
            rotated_z = (local_x * sin_a + local_z * cos_a) * radius

            world_x = relative_longitude + rotated_x
            world_z = relative_latitude + rotated_z

            GL.glTexCoord2f(u, v)
            GL.glVertex3f(world_x, y, world_z)
        GL.glEnd()

    @staticmethod
    def _load_ore_field_texture_surface() -> pygame.Surface:
        """Load and process the ore field texture from the resource file.

        The texture is processed to convert grayscale intensity to alpha:
        - White (255) becomes fully transparent (alpha 0)
        - Black (0) becomes fully opaque (alpha 255)
        - Gray values map proportionally
        """
        texture_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "Resources",
            "textures",
            "ore_field.png"
        )
        # Load image (will be RGB or RGBA)
        img = pygame.image.load(texture_path)
        w, h = img.get_size()

        # Create a new surface with RGBA
        result = pygame.Surface((w, h), pygame.SRCALPHA, 32)
        result_data = pygame.image.tostring(result, 'RGBA')

        # Get image data as pixel array and process each pixel
        img_data = pygame.image.tostring(img, 'RGB')

        # Process pixels: compute alpha from grayscale intensity
        # Iterate through the image data 3 bytes at a time (RGB)
        result_pixels = bytearray()
        for i in range(0, len(img_data), 3):
            r = img_data[i]
            g = img_data[i + 1]
            b = img_data[i + 2]
            # Convert RGB to grayscale, then invert for alpha
            grayscale = int(0.299 * r + 0.587 * g + 0.114 * b)
            alpha = 255 - grayscale
            result_pixels.extend([r, g, b, alpha])

        # Create surface from the processed pixel data
        result = pygame.image.fromstring(bytes(result_pixels), (w, h), 'RGBA')
        return result

    @staticmethod
    def _get_ore_field_texture() -> int:
        """Get or create the cached ore field texture."""
        if OreFields._ore_field_texture_id is None:
            surface = OreFields._load_ore_field_texture_surface()
            w, h = surface.get_size()

            # Convert to RGBA
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
            OreFields._ore_field_texture_id = texture

        return OreFields._ore_field_texture_id
