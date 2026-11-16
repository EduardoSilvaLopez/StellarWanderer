"""Depth-tested OpenGL rock rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple
import math

import numpy as np
from OpenGL import GL, GLU

from common.frame_watch import frame_watch
from .constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH, SHADOWS_BELOW_TIME_SCALE
from .ore_fields import OreFields
from .ore_mines import OreMines
from .outposts import Outposts
from .rock_batches import RockBatches
from .shadow_map import ShadowMap
from .shadowed_surface import ShadowedSurface
from .surface_light import SurfaceLight
from .terrain_gl import TerrainGl

if TYPE_CHECKING:
    from datetime import datetime
    from spaceships.ship import Ship
    from galaxies.km2 import Km2
    from galaxies.ore_fields import OreField
    from galaxies.ore_mine import OreMine
    from galaxies.outpost import Outpost


class Rocks:
    """Render world-aligned rocks using the OpenGL depth buffer."""

    @staticmethod
    def draw(width: int, height: int, ship: Ship, km2s: List[Km2], ore_fields: List[OreField], mines: List[OreMine],
             outposts: List[Outpost], light: SurfaceLight, game_date_time: datetime) -> None:
        """Draw the rocks of `km2s` (cached batches, see rock_batches.py) and the rest of the surface in a
        perspective OpenGL pass.

        A depth buffer, rather than face-selection heuristics, decides which
        projected face is visible at each pixel.
        """
        view_height = int(height * CONSOLE_TOP)
        # OpenGL's origin is bottom-left; the canopy is the top part of the
        # Pygame frame, so position this 3D viewport above the cockpit panel.
        Rocks.draw_view((0, height - view_height, width, view_height), math.degrees(VIEW_VERTICAL_FOV_RADIANS),
                        MAX_DEPTH, ship.attitude.camera_matrix(), ship, km2s, ore_fields, mines, outposts, light,
                        game_date_time)

    @staticmethod
    def draw_view(viewport: Tuple[int, int, int, int], fov_degrees: float, far: float, camera_matrix: list, ship: Ship,
                  km2s: List[Km2], ore_fields: List[OreField], mines: List[OreMine], outposts: List[Outpost],
                  light: SurfaceLight, game_date_time: datetime) -> None:
        """The same, in `viewport` (x, y, width, height, from the window's bottom left), with the given vertical field
        of view, far plane and camera matrix (see Attitude.camera_matrix): the canopy's, or the scoop's."""
        GL.glViewport(*viewport)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GLU.gluPerspective(fov_degrees, viewport[2] / viewport[3], max(0.1, NEAR_CLIP), far)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        # Maps the ship's right/up/forward axes onto OpenGL's eye axes (looking down -Z).
        GL.glMultMatrixf(camera_matrix)
        # X/Z are NOT translated here: at large enough world coordinates (far
        # from the origin), glTranslatef's float32 truncation would already
        # have destroyed sub-meter precision before the GPU ever sees it.
        # Instead, every vertex below is made camera-relative in Python
        # (double precision) before being handed to glVertex3f, so only
        # small, already-precise offsets ever get truncated to float32.
        # Y doesn't need this treatment: while bound, ship.position.y runs from
        # Ship.HEIGHT up to (UNBIND_RADIUS_MULTIPLE - 1) x radius, about 1,200 km at most
        # on an earthlike planet, where float32 still resolves about 0.1 m.
        rotation = np.array(GL.glGetFloatv(GL.GL_MODELVIEW_MATRIX), dtype=np.float64).T[:3, :3]
        GL.glTranslatef(0.0, -ship.position.y, 0.0)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        import game_environment as gem
        world = gem.current_environment.fixed_world
        import galaxies.people.player as player_module
        shadows = not light.lamp and player_module.current_player.time_scale < SHADOWS_BELOW_TIME_SCALE

        def casters(shadow: ShadowMap, cascade: int) -> None:
            Rocks._cast(shadow, cascade, ship, km2s, outposts, light)

        if world is None or not TerrainGl.draw(world, ship, light, shadows, casters):  # relief draws its own ground
            Rocks._draw_ground(light)
        frame_watch.mark('ground')

        OreFields.draw(ore_fields, ship.position.x, ship.position.z, light)
        OreMines.draw(mines, ship.position.x, ship.position.z, light, game_date_time)
        shadow = TerrainGl.shadow_map()
        with ShadowedSurface.receiving(shadow, light, rotation, textured=True):
            Outposts.draw(outposts, ship.position.x, ship.position.z, light)
        frame_watch.mark('ore fields, mines, outposts')

        RockBatches.draw(km2s, ship.position.x, ship.position.z, light, ship.position.y, shadow, rotation)
        frame_watch.mark('rocks')

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    @staticmethod
    def _cast(shadow: ShadowMap, cascade: int, ship: Ship, km2s: List[Km2], outposts: List[Outpost],
              light: SurfaceLight) -> None:
        """What stands on the ground, drawn into a cascade of the shadow map: the rocks of the Km2s and the outposts
        that its square can see, in the light's view (the vertices are made relative to the camera, as in the view)."""
        x, y, z = ship.position.x, ship.position.y, ship.position.z
        ground = ship.navigation.ground_height_at(x, z) - y
        spots = list(km2s)
        km2_centres = np.array([(k.longitude + k.SIZE / 2 - x, ground, k.latitude + k.SIZE / 2 - z) for k in spots])
        near_km2s = ([k for k, taken in zip(spots, shadow.covers(cascade, km2_centres, np.full(len(spots), 1500.0)))
                      if taken] if spots else [])
        near_outposts = []
        if outposts:
            centres = np.array([(o.longitude - x, o.ground_height - y, o.latitude - z) for o in outposts])
            seen = shadow.covers(cascade, centres, np.full(len(outposts), 120.0))
            near_outposts = [o for o, taken in zip(outposts, seen) if taken]
        if not near_km2s and not near_outposts:
            return
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadMatrixf(np.ascontiguousarray(shadow.render_matrices[cascade].T, dtype=np.float32))
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glTranslatef(0.0, -y, 0.0)
        RockBatches.cast(near_km2s, x, z, shadow.render_matrices[cascade], y)
        Outposts.draw(near_outposts, x, z, light)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_MODELVIEW)

    @staticmethod
    def _draw_ground(light: SurfaceLight) -> None:
        """Draw the local surface lit by the sun, populating depth for rocks to sit on.

        Always centred on the camera (player X/Z is applied via the
        camera-relative vertex convention, not baked into these vertices),
        so this needs no player position at all.
        """
        extent = MAX_DEPTH

        GL.glColor3ub(*light.ground_colour())
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(-extent, 0.0, -extent)
        GL.glVertex3f(extent, 0.0, -extent)
        GL.glVertex3f(extent, 0.0, extent)
        GL.glVertex3f(-extent, 0.0, extent)
        GL.glEnd()
