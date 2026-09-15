"""Depth-tested OpenGL rock rendering."""

import math

from OpenGL import GL, GLU

from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH


class Rocks:
    """Render world-aligned rocks using the OpenGL depth buffer."""

    @staticmethod
    def draw(width, height, player, rocks):
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

        for rock in rocks:
            Rocks._draw_rock(rock)

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    @staticmethod
    def _draw_ground(player):
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
    def _draw_rock(rock):
        half = rock.size / 2.0
        y0, y1 = rock.y - half, rock.y + half

        # Rocks are rotated around their own vertical (Y) axis by rock.orientation
        # degrees, deviating from north (0 = unrotated, positive = clockwise) —
        # the same convention used for the ship's forward vector.
        orientation = math.radians(rock.orientation)
        cos_o = math.cos(orientation)
        sin_o = math.sin(orientation)

        def rotated_corner(local_x, local_z):
            world_x = rock.x + local_x * cos_o + local_z * sin_o
            world_z = rock.z - local_x * sin_o + local_z * cos_o
            return world_x, world_z

        x0z0 = rotated_corner(-half, -half)
        x1z0 = rotated_corner(half, -half)
        x1z1 = rotated_corner(half, half)
        x0z1 = rotated_corner(-half, half)

        base = rock.color
        top = tuple(max(0, value - 50) for value in base)
        side = tuple(max(0, value - 25) for value in base)
        bottom = tuple(max(0, value - 70) for value in base)

        faces = (
            (top, ((x0z0[0], y1, x0z0[1]), (x1z0[0], y1, x1z0[1]), (x1z1[0], y1, x1z1[1]), (x0z1[0], y1, x0z1[1]))),
            (bottom, ((x0z1[0], y0, x0z1[1]), (x1z1[0], y0, x1z1[1]), (x1z0[0], y0, x1z0[1]), (x0z0[0], y0, x0z0[1]))),
            (side, ((x0z0[0], y0, x0z0[1]), (x0z1[0], y0, x0z1[1]), (x0z1[0], y1, x0z1[1]), (x0z0[0], y1, x0z0[1]))),
            (side, ((x1z1[0], y0, x1z1[1]), (x1z0[0], y0, x1z0[1]), (x1z0[0], y1, x1z0[1]), (x1z1[0], y1, x1z1[1]))),
            (base, ((x0z0[0], y0, x0z0[1]), (x1z0[0], y0, x1z0[1]), (x1z0[0], y1, x1z0[1]), (x0z0[0], y1, x0z0[1]))),
            (base, ((x1z1[0], y0, x1z1[1]), (x0z1[0], y0, x0z1[1]), (x0z1[0], y1, x0z1[1]), (x1z1[0], y1, x1z1[1]))),
        )

        GL.glBegin(GL.GL_QUADS)
        for color, vertices in faces:
            GL.glColor3ub(*color)
            for vertex in vertices:
                GL.glVertex3f(*vertex)
        GL.glEnd()
