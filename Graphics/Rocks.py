"""Depth-tested OpenGL rock rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple
import math

from OpenGL import GL, GLU

from .Constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH, PLANET_GRAY
from .OreFields import OreFields
from .OreMines import OreMines

if TYPE_CHECKING:
    from Player import Player
    from Galaxies.Rock import Rock
    from Galaxies.OreField import OreField
    from Galaxies.OreMine import OreMine


class Rocks:
    """Render world-aligned rocks using the OpenGL depth buffer."""

    @staticmethod
    def draw(width: int, height: int, player: Player, rocks: List[Rock], ore_fields: List[OreField], mines: List[OreMine]) -> None:
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
        # X/Z are NOT translated here: at large enough world coordinates (far
        # from the origin), glTranslatef's float32 truncation would already
        # have destroyed sub-meter precision before the GPU ever sees it.
        # Instead, every vertex below is made camera-relative in Python
        # (double precision) before being handed to glVertex3f, so only
        # small, already-precise offsets ever get truncated to float32.
        # Y doesn't need this treatment: player.position.y is bounded to
        # [ship.HEIGHT, Player.MAX_ALTITUDE] = [10, 20000], far too small for
        # float32 to meaningfully round.
        GL.glTranslatef(0.0, -player.position.y, 0.0)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        Rocks._draw_ground()

        OreFields.draw(ore_fields, player.position.x, player.position.z)
        OreMines.draw(mines, player.position.x, player.position.z)

        for rock in rocks:
            Rocks._draw_rock(rock, player.position.x, player.position.z)

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    @staticmethod
    def _draw_ground() -> None:
        """Draw the local surface in the planet colour, populating depth for rocks to sit on.

        Always centred on the camera (player X/Z is applied via the
        camera-relative vertex convention, not baked into these vertices),
        so this needs no player position at all.
        """
        extent = MAX_DEPTH

        GL.glColor3ub(*PLANET_GRAY)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(-extent, 0.0, -extent)
        GL.glVertex3f(extent, 0.0, -extent)
        GL.glVertex3f(extent, 0.0, extent)
        GL.glVertex3f(-extent, 0.0, extent)
        GL.glEnd()

    @staticmethod
    def _draw_rock(rock: Rock, player_x: float, player_z: float) -> None:
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

        # Subtract the player's position here, in double precision, before
        # these coordinates ever reach a float32 glVertex3f call — see the
        # comment in draw() for why.
        relative_longitude = rock.longitude - player_x
        relative_latitude = rock.latitude - player_z

        def corner(sign_x: int, sign_y: int, sign_z: int) -> Tuple[float, float, float]:
            local_x, local_y, local_z = sign_x * half, sign_y * half, sign_z * half
            x1 = local_x * cos_t - local_y * sin_t
            y1 = local_x * sin_t + local_y * cos_t
            z1 = local_z
            x2 = x1 * cos_o + z1 * sin_o
            z2 = -x1 * sin_o + z1 * cos_o
            return (relative_longitude + x2, rock.altitude + y1, relative_latitude + z2)

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
