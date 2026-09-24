"""Depth-tested OpenGL rock rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple
import math

from OpenGL import GL, GLU

from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH

if TYPE_CHECKING:
    from Player import Player
    from Galaxies.Rock import Rock
    from Galaxies.OreField import OreField


class Rocks:
    """Render world-aligned rocks using the OpenGL depth buffer."""

    ORE_FIELD_SEGMENTS = 24
    ORE_FIELD_HEIGHT = 0.05  # Small offset above the ground to avoid z-fighting.

    @staticmethod
    def draw(width: int, height: int, player: Player, rocks: List[Rock], ore_fields: List[OreField]) -> None:
        """Draw all cube faces in a perspective OpenGL pass.

        A depth buffer, rather than face-selection heuristics, decides which
        projected face is visible at each pixel.
        """
        view_height = int(height * CONSOLE_TOP)
        aspect = width / view_height
        near_plane = max(0.1, NEAR_CLIP)

        # OpenGL's origin is bottom-left; the canopy is the top part of the
        # Pygame frame, so position this 3D viewport above the cockpit panel.
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GLU.gluPerspective(
            math.degrees(VIEW_VERTICAL_FOV_RADIANS), aspect, near_plane, MAX_DEPTH
        )
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        # OpenGL looks down -Z; preserve the game's +X screen-right and
        # +Z forward basis while rotating the camera clockwise.
        GL.glRotatef(player.orientation, 0.0, 1.0, 0.0)
        GL.glScalef(1.0, 1.0, -1.0)
        GL.glTranslatef(-player.position.x, -player.position.y, -player.position.z)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        Rocks._draw_ground(player)

        for ore_field in ore_fields:
            Rocks._draw_ore_field(ore_field)

        for rock in rocks:
            Rocks._draw_rock(rock)

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    @staticmethod
    def _draw_ground(player: Player) -> None:
        """Populate depth for the local surface without changing its color."""
        extent = MAX_DEPTH
        x0 = player.position.x - extent
        x1 = player.position.x + extent
        z0 = player.position.z - extent
        z1 = player.position.z + extent

        GL.glColorMask(GL.GL_FALSE, GL.GL_FALSE, GL.GL_FALSE, GL.GL_FALSE)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(x0, 0.0, z0)
        GL.glVertex3f(x1, 0.0, z0)
        GL.glVertex3f(x1, 0.0, z1)
        GL.glVertex3f(x0, 0.0, z1)
        GL.glEnd()
        GL.glColorMask(GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE)

    @staticmethod
    def _draw_ore_field(ore_field: OreField) -> None:
        """Draw a flat circle on the ground marking an ore field's extent."""
        y = Rocks.ORE_FIELD_HEIGHT
        GL.glColor3ub(*ore_field.color)
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex3f(ore_field.longitude, y, ore_field.latitude)
        for i in range(Rocks.ORE_FIELD_SEGMENTS + 1):
            angle = 2.0 * math.pi * i / Rocks.ORE_FIELD_SEGMENTS
            x = ore_field.longitude + ore_field.radius * math.cos(angle)
            z = ore_field.latitude + ore_field.radius * math.sin(angle)
            GL.glVertex3f(x, y, z)
        GL.glEnd()

    @staticmethod
    def _draw_rock(rock: Rock) -> None:
        half = rock.size / 2.0

        # Rocks are tilted around their own local Z axis by rock.tilt degrees,
        # THEN rotated around their vertical (Y) axis by rock.orientation
        # degrees, deviating from north (0 = unrotated, positive = clockwise) —
        # the same convention used for the ship's forward vector.
        tilt = math.radians(rock.tilt)
        cos_t = math.cos(tilt)
        sin_t = math.sin(tilt)
        orientation = math.radians(rock.orientation)
        cos_o = math.cos(orientation)
        sin_o = math.sin(orientation)

        def corner(sign_x: int, sign_y: int, sign_z: int) -> Tuple[float, float, float]:
            local_x, local_y, local_z = sign_x * half, sign_y * half, sign_z * half
            x1 = local_x * cos_t - local_y * sin_t
            y1 = local_x * sin_t + local_y * cos_t
            z1 = local_z
            x2 = x1 * cos_o + z1 * sin_o
            z2 = -x1 * sin_o + z1 * cos_o
            return (rock.longitude + x2, rock.altitude + y1, rock.latitude + z2)

        c000 = corner(-1, -1, -1)
        c100 = corner(+1, -1, -1)
        c110 = corner(+1, +1, -1)
        c010 = corner(-1, +1, -1)
        c001 = corner(-1, -1, +1)
        c101 = corner(+1, -1, +1)
        c111 = corner(+1, +1, +1)
        c011 = corner(-1, +1, +1)

        base = rock.color
        top = tuple(max(0, value - 50) for value in base)
        side = tuple(max(0, value - 25) for value in base)
        bottom = tuple(max(0, value - 70) for value in base)

        faces = (
            (top, (c010, c110, c111, c011)),
            (bottom, (c001, c101, c100, c000)),
            (side, (c000, c001, c011, c010)),
            (side, (c101, c100, c110, c111)),
            (base, (c000, c100, c110, c010)),
            (base, (c101, c001, c011, c111)),
        )

        GL.glBegin(GL.GL_QUADS)
        for color, vertices in faces:
            GL.glColor3ub(*color)
            for vertex in vertices:
                GL.glVertex3f(*vertex)
        GL.glEnd()
