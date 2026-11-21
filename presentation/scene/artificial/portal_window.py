"""What is seen through a Portal's opening: the firmament of the system at the other end of the link.

The other end is placed as if both stars were on one axis (`Portal.carry`), so the sky through the ring is the one the
ship would see from the same place relative to the other ring, looking the same way relative to it: the Milky Way, the
fixed stars of that system and its star, not its worlds. It is drawn inside the ring's disc, over what the ship's own sky
drew there (this side's sky, worlds and base are not seen through it), with the stencil as the mask. Crossing is then
unseen: the ring behind the ship shows the old system, and the rest of the view is already the new one.

Drawn from the ring's own frame in double precision, as `PortalGl` draws the ring, just before its band.
"""

from __future__ import annotations

import math
from typing import Optional, TYPE_CHECKING

import numpy as np
from OpenGL import GL, GLU

from presentation.cockpit.instruments.common import view_geometry
from presentation.constants import MIN_VISIBLE_PX, NEAR_CLIP, SPACE_COLOR, VIEW_VERTICAL_FOV_RADIANS
from presentation.scene.interplanetary.local_star import view_from
from presentation.scene.interplanetary.star_gl import StarGl
from presentation.scene.interstellar.distant_stars import DistantStars
from presentation.scene.interstellar.milky_way import MilkyWay
from universe.artifacts.spaceships.attitude import Attitude

if TYPE_CHECKING:
    from common.vector3 import Vector3
    from game_environment import GameEnvironment
    from universe.artifacts.settlements.portal import Portal
    from universe.artifacts.spaceships.ship import Ship

DISC_SEGMENTS = 64  # the corners of the polygon that is the mask


class PortalWindow:
    """The sky of the other end of a Portal, inside its ring."""

    _has_stencil: Optional[bool] = None  # whether the window has a stencil buffer: without one there is no mask

    @staticmethod
    def draw(width: int, height: int, ship: Ship, environment: GameEnvironment, portal: Portal) -> None:
        """Draws the window of `portal` if its ring is in view. Call with the depth test off, before the ring's band."""
        if PortalWindow._has_stencil is None:
            PortalWindow._has_stencil = GL.glGetIntegerv(GL.GL_STENCIL_BITS) > 0
        if not PortalWindow._has_stencil:
            return
        arrival = portal.other_end(environment.galaxy)
        if arrival is None:
            return
        date_time = environment.date_time
        position = ship.navigation.stellar_position(date_time)
        to_centre = portal.centre - position
        distance = to_centre.length()
        view_height, _, focal = view_geometry(height)
        if distance == 0.0 or 2.0 * portal.RADIUS * focal / distance < MIN_VISIBLE_PX:
            return
        points = portal.ring_points(DISC_SEGMENTS) - np.array(tuple(position))  # the ring's rim from the ship
        forward = ship.attitude.forward
        if float((points @ np.array(tuple(forward))).max()) <= NEAR_CLIP and to_centre.dot(forward) <= NEAR_CLIP:
            return  # all of it behind the ship

        # The view from the other end: the same place relative to its ring, looking the same way relative to it.
        attitude = Attitude(ship)
        attitude.right = portal.carry(arrival, ship.attitude.right)
        attitude.up = portal.carry(arrival, ship.attitude.up)
        attitude.forward = portal.carry(arrival, ship.attitude.forward)
        seen_from = arrival.centre + portal.carry(arrival, position - portal.centre)
        star = arrival.base.stellar_system.star

        PortalWindow._mask(width, height, view_height, ship, to_centre, points, distance + 3.0 * portal.RADIUS)
        GL.glStencilFunc(GL.GL_EQUAL, 1, 0xFF)
        GL.glStencilOp(GL.GL_KEEP, GL.GL_KEEP, GL.GL_KEEP)
        PortalWindow._blank(width, height)
        MilkyWay.draw(width, height, ship, date_time, attitude)
        DistantStars.draw_window(width, height,
                                 DistantStars.dots_seen_from(environment, star, seen_from, attitude, width, height))
        view = view_from(star, -seen_from, attitude, width, height)
        if view is not None:
            StarGl.draw_star(width, height, view, (date_time - environment.EPOCH).total_seconds(),
                             ship.owner.time_scale)
        GL.glDisable(GL.GL_STENCIL_TEST)

    @staticmethod
    def _mask(width: int, height: int, view_height: int, ship: Ship, to_centre: Vector3, points: np.ndarray,
              far: float) -> None:
        """Marks the ring's disc in the stencil (the 3D pass clips what is behind the ship or beyond the window), and
        leaves the stencil test on."""
        GL.glEnable(GL.GL_STENCIL_TEST)
        GL.glStencilMask(0xFF)
        GL.glClearStencil(0)
        GL.glClear(GL.GL_STENCIL_BUFFER_BIT)
        GL.glStencilFunc(GL.GL_ALWAYS, 1, 0xFF)
        GL.glStencilOp(GL.GL_KEEP, GL.GL_KEEP, GL.GL_REPLACE)
        GL.glColorMask(GL.GL_FALSE, GL.GL_FALSE, GL.GL_FALSE, GL.GL_FALSE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GLU.gluPerspective(math.degrees(VIEW_VERTICAL_FOV_RADIANS), width / view_height, 0.05, far)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glMultMatrixf(ship.attitude.camera_matrix())
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex3f(to_centre.x, to_centre.y, to_centre.z)
        for x, y, z in np.vstack([points, points[:1]]):
            GL.glVertex3f(x, y, z)
        GL.glEnd()
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glColorMask(GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE)
        GL.glViewport(0, 0, width, height)

    @staticmethod
    def _blank(width: int, height: int) -> None:
        """Paints the whole window with the colour of empty space (the stencil keeps it to the disc)."""
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, width, height, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glDisable(GL.GL_BLEND)
        GL.glColor3f(SPACE_COLOR[0] / 255.0, SPACE_COLOR[1] / 255.0, SPACE_COLOR[2] / 255.0)
        GL.glBegin(GL.GL_QUADS)
        for x, y in ((0, 0), (width, 0), (width, height), (0, height)):
            GL.glVertex2f(x, y)
        GL.glEnd()
        GL.glColor4f(1.0, 1.0, 1.0, 1.0)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
