"""Depth-tested OpenGL ore field rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List
import math

from OpenGL import GL

if TYPE_CHECKING:
    from Galaxies.OreField import OreField


class OreFields:
    """Render flat markers on the ground for ore field extents."""

    ORE_FIELD_SEGMENTS = 24
    ORE_FIELD_HEIGHT = 0.05  # Small offset above the ground to avoid z-fighting.

    @staticmethod
    def draw(ore_fields: List[OreField]) -> None:
        """Draw every ore field, within the camera transform set up by the caller."""
        for ore_field in ore_fields:
            OreFields._draw_ore_field(ore_field)

    @staticmethod
    def _draw_ore_field(ore_field: OreField) -> None:
        """Draw a flat circle on the ground marking an ore field's extent."""
        y = OreFields.ORE_FIELD_HEIGHT
        GL.glColor3ub(*ore_field.color)
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex3f(ore_field.longitude, y, ore_field.latitude)
        for i in range(OreFields.ORE_FIELD_SEGMENTS + 1):
            angle = 2.0 * math.pi * i / OreFields.ORE_FIELD_SEGMENTS
            x = ore_field.longitude + ore_field.radius * math.cos(angle)
            z = ore_field.latitude + ore_field.radius * math.sin(angle)
            GL.glVertex3f(x, y, z)
        GL.glEnd()
