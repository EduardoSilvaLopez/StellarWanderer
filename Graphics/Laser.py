"""Depth-tested OpenGL laser beam rendering."""

import math

from OpenGL import GL, GLU

from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH, LASER_LENGTH, LASER


class Laser:
    """Render the laser beam using the OpenGL depth buffer for occlusion."""

    @staticmethod
    def draw(width, height, player):
        """Draw the laser beam if the player is firing.

        Laser is a straight line from player position extending 500 meters
        forward along the ship's heading, depth-tested against rocks/ground.
        """
        if not player.ship.laser.firing:
            return

        view_height = int(height * CONSOLE_TOP)
        aspect = width / view_height
        near_plane = max(0.1, NEAR_CLIP)

        # Match OpenGLRocks viewport and camera transform exactly.
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
        GL.glRotatef(player.orientation, 0.0, 1.0, 0.0)
        GL.glScalef(1.0, 1.0, -1.0)
        GL.glTranslatef(-player.position.x, -player.position.y, -player.position.z)

        # Compute laser endpoint: forward vector is (sin(θ), 0, cos(θ))
        orientation = math.radians(player.orientation)
        forward_x = math.sin(orientation)
        forward_z = math.cos(orientation)

        # Offset start point slightly ahead of camera to avoid culling
        start_x = player.position.x + forward_x * 5.0
        start_y = player.position.y - 5.0  # slightly below camera to avoid z-fighting with cockpit
        start_z = player.position.z + forward_z * 5.0

        end_x = player.position.x + LASER_LENGTH * forward_x
        end_y = player.position.y
        end_z = player.position.z + LASER_LENGTH * forward_z

        # Perpendicular vector (right): rotate forward 90° in XZ plane
        right_x = math.cos(orientation)
        right_z = -math.sin(orientation)

        # Laser beam cross-section half-size, in meters
        half_size = 0.5

        # The beam is fired exactly where the ship/camera is looking, so its
        # centre line is always coincident with the camera's own view axis,
        # which projects to a single point (the crosshair) at every depth. A
        # flat ribbon that only offsets in ONE perpendicular direction (either
        # only sideways, or only up/down) leaves the OTHER screen axis pinned
        # to that single point, producing a zero-area quad that never
        # rasterizes (confirmed empirically — the naive ribbon approaches
        # render nothing). The fix: draw a proper rectangular tube — 4 side
        # quads, each combining BOTH the "right" and "up" offsets — so every
        # face has real extent in both screen dimensions.
        def corner(cx, cy, cz, right_sign, up_sign):
            return (
                cx + right_x * half_size * right_sign,
                cy + half_size * up_sign,
                cz + right_z * half_size * right_sign,
            )

        s_tr = corner(start_x, start_y, start_z, 1, 1)
        s_br = corner(start_x, start_y, start_z, 1, -1)
        s_bl = corner(start_x, start_y, start_z, -1, -1)
        s_tl = corner(start_x, start_y, start_z, -1, 1)
        e_tr = corner(end_x, end_y, end_z, 1, 1)
        e_br = corner(end_x, end_y, end_z, 1, -1)
        e_bl = corner(end_x, end_y, end_z, -1, -1)
        e_tl = corner(end_x, end_y, end_z, -1, 1)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glColor3ub(*LASER)
        GL.glBegin(GL.GL_QUADS)
        for a, b, c, d in (
            (s_tr, s_br, e_br, e_tr),  # right face
            (s_br, s_bl, e_bl, e_br),  # bottom face
            (s_bl, s_tl, e_tl, e_bl),  # left face
            (s_tl, s_tr, e_tr, e_tl),  # top face
        ):
            GL.glVertex3f(*a)
            GL.glVertex3f(*b)
            GL.glVertex3f(*c)
            GL.glVertex3f(*d)
        GL.glEnd()
        GL.glDisable(GL.GL_DEPTH_TEST)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
