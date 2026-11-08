"""Textured OpenGL ore field rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List
import math
import weakref

import numpy as np
import pygame
from OpenGL import GL
from common.frame_watch import frame_watch
from common.paths import resource_path

if TYPE_CHECKING:
    from galaxies.ore_fields import OreField
    from .surface_light import SurfaceLight


class OreFields:
    """Render textured ore fields on the ground."""

    ORE_FIELD_HEIGHT = 0.05  # Small offset above the ground to avoid z-fighting.
    RELIEF_HEIGHT = 0.25  # The same over relief, where the terrain's mesh is coarser than the field's grid.
    GRID = 8  # Over relief the field is a grid of this many quads a side, following the ground.
    _relief_quads: weakref.WeakKeyDictionary[OreField, tuple] = weakref.WeakKeyDictionary()  # by field
    # The texture's paper background is not pure white (it runs from about 224 to 255 grey): every grey at or above this
    # is fully transparent, or the whole quad would show as a faint lighter square.
    TEXTURE_CLEAR_GRAY = 224
    _ore_field_texture_id: Optional[int] = None

    @staticmethod
    def draw(ore_fields: List[OreField], player_x: float, player_z: float, light: SurfaceLight) -> None:
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
            OreFields._draw_ore_field(ore_field, player_x, player_z, light)

        # Restore GL state
        GL.glPopAttrib()

    @staticmethod
    def _draw_ore_field(ore_field: OreField, player_x: float, player_z: float, light: SurfaceLight) -> None:
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

        # Set color for texture modulation (white leaves texture unchanged), lit by the sun on the ground
        GL.glColor3ub(*light.shade(ore_field.color, light.brightness(0.0, 1.0, 0.0)))
        if ore_field.parent_km2.parent_world.terrain.relief != 0.0:
            OreFields._draw_over_relief(ore_field, relative_longitude, relative_latitude)
            return

        # Rotation angle in radians
        angle = math.radians(ore_field.orientation)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Four corners of the quad, rotated around center
        corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]  # local coordinates
        uv_coords = [(0, 1), (1, 1), (1, 0), (0, 0)]  # UV for quad

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
    def _draw_over_relief(ore_field: OreField, relative_longitude: float, relative_latitude: float) -> None:
        """The field as a grid of GRID x GRID quads that follows the ground, kept off it by RELIEF_HEIGHT (a coarser
        mesh of the terrain can lie a little above the grid between its points). The vertices are built once, relative
        to the field's centre."""
        cached = OreFields._relief_quads.get(ore_field)
        if cached is None:
            angle = math.radians(ore_field.orientation)
            local = np.linspace(-1.0, 1.0, OreFields.GRID + 1)
            lx, lz = np.meshgrid(local, local, indexing="ij")
            rotated_x = (lx * math.cos(angle) - lz * math.sin(angle)) * ore_field.radius
            rotated_z = (lx * math.sin(angle) + lz * math.cos(angle)) * ore_field.radius
            heights = ore_field.parent_km2.parent_world.terrain.heights(ore_field.longitude + rotated_x,
                                                                        ore_field.latitude + rotated_z)
            vertices = np.stack([rotated_x, heights + OreFields.RELIEF_HEIGHT, rotated_z], axis=-1)
            texture = np.stack([(lx + 1.0) / 2.0, (1.0 - lz) / 2.0], axis=-1)
            corners = [(i + di, j + dj) for i in range(OreFields.GRID) for j in range(OreFields.GRID)
                       for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1))]
            rows, columns = zip(*corners)
            cached = (np.ascontiguousarray(vertices[rows, columns], dtype=np.float32),
                      np.ascontiguousarray(texture[rows, columns], dtype=np.float32))
            OreFields._relief_quads[ore_field] = cached
        vertices, texture = cached
        moved = vertices + np.array([relative_longitude, 0.0, relative_latitude], dtype=np.float32)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, moved)
        GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, texture)
        GL.glDrawArrays(GL.GL_QUADS, 0, len(moved))
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)

    @staticmethod
    def _load_ore_field_texture_surface() -> pygame.Surface:
        """Load and process the ore field texture from the resource file.

        The texture is processed to convert grayscale intensity to alpha:
        - Grays at or above TEXTURE_CLEAR_GRAY become fully transparent (alpha 0), the paper background included
        - Black (0) becomes fully opaque (alpha 255)
        - Grays below it map proportionally

        Computed with numpy over all pixels at once (a per-pixel Python loop took over a second on the 1024 x 1024 image,
        a hang on the first ore field drawn).
        """
        texture_path = resource_path("textures", "ore_field.png")
        # Load image (will be RGB or RGBA)
        img = pygame.image.load(texture_path)
        w, h = img.get_size()

        # Get image data as pixel array, one row of (r, g, b) per pixel
        rgb = np.frombuffer(pygame.image.tostring(img, 'RGB'), dtype=np.uint8).reshape(-1, 3).astype(np.float64)

        # Convert RGB to grayscale, then invert for alpha, with the paper background cut to zero
        grayscale = np.floor(rgb[:, 0] * 0.299 + rgb[:, 1] * 0.587 + rgb[:, 2] * 0.114).astype(np.int64)
        alpha = np.maximum(0, OreFields.TEXTURE_CLEAR_GRAY - grayscale) * 255 // OreFields.TEXTURE_CLEAR_GRAY

        # Create surface from the processed pixel data
        pixels = np.concatenate([rgb.astype(np.uint8), alpha.astype(np.uint8)[:, None]], axis=1)
        return pygame.image.fromstring(pixels.tobytes(), (w, h), 'RGBA')

    @staticmethod
    def _get_ore_field_texture() -> int:
        """Get or create the cached ore field texture."""
        if OreFields._ore_field_texture_id is None:
            with frame_watch.timed('ore field texture'):
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
