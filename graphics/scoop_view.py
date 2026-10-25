"""The scoop's view: what is under the ship, seen from its belly, in the scanner's place."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple
import numpy as np
import pygame
from OpenGL import GL

from .asteroids import Asteroids
from spaceships.ship import Ship
from .constants import SCOOP_FOV_DEGREES
from .rocks import Rocks

if TYPE_CHECKING:
    from galaxies.km2 import Km2
    from galaxies.outpost import Outpost
    from game_environment import GameEnvironment
    from spaceships.ship import Ship
    from .asteroids import Sighting
    from .surface_light import SurfaceLight

LAMP_REACH = 0.6  # the spread of each corner lamp's light (a Gaussian's sigma), in half sides of the square
LAMP_FLOOR = 0.5  # the share of the light that reaches the middle of the square whatever the lamps do


class ScoopView:
    """A square view looking down (Attitude.down_camera_matrix), drawn by OpenGLGui after the cockpit, over the
    square that `Scanner` leaves for it (`Scanner.scoop_rect`).

    The scoop is an open hole in the hull and shows only what its lamps reach: Ship.SCOOP_RANGE. Nothing of the sky is
    drawn: no stars, no worlds, no Milky Way, no sun. Bound, it is the ground and what is on it (rocks, ore fields,
    mines, outposts) within that range, lit from above by the lamps whatever the time of day (`SurfaceLight.lamp`),
    which also says how high the ship is: the ground appears as it comes within reach. Unbound, it is the asteroids
    within that range. What is near fades to black towards the range (fog), and a mask of four lobes of light, one
    from each corner of the hole, covers the picture. Only the nearest Km2s are given to the rock batches, which the
    canopy's pass has already built, so the view costs little.
    """

    _mask_texture: Optional[int] = None
    _mask_size: int = 0

    @staticmethod
    def draw(rect: pygame.Rect, window_size: Tuple[int, int], ship: Ship, environment: GameEnvironment,
             km2s: Optional[List[Km2]], outposts: List[Outpost], light: Optional[SurfaceLight],
             sightings: List[Sighting]) -> None:
        """Draws the view in `rect` (software coordinates). `km2s`, `outposts` and `light` are the canopy's, None or
        empty when it has no rocks to draw; `sightings` are the asteroids it sought while unbound."""
        width, height = window_size
        viewport = (rect.left, height - rect.bottom, rect.width, rect.height)
        GL.glViewport(*viewport)
        GL.glEnable(GL.GL_SCISSOR_TEST)
        GL.glScissor(*viewport)
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_FOG)
        GL.glFogi(GL.GL_FOG_MODE, GL.GL_LINEAR)
        GL.glFogf(GL.GL_FOG_START, Ship.SCOOP_RANGE * 0.3)
        GL.glFogf(GL.GL_FOG_END, Ship.SCOOP_RANGE)
        GL.glFogfv(GL.GL_FOG_COLOR, (0.0, 0.0, 0.0, 1.0))
        if ship.is_bound:
            if km2s is not None and light is not None and ship.position.y <= Ship.SCOOP_RANGE:
                ScoopView._draw_surface(viewport, ship, environment, km2s, outposts, light)
        else:
            Asteroids.draw_near(ship, environment, sightings, Ship.SCOOP_RANGE, SCOOP_FOV_DEGREES, 1.0)
        GL.glDisable(GL.GL_FOG)
        ScoopView._draw_lamps(viewport)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glViewport(0, 0, width, height)

    @staticmethod
    def _draw_surface(viewport: Tuple[int, int, int, int], ship: Ship, environment: GameEnvironment, km2s: List[Km2],
                      outposts: List[Outpost], light: SurfaceLight) -> None:
        """The ground and what is on it within Ship.SCOOP_RANGE of the ship, lit by the lamps."""
        x, z = ship.position.x, ship.position.z
        near = [km2 for km2 in km2s
                if km2.longitude - Ship.SCOOP_RANGE <= x < km2.longitude + km2.SIZE + Ship.SCOOP_RANGE
                and km2.latitude - Ship.SCOOP_RANGE <= z < km2.latitude + km2.SIZE + Ship.SCOOP_RANGE]
        ore_fields = [field for km2 in near for field in km2.ore_fields + km2.external_fields]
        Rocks.draw_view(viewport, SCOOP_FOV_DEGREES, Ship.SCOOP_RANGE, ship.attitude.down_camera_matrix(), ship, near,
                        ore_fields, [mine for field in ore_fields for mine in field.mines], outposts,
                        light.lit_by_lamps(), environment.date_time)

    @staticmethod
    def lamp_mask(size: int) -> np.ndarray:
        """(size, size, 4) uint8: black, opaque where the lamps' light does not reach. Four lobes, one from each
        corner, meeting in the middle at LAMP_FLOOR to 1 of the light."""
        axis = (np.arange(size) + 0.5) / size * 2.0 - 1.0
        x, y = np.meshgrid(axis, axis)
        glow = sum(np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * LAMP_REACH ** 2))
                   for cx in (-1.0, 1.0) for cy in (-1.0, 1.0))
        light = LAMP_FLOOR + (1.0 - LAMP_FLOOR) * np.minimum(1.0, glow)
        mask = np.zeros((size, size, 4), dtype=np.uint8)
        mask[..., 3] = ((1.0 - light) * 255.0).astype(np.uint8)
        return mask

    @staticmethod
    def _draw_lamps(viewport: Tuple[int, int, int, int]) -> None:
        """The mask of the lamps over the view, which is the current viewport. It is made again when the square's
        size changes."""
        size = viewport[2]
        if ScoopView._mask_texture is None:
            ScoopView._mask_texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, ScoopView._mask_texture)
        if ScoopView._mask_size != size:
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, size, size, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE,
                            ScoopView.lamp_mask(size))
            ScoopView._mask_size = size
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, 1, 1, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glColor4f(1.0, 1.0, 1.0, 1.0)
        GL.glBegin(GL.GL_QUADS)
        for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
            GL.glTexCoord2f(u, v)
            GL.glVertex2f(u, v)
        GL.glEnd()
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glDisable(GL.GL_TEXTURE_2D)
