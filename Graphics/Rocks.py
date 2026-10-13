"""Depth-tested OpenGL rock rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List
import math

from OpenGL import GL, GLU

from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH
from .OreFields import OreFields
from .OreMines import OreMines
from .outposts import Outposts
from .rock_batches import RockBatches
from .surface_light import SurfaceLight

if TYPE_CHECKING:
    from Galaxies.People.player import Player
    from Galaxies.km2 import Km2
    from Galaxies.ore_fields import OreField
    from Galaxies.ore_mine import OreMine
    from Galaxies.outpost import Outpost


class Rocks:
    """Render world-aligned rocks using the OpenGL depth buffer."""

    @staticmethod
    def draw(width: int, height: int, player: Player, km2s: List[Km2], ore_fields: List[OreField], mines: List[OreMine],
             outposts: List[Outpost], light: SurfaceLight) -> None:
        """Draw the rocks of `km2s` (cached batches, see rock_batches.py) and the rest of the surface in a
        perspective OpenGL pass.

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
        # Maps the ship's right/up/forward axes onto OpenGL's eye axes (looking down -Z).
        GL.glMultMatrixf(player.camera_matrix())
        # X/Z are NOT translated here: at large enough world coordinates (far
        # from the origin), glTranslatef's float32 truncation would already
        # have destroyed sub-meter precision before the GPU ever sees it.
        # Instead, every vertex below is made camera-relative in Python
        # (double precision) before being handed to glVertex3f, so only
        # small, already-precise offsets ever get truncated to float32.
        # Y doesn't need this treatment: while bound, player.position.y runs from
        # Ship.HEIGHT up to (UNBIND_RADIUS_MULTIPLE - 1) x radius, about 1,200 km at most
        # on an earthlike planet, where float32 still resolves about 0.1 m.
        GL.glTranslatef(0.0, -player.position.y, 0.0)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        Rocks._draw_ground(light)

        OreFields.draw(ore_fields, player.position.x, player.position.z, light)
        OreMines.draw(mines, player.position.x, player.position.z, light)
        Outposts.draw(outposts, player.position.x, player.position.z, light)

        RockBatches.draw(km2s, player.position.x, player.position.z, light)

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

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
