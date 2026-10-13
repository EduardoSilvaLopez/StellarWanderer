"""Depth-tested OpenGL rock rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple
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
    from Galaxies.rock import Rock
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

    @staticmethod
    def _draw_rock(rock: Rock, player_x: float, player_z: float, light: SurfaceLight) -> None:
        """One rock, drawn immediately. Not used in the game any more: RockBatches draws the rocks. It stays as
        the reference that a batch must reproduce (vertices and colours), for tests."""
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

        # The heat glow (rock.color above rock.initial_color) is added after shading, so a hot rock still
        # glows on the side away from the sun.
        glow = tuple(max(0, now - start) for now, start in zip(rock.color, rock.initial_color))

        def face_colour(normal_x: float, normal_y: float, normal_z: float) -> Tuple[int, int, int]:
            """The face's colour: its normal rotated like the corners (tilt, then orientation), lit by the sun."""
            x1 = normal_x * cos_t - normal_y * sin_t
            y1 = normal_x * sin_t + normal_y * cos_t
            x2 = x1 * cos_o + normal_z * sin_o
            z2 = -x1 * sin_o + normal_z * cos_o
            shaded = SurfaceLight.shade(rock.initial_color, light.brightness(x2, y1, z2))
            return tuple(min(255, shaded[i] + glow[i]) for i in range(3))

        faces = (
            (face_colour(0.0, 1.0, 0.0), (c010, c110, c111, c011)),
            (face_colour(0.0, -1.0, 0.0), (c001, c101, c100, c000)),
            (face_colour(-1.0, 0.0, 0.0), (c000, c001, c011, c010)),
            (face_colour(1.0, 0.0, 0.0), (c101, c100, c110, c111)),
            (face_colour(0.0, 0.0, -1.0), (c000, c100, c110, c010)),
            (face_colour(0.0, 0.0, 1.0), (c101, c001, c011, c111)),
        )

        GL.glBegin(GL.GL_QUADS)
        for color, vertices in faces:
            GL.glColor3ub(*color)
            for vertex in vertices:
                GL.glVertex3f(*vertex)
        GL.glEnd()
