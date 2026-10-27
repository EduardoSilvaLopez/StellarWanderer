"""The Portal in space (`Portal`): a ring of intense white light, drawn while the ship is unbound.

The light it gives is what the ring's angular radius says (`intensity`): nothing far away, full when the ring is big in
the sky. Three things follow from it, in the order of the frame:
  * the glare (`draw_glare`), over the sky and under everything that is drawn after it: a white glow round the ring and
    a black wash over the whole view, as strong as the light, whichever way the ship points: the eyes adapt, as
    behind sunglasses, and the stars and the planets (the sky) go dark. The portal base and the asteroids, which are
    drawn after it, are not darkened.
  * the ring (`draw`), in the 3D pass, with its own perspective as the base has: a band of white light with a halo,
    whose halo never gets narrower than a few pixels, so that it shows from afar as a glowing point. Its opening is
    drawn as the rest of the sky, from both sides.
  * the cockpit (`tint_cockpit`): white added to the opaque pixels of the cockpit, as the star's colour is
    (graphics/starlight.py).

Like the base, the ring is drawn from the camera's own frame: where it is in relation to the ship is worked out in
double precision before it goes to OpenGL.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pygame
from OpenGL import GL, GLU

from .constants import NEAR_CLIP, VIEW_VERTICAL_FOV_RADIANS
from .instruments.common import view_geometry
from .portal_base_gl import PortalBaseGl

if TYPE_CHECKING:
    from galaxies.portals.portal import Portal
    from game_environment import GameEnvironment
    from spaceships.ship import Ship

LIGHT_COLOUR = (235, 242, 255)  # the Portal's light: white, a little cold


class PortalGl:
    """Draws the Portal of the ship's system."""

    RING_SEGMENTS = 128
    MIN_CORE_PIXELS = 1.5  # the ring's half width on the screen, however far
    # The layers of the ring's light, from the core to the widest halo: half width, in core widths, and strength.
    LAYERS = ((2.5, 1.0), (7.0, 0.55), (20.0, 0.28), (60.0, 0.14))
    HALO_MAX_SHARE = 0.25  # of the ring's radius: a halo is never wider than this
    GLOW_MIN_HALF_PX = 420.0  # the glow of a distant Portal, half of its size in pixels: a bright point
    GLARE_SIZE_OF_RING = 45.0  # the glow's half size, in radii of the ring on the screen
    GLARE_MAX_HALF_SHARE = 4.0  # of the window's width
    ANGLE_START = 0.0058  # rad, the ring's angular radius where its light begins to dazzle (a third of a degree)
    ANGLE_FULL = 0.102  # rad, where it dazzles fully (about 6 degrees)
    WASH_GAIN = 3.7  # the dark wash saturates at 1/WASH_GAIN of the light
    GLOW_STRENGTH = 0.3  # of the glow's brightness
    TINT_MAX = 115  # the most white added to the cockpit

    # region Light
    @staticmethod
    def intensity(portal: Portal, relative: np.ndarray) -> float:
        """How much the ring dazzles, 0 to 1, from the angle it covers in the sky: 0 for a ring seen under ANGLE_START,
        1 from ANGLE_FULL on (and inside it), in between smoothly. `relative` is the ring's centre from the ship."""
        distance = float(np.linalg.norm(relative))
        angle = math.pi / 2.0 if distance <= portal.RADIUS else math.asin(portal.RADIUS / distance)
        share = min(1.0, max(0.0, (angle - PortalGl.ANGLE_START) / (PortalGl.ANGLE_FULL - PortalGl.ANGLE_START)))
        return share * share * (3.0 - 2.0 * share)

    @staticmethod
    def _relative_centre(portal: Portal, ship: Ship, environment: GameEnvironment) -> np.ndarray:
        position = ship.navigation.stellar_position(environment.date_time)
        centre = portal.centre
        return np.array([centre.x - position.x, centre.y - position.y, centre.z - position.z])

    @staticmethod
    def tint_cockpit(overlay: pygame.Surface, environment: GameEnvironment, ship: Ship) -> None:
        """White added to the opaque cockpit pixels, as much as the light says (the transparent panes stay so)."""
        if ship.is_bound:
            return
        portal = environment.nearest_system.portal
        level = PortalGl.intensity(portal, PortalGl._relative_centre(portal, ship, environment))
        added = int(PortalGl.TINT_MAX * level)
        if added > 0:
            overlay.fill((added, added, added), special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def is_behind_base(environment: GameEnvironment, ship: Ship) -> bool:
        """Whether the Portal is farther from the ship than the base: it is then drawn first, as the base is drawn over
        what is behind it."""
        system = environment.nearest_system
        position = ship.navigation.stellar_position(environment.date_time)
        portal_distance = (system.portal.centre - position).length()
        base_distance = (system.portal_base.stellar_position(environment.date_time) - position).length()
        return portal_distance > base_distance
    # endregion

    # region Glare
    @staticmethod
    def draw_glare(width: int, height: int, ship: Ship, environment: GameEnvironment) -> None:
        """The darkening wash and the glow, over the sky. Call with the depth test off, after the sky and before what
        must stay in front of it (the base)."""
        portal = environment.nearest_system.portal
        relative = PortalGl._relative_centre(portal, ship, environment)
        level = PortalGl.intensity(portal, relative)
        wash = min(1.0, PortalGl.WASH_GAIN * level)  # wherever the ship points: only the distance counts

        view_height, horizon_y, focal = view_geometry(height)
        right = float(relative @ np.array(tuple(ship.attitude.right)))
        up = float(relative @ np.array(tuple(ship.attitude.up)))
        forward = float(relative @ np.array(tuple(ship.attitude.forward)))
        glow = None
        if forward > NEAR_CLIP:
            distance = float(np.linalg.norm(relative))
            ring_px = focal * portal.RADIUS / math.sqrt(max(distance * distance - portal.RADIUS ** 2, 1.0))
            half = min(max(PortalGl.GLOW_MIN_HALF_PX, PortalGl.GLARE_SIZE_OF_RING * ring_px),
                       PortalGl.GLARE_MAX_HALF_SHARE * width)
            glow = (width / 2.0 + focal * right / forward, horizon_y - focal * up / forward, half)

        if wash <= 0.0 and glow is None:
            return
        _, sprite = PortalBaseGl.soft_textures()
        GL.glViewport(0, 0, width, height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, width, height, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)  # additive
        if wash > 0.0:
            GL.glDisable(GL.GL_TEXTURE_2D)
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)  # darkens
            GL.glColor4f(0.0, 0.0, 0.0, wash)
            GL.glBegin(GL.GL_QUADS)
            for x, y in ((0, 0), (width, 0), (width, height), (0, height)):
                GL.glVertex2f(x, y)
            GL.glEnd()
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)  # additive again
        if glow is not None:
            x, y, half = glow
            GL.glEnable(GL.GL_TEXTURE_2D)
            GL.glBindTexture(GL.GL_TEXTURE_2D, sprite)
            alpha = PortalGl.GLOW_STRENGTH * (0.35 + 0.65 * level)
            GL.glColor4f(LIGHT_COLOUR[0] / 255.0, LIGHT_COLOUR[1] / 255.0, LIGHT_COLOUR[2] / 255.0, alpha)
            GL.glBegin(GL.GL_QUADS)
            for u, v, dx, dy in ((0, 0, -1, -1), (1, 0, 1, -1), (1, 1, 1, 1), (0, 1, -1, 1)):
                GL.glTexCoord2f(u, v)
                GL.glVertex2f(x + dx * half, y + dy * half)
            GL.glEnd()
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)  # back to the blending the rest of the frame uses
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
    # endregion

    # region Ring
    @staticmethod
    def draw(width: int, height: int, ship: Ship, environment: GameEnvironment) -> None:
        """The ring, in the 3D pass, with its own perspective."""
        portal = environment.nearest_system.portal
        relative = PortalGl._relative_centre(portal, ship, environment)
        distance = float(np.linalg.norm(relative))
        if distance == 0.0:
            return
        position = np.array(tuple(ship.navigation.stellar_position(environment.date_time)))
        points = portal.ring_points(PortalGl.RING_SEGMENTS) - position  # the ring's centre line from the ship
        forward = np.array(tuple(ship.attitude.forward))
        if float((points @ forward).max()) <= NEAR_CLIP and float(relative @ forward) <= NEAR_CLIP:
            return  # all of it behind the ship

        view_height, _, focal = view_geometry(height)
        # The depth along the view direction is less than the distance for what is off-axis, so the near plane is kept
        # close (nothing is depth tested here) and the far one clears the ring and its widest halo.
        far = distance + (2.0 + PortalGl.HALO_MAX_SHARE) * portal.RADIUS
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GLU.gluPerspective(math.degrees(VIEW_VERTICAL_FOV_RADIANS), width / view_height, 0.05, far)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glMultMatrixf(ship.attitude.camera_matrix())
        GL.glDisable(GL.GL_DEPTH_TEST)

        PortalGl._draw_band(portal, points, focal)

        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glViewport(0, 0, width, height)

    @staticmethod
    def _draw_band(portal: Portal, points: np.ndarray, focal: float) -> None:
        """The band of light and its halos, as strips that face the camera, added to what is there."""
        count = len(points)
        angle = np.linspace(0.0, math.tau, count, endpoint=False)
        axis = np.array([0.0, 0.0, 1.0])
        tangent = np.array(tuple(portal.tangent))
        along = -np.sin(angle)[:, None] * axis + np.cos(angle)[:, None] * tangent  # the ring's direction at each point
        distance = np.linalg.norm(points, axis=1)
        side = np.cross(along, -points)  # across the band, facing the camera
        length = np.linalg.norm(side, axis=1)
        side = np.where(length[:, None] > 1e-9 * np.maximum(distance, 1.0)[:, None],
                        side / np.maximum(length, 1e-12)[:, None], axis[None, :])
        core = np.maximum(portal.BAND_THICKNESS / 2.0, PortalGl.MIN_CORE_PIXELS * distance / focal)  # (count,)

        positions, uvs, colours = [], [], []
        nxt = (np.arange(count) + 1) % count
        order = np.stack([np.arange(count), np.arange(count) + count, nxt, np.arange(count) + count,
                          nxt + count, nxt], axis=1).reshape(-1)  # two triangles for each segment
        corner_u = np.concatenate([np.zeros(count), np.ones(count)])
        light = np.array(LIGHT_COLOUR, np.float32) / 255.0
        for factor, strength in PortalGl.LAYERS:
            half = np.minimum(core * factor, np.maximum(PortalGl.HALO_MAX_SHARE * portal.RADIUS, core))
            vertices = np.concatenate([points - side * half[:, None], points + side * half[:, None]])
            positions.append(vertices[order])
            uvs.append(np.stack([corner_u, np.full(2 * count, 0.5)], axis=1)[order])
            rgba = np.empty((2 * count, 4), np.float32)
            rgba[:, :3] = light
            rgba[:, 3] = strength
            colours.append(rgba[order])
        positions = np.ascontiguousarray(np.concatenate(positions), np.float32)
        uvs = np.ascontiguousarray(np.concatenate(uvs), np.float32)
        colours = np.ascontiguousarray(np.concatenate(colours), np.float32)

        gradient, _ = PortalBaseGl.soft_textures()
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, gradient)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)  # additive
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, positions)
        GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, uvs)
        GL.glColorPointer(4, GL.GL_FLOAT, 0, colours)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(positions))
        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
    # endregion
