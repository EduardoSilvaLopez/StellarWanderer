"""Depth-tested OpenGL laser beam rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, Tuple
import math

from OpenGL import GL, GLU

from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH, LASER_COLOR

if TYPE_CHECKING:
    from Player import Player


class Laser:
    """Render the laser beam using the OpenGL depth buffer for occlusion."""

    @staticmethod
    def draw(width: int, height: int, player: Player) -> None:
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
        GL.glMultMatrixf(player.camera_matrix())
        # X/Z made camera-relative on the CPU (double precision) instead of via
        # glTranslatef, to avoid float32 truncation at large world coordinates
        # — see the matching comment in Rocks.draw() for why.
        if player.is_bound:
            GL.glTranslatef(0.0, -player.position.y, 0.0)
            # Perpendicular vector (right): rotate forward 90° in XZ plane
            yaw = math.radians(player.yaw)
            right_axis = (math.cos(yaw), 0.0, -math.sin(yaw))
            up_axis = (0.0, 1.0, 0.0)
            origin = (player.position.x, 0.0, player.position.z)
        else:
            # Unbound the beam is stored relative to the ship, along its own axes.
            right_axis = player.right
            up_axis = player.up
            origin = (0.0, 0.0, 0.0)

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
        def corner(cx: float, cy: float, cz: float, right_sign: int, up_sign: int) -> Tuple[float, float, float]:
            return tuple(
                centre - base + right * half_size * right_sign + up * half_size * up_sign
                for centre, base, right, up in zip((cx, cy, cz), origin, right_axis, up_axis)
            )

        s_tr = corner(player.ship.laser.start_x, player.ship.laser.start_y, player.ship.laser.start_z, 1, 1)
        s_br = corner(player.ship.laser.start_x, player.ship.laser.start_y, player.ship.laser.start_z, 1, -1)
        s_bl = corner(player.ship.laser.start_x, player.ship.laser.start_y, player.ship.laser.start_z, -1, -1)
        s_tl = corner(player.ship.laser.start_x, player.ship.laser.start_y, player.ship.laser.start_z, -1, 1)
        e_tr = corner(player.ship.laser.end_x, player.ship.laser.end_y, player.ship.laser.end_z, 1, 1)
        e_br = corner(player.ship.laser.end_x, player.ship.laser.end_y, player.ship.laser.end_z, 1, -1)
        e_bl = corner(player.ship.laser.end_x, player.ship.laser.end_y, player.ship.laser.end_z, -1, -1)
        e_tl = corner(player.ship.laser.end_x, player.ship.laser.end_y, player.ship.laser.end_z, -1, 1)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glColor3ub(*LASER_COLOR)
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
