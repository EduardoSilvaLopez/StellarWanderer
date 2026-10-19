"""The far background of the sky: the Milky Way, Andromeda and the Magellanic Clouds, where they really are.

The picture is a panorama made by tools/generate_milky_way.py: equirectangular, in galactic coordinates (the centre of the picture
is galactic longitude 0, the top is the north galactic pole). It is drawn in OpenGL, as a textured sphere around the camera,
before the sun and under the sky layer (`OpenGLGui.draw`), which is transparent where there is nothing: the GPU does the work,
and a frame costs one display list.

Where things are: the stellar frame (x right, y up, z forward) is the galactic frame turned, with the initial star as origin
(galaxies/fixed_stars.py): the galactic centre is straight to -z, the north galactic pole is +y, and a direction at galactic
longitude l and latitude b is (cos b sin l, sin b, -cos b cos l). The sky is so far away that it is the same for every
system of the region. Unbound, the sphere stays in the stellar frame; bound, it is turned into the surface frame by
`Navigation.sky_rotation`, so it moves with the world's spin and the ship's place on it.

The picture's brightness is the real one in ratios, not in absolute terms (see MILKY_WAY_EXPOSURE in constants.py).
"""

from __future__ import annotations
import math
from typing import Optional, TYPE_CHECKING

import pygame
from OpenGL import GL, GLU

from common.paths import resource_path
from .constants import CONSOLE_TOP, MAX_DEPTH, MILKY_WAY_EXPOSURE, NEAR_CLIP, VIEW_VERTICAL_FOV_RADIANS

if TYPE_CHECKING:
    from datetime import datetime
    from spaceships.ship import Ship

PANORAMA_PATH = resource_path('textures', 'milky_way.png')
SPHERE_RADIUS = 1000.0  # between the near and far planes: it only has to enclose the camera
LONGITUDE_STEPS = 128
LATITUDE_STEPS = 64


class MilkyWay:
    """Draws the panorama on a sphere. The texture and the sphere are made on the first frame; with no picture, nothing is drawn."""

    _texture: Optional[int] = None
    _sphere: Optional[int] = None  # a display list
    _failed: bool = False

    @staticmethod
    def draw(width: int, height: int, ship: Ship, date_time: datetime) -> None:
        """Draw the sky's background into the canopy part of the window, in the colours that are already there (the clear colour)."""
        if MILKY_WAY_EXPOSURE <= 0.0 or not MilkyWay._ready():
            return
        view_height = int(height * CONSOLE_TOP)
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GLU.gluPerspective(math.degrees(VIEW_VERTICAL_FOV_RADIANS), width / view_height, max(0.1, NEAR_CLIP), MAX_DEPTH)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glMultMatrixf(ship.attitude.camera_matrix())
        # The sphere is in the stellar frame; its axes' images in the active frame are the columns of this matrix.
        x_axis, y_axis, z_axis = ship.navigation.sky_rotation(date_time)
        GL.glMultMatrixf([
            x_axis.x, x_axis.y, x_axis.z, 0.0,
            y_axis.x, y_axis.y, y_axis.z, 0.0,
            z_axis.x, z_axis.y, z_axis.z, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ])

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, MilkyWay._texture)
        GL.glColor3f(MILKY_WAY_EXPOSURE, MILKY_WAY_EXPOSURE, MILKY_WAY_EXPOSURE)  # the texture is multiplied by the colour
        GL.glCallList(MilkyWay._sphere)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glColor4f(1.0, 1.0, 1.0, 1.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    @staticmethod
    def _ready() -> bool:
        """True when the texture and the sphere exist, making them the first time. False (for good) if the picture is missing."""
        if MilkyWay._failed:
            return False
        if MilkyWay._texture is None:
            try:
                image = pygame.image.load(PANORAMA_PATH)
            except (FileNotFoundError, pygame.error):
                MilkyWay._failed = True
                return False
            MilkyWay._texture = MilkyWay._make_texture(image)
            MilkyWay._sphere = MilkyWay._make_sphere()
        return True

    @staticmethod
    def _make_texture(image: pygame.Surface) -> int:
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)  # the picture wraps round at the anticentre
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        width, height = image.get_size()
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGB, width, height, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE,
            pygame.image.tostring(image.convert(24), 'RGB', False),  # the first row is the north pole, at t = 0
        )
        return texture

    @staticmethod
    def _make_sphere() -> int:
        """A display list: a sphere in the stellar frame, with the panorama's texture coordinates (u from the galactic longitude,
        -180 to 180 degrees, v from the latitude, the north pole first)."""
        sphere = int(GL.glGenLists(1))
        GL.glNewList(sphere, GL.GL_COMPILE)
        for row in range(LATITUDE_STEPS):
            GL.glBegin(GL.GL_QUAD_STRIP)
            for column in range(LONGITUDE_STEPS + 1):
                longitude = (column / LONGITUDE_STEPS - 0.5) * math.tau
                for latitude_index in (row, row + 1):
                    latitude = math.pi / 2 - latitude_index * math.pi / LATITUDE_STEPS
                    GL.glTexCoord2f(column / LONGITUDE_STEPS, latitude_index / LATITUDE_STEPS)
                    GL.glVertex3f(
                        SPHERE_RADIUS * math.cos(latitude) * math.sin(longitude),
                        SPHERE_RADIUS * math.sin(latitude),
                        -SPHERE_RADIUS * math.cos(latitude) * math.cos(longitude),
                    )
            GL.glEnd()
        GL.glEndList()
        return sphere
