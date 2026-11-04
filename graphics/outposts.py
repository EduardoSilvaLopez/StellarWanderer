"""Textured OpenGL outpost buildings: flat boxes with a door on one long wall (common/resources/textures/outpost.png).

The atlas layout is described in tools/generate_outpost_texture.py. The door faces the outpost's
orientation (degrees clockwise from north, as for rocks and mines), so local +z is the door wall.

The building is 24 m x 12 m x 6 m (Outpost.WIDTH/DEPTH/HEIGHT), two levels of 3 m with the ledge at 3 m. The texture
is for a world without air or water: lightly weathered composite cladding (dust and micrometeorite pits, no rain or
rust), a red band at the ledge, lit and dark windows, round portholes, a sealed airlock in the middle of the door
wall, docking collars, thermal radiator panels, gold insulation foil, thruster clusters, EVA handrails, a sensor dome,
and solar panels and a dish on the roof. Do not add vents, fans or drain pipes.

A real 3D flagpole stands on the front left corner of the roof and rises POLE_RISE (5 m) above it, past HEIGHT, with
a rigid flag (a flag cannot wave in vacuum) held out by a rod, drawn on both faces from the FLAG region. The pole is
only drawn: the scanner's box, HEIGHT and CLEARED_RADIUS do not include it.

Windows, lamps and indicator lights are painted after the weathering, so they stay bright; at night they dim with the
rest, as the lighting is applied by vertex colour. To regenerate the texture: python tools/generate_outpost_texture.py
(numpy + pygame, seeded, so the result is repeatable; the previous texture is kept as outpost.Backup.png).

From Outpost.PAD_FROM_SIZE the ground under the building is a flat concrete square, with the building in one corner, and
a dark ring painted on it, the landing pad. The concrete is a public domain photo
(common/resources/textures/concrete.png), mirrored over the square, two metres to a tile. The pad is drawn first, on
the ground in the outpost's frame, before the buildings.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
import math
import logging
import os

import pygame
from OpenGL import GL, GLU
from common.frame_watch import frame_watch
from common.paths import resource_path

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from .surface_light import SurfaceLight

logger = logging.getLogger(__name__)

ATLAS_WIDTH = 2048
ATLAS_HEIGHT = 1024
TEXTURE_PATH = resource_path('textures', 'outpost.png')

# Atlas regions (x, y, w, h) in pixels; must match tools/generate_outpost_texture.py.
FRONT = (0, 0, 960, 240)
BACK = (0, 248, 960, 240)
LEFT = (976, 0, 480, 240)
RIGHT = (976, 248, 480, 240)
ROOF = (0, 496, 960, 480)
FLAG = (1472, 0, 384, 256)  # the flag, 3:2
METAL = (1472, 264, 32, 32)  # plain steel, for the flagpole and its fittings

# The flagpole stands on the front left corner of the roof and rises above it. It is only drawn: the
# outpost's HEIGHT, its box for the scanner and the cleared ground do not include it.
POLE_RISE = 5.0  # metres above the roof
POLE_HALF_WIDTH = 0.07  # the pole is a square 0.14 m across
POLE_INSET = 0.8  # from the corner of the roof
FLAG_WIDTH = 3.0  # a rigid flag, held out by a rod (a flag cannot wave without air)
FLAG_HEIGHT = 2.0

# The ground of the pad, lifted a little so it does not fight the terrain nor the ring.
SQUARE_LIFT = 0.02  # metres
RING_LIFT = 0.04
CONCRETE_PATH = resource_path('textures', 'concrete.png')  # a public domain photo of concrete
CONCRETE_TILE_METRES = 2.0  # the photo's width on the ground, repeated over the square
RING_COLOUR = (38, 38, 40)  # very dark grey, painted on the concrete
RING_SEGMENTS = 96


class Outposts:
    """Render outpost buildings within the camera transform set up by the caller (see Rocks.draw).
    Each face is lit by the sun from its own normal (see SurfaceLight)."""

    _texture_id: Optional[int] = None
    _concrete_texture_id: Optional[int] = None

    @staticmethod
    def draw(outposts: List[Outpost], player_x: float, player_z: float, light: SurfaceLight) -> None:
        if not outposts:
            return
        pads = [outpost for outpost in outposts if outpost.has_pad]
        if pads:
            GL.glEnable(GL.GL_TEXTURE_2D)
            GL.glBindTexture(GL.GL_TEXTURE_2D, Outposts._get_concrete_texture())
            for outpost in pads:
                Outposts._draw_pad(outpost, player_x, player_z, light)
            GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, Outposts._get_texture())
        for outpost in outposts:
            Outposts._draw_outpost(outpost, player_x, player_z, light)
        GL.glDisable(GL.GL_TEXTURE_2D)

    @staticmethod
    def _corner_maker(outpost: Outpost, player_x: float,
                      player_z: float) -> Callable[[float, float, float], Tuple[float, float, float]]:
        """Maps the outpost's local coordinates (metres from its centre: x along the width, z on the door axis, y up)
        to the view. The camera is subtracted in double precision, before glVertex3f (see Rocks.draw)."""
        angle = math.radians(outpost.orientation)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        origin_x = outpost.longitude - player_x
        origin_z = outpost.latitude - player_z

        def corner(lx: float, ly: float, lz: float) -> Tuple[float, float, float]:
            x2 = lx * cos_a + lz * sin_a
            z2 = -lx * sin_a + lz * cos_a
            return (origin_x + x2, ly, origin_z + z2)
        return corner

    @staticmethod
    def _draw_pad(outpost: Outpost, player_x: float, player_z: float, light: SurfaceLight) -> None:
        """The concrete square, with the outpost in its corner, and the landing pad's ring on it."""
        corner = Outposts._corner_maker(outpost, player_x, player_z)
        up = light.brightness(0.0, 1.0, 0.0)
        left = -outpost.WIDTH / 2.0 - outpost.PAD_MARGIN
        back = -outpost.DEPTH / 2.0 - outpost.PAD_MARGIN
        side = outpost.PAD_SQUARE

        def vertex(lx: float, ly: float, lz: float) -> None:
            """A point of the pad: its texture coordinates are the metres from the square's corner, over the tile."""
            GL.glTexCoord2f((lx - left) / CONCRETE_TILE_METRES, (lz - back) / CONCRETE_TILE_METRES)
            GL.glVertex3f(*corner(lx, ly, lz))

        # The texture is modulated by the colour, so the light is the colour and the concrete is the texture.
        GL.glColor3ub(*light.shade((255, 255, 255), up))
        GL.glBegin(GL.GL_QUADS)
        for lx, lz in ((left, back), (left + side, back), (left + side, back + side), (left, back + side)):
            vertex(lx, SQUARE_LIFT, lz)
        GL.glEnd()

        centre_x = left + outpost.PAD_CENTRE[0]
        centre_z = back + outpost.PAD_CENTRE[1]
        inner = outpost.PAD_RADIUS - outpost.PAD_LINE / 2.0
        outer = outpost.PAD_RADIUS + outpost.PAD_LINE / 2.0
        GL.glColor3ub(*light.shade(RING_COLOUR, up))
        GL.glBegin(GL.GL_QUAD_STRIP)
        for step in range(RING_SEGMENTS + 1):
            cos_t = math.cos(2.0 * math.pi * step / RING_SEGMENTS)
            sin_t = math.sin(2.0 * math.pi * step / RING_SEGMENTS)
            vertex(centre_x + inner * cos_t, RING_LIFT, centre_z + inner * sin_t)
            vertex(centre_x + outer * cos_t, RING_LIFT, centre_z + outer * sin_t)
        GL.glEnd()

    @staticmethod
    def _draw_outpost(outpost: Outpost, player_x: float, player_z: float, light: SurfaceLight) -> None:
        width = outpost.WIDTH / 2.0
        depth = outpost.DEPTH / 2.0
        height = outpost.HEIGHT
        angle = math.radians(outpost.orientation)
        cos_a, sin_a = math.cos(angle), math.sin(angle)  # rotation, as in _corner_maker
        corner = Outposts._corner_maker(outpost, player_x, player_z)

        def quad(
                face: Tuple[int, int, int, int], normal: Tuple[float, float, float],
                points: List[Tuple[float, float, float]], uvs: List[Tuple[float, float]]
                ) -> None:
            u0, v0, u1, v1 = Outposts._uv_rect(face)
            # The outward normal of this face, in world terms, lit by the sun.
            GL.glColor3ub(*light.shade((255, 255, 255), light.brightness(*normal)))
            GL.glBegin(GL.GL_QUADS)
            for (x, y, z), (u, v) in zip(points, uvs):
                GL.glTexCoord2f(u0 + (u1 - u0) * u, v0 + (v1 - v0) * v)
                GL.glVertex3f(x, y, z)
            GL.glEnd()

        # Outward normals: local +z is (sin a, 0, cos a) in the world, with the same rotation as corner().
        door_normal = (sin_a, 0.0, cos_a)
        side_normal = (cos_a, 0.0, -sin_a)

        # Door wall: long side on local +z (the door faces `orientation`).
        quad(FRONT, door_normal,
             [corner(-width, 0, depth), corner(width, 0, depth), corner(width, height, depth),
              corner(-width, height, depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        # Back wall: long side on local -z, seen from outside, so mirrored in u.
        quad(BACK, (-sin_a, 0.0, -cos_a),
             [corner(width, 0, -depth), corner(-width, 0, -depth), corner(-width, height, -depth),
              corner(width, height, -depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        # Short walls, 6 m each.
        quad(LEFT, (-side_normal[0], 0.0, -side_normal[2]),
             [corner(-width, 0, depth), corner(-width, 0, -depth), corner(-width, height, -depth),
              corner(-width, height, depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        quad(RIGHT, side_normal,
             [corner(width, 0, -depth), corner(width, 0, depth), corner(width, height, depth),
              corner(width, height, -depth)],
             [(0, 1), (1, 1), (1, 0), (0, 0)])
        # Flat roof.
        quad(ROOF, (0.0, 1.0, 0.0),
             [corner(-width, height, depth), corner(width, height, depth), corner(width, height, -depth),
              corner(-width, height, -depth)],
             [(0, 0), (1, 0), (1, 1), (0, 1)])

        # Flagpole on the front left corner of the roof, with its flag held out to the right of the door wall.
        def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
            """A steel box in the building's local coordinates: four sides and the top."""
            def corners(*points: Tuple[float, float, float]) -> List[Tuple[float, float, float]]:
                return [corner(*point) for point in points]
            uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
            quad(METAL, door_normal, corners((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)), uvs)
            quad(METAL, (-sin_a, 0.0, -cos_a), corners((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)), uvs)
            quad(METAL, (-side_normal[0], 0.0, -side_normal[2]),
                 corners((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)), uvs)
            quad(METAL, side_normal, corners((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)), uvs)
            quad(METAL, (0.0, 1.0, 0.0), corners((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)), uvs)

        pole_x, pole_z = -width + POLE_INSET, depth - POLE_INSET
        pole_top = height + POLE_RISE
        half = POLE_HALF_WIDTH
        box(pole_x - 0.3, pole_x + 0.3, height, height + 0.12, pole_z - 0.3, pole_z + 0.3)  # base plate
        box(pole_x - half, pole_x + half, height, pole_top, pole_z - half, pole_z + half)  # pole
        box(pole_x - 0.1, pole_x + 0.1, pole_top, pole_top + 0.2, pole_z - 0.1, pole_z + 0.1)  # finial
        flag_top = pole_top - 0.25
        flag_x0, flag_x1 = pole_x + half, pole_x + half + FLAG_WIDTH
        box(flag_x0, flag_x1, flag_top, flag_top + 0.06, pole_z - 0.03, pole_z + 0.03)  # rod
        flag_bottom = flag_top - FLAG_HEIGHT
        # Both faces of the cloth, a hair apart so they do not fight; the back is seen mirrored, as on a real flag.
        for offset, normal, uvs in (
                (0.015, door_normal, [(0, 1), (1, 1), (1, 0), (0, 0)]),
                (-0.015, (-sin_a, 0.0, -cos_a), [(1, 1), (0, 1), (0, 0), (1, 0)])):
            quad(FLAG, normal,
                 [corner(flag_x0, flag_bottom, pole_z + offset), corner(flag_x1, flag_bottom, pole_z + offset),
                  corner(flag_x1, flag_top, pole_z + offset), corner(flag_x0, flag_top, pole_z + offset)],
                 uvs)

    @staticmethod
    def _uv_rect(region: Tuple[int, int, int, int]) -> Tuple[float, float, float, float]:
        """Texture coordinates of an atlas region: (u0, v0, u1, v1), with v = 0 at the first image row."""
        x, y, w, h = region
        return x / ATLAS_WIDTH, y / ATLAS_HEIGHT, (x + w) / ATLAS_WIDTH, (y + h) / ATLAS_HEIGHT

    @staticmethod
    def _get_concrete_texture() -> int:
        if Outposts._concrete_texture_id is None:
            with frame_watch.timed('concrete texture'):
                if os.path.exists(CONCRETE_PATH):
                    surface = pygame.image.load(CONCRETE_PATH).convert()
                else:
                    logger.error(f"Concrete texture missing: {CONCRETE_PATH}. Using a plain grey texture.")
                    surface = pygame.Surface((64, 64)).convert()
                    surface.fill((140, 140, 136))
                pixels = pygame.image.tostring(surface, 'RGBA', False)
                width, height = surface.get_size()

                texture = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                # Mirrored, so the photo joins with itself at every edge without being edited.
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_MIRRORED_REPEAT)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
                GLU.gluBuild2DMipmaps(GL.GL_TEXTURE_2D, GL.GL_RGBA, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE,
                                      pixels)
                Outposts._concrete_texture_id = texture
        return Outposts._concrete_texture_id

    @staticmethod
    def _get_texture() -> int:
        if Outposts._texture_id is None:
            with frame_watch.timed('outpost texture'):
                if os.path.exists(TEXTURE_PATH):
                    surface = pygame.image.load(TEXTURE_PATH).convert_alpha()
                else:
                    logger.error(f"Outpost texture missing: {TEXTURE_PATH}. Using a plain grey texture.")
                    surface = pygame.Surface((ATLAS_WIDTH, ATLAS_HEIGHT)).convert()
                    surface.fill((90, 94, 102))
                width, height = surface.get_size()
                pixels = pygame.image.tostring(surface, 'RGBA', False)

                texture = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GLU.gluBuild2DMipmaps(GL.GL_TEXTURE_2D, GL.GL_RGBA, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels)
                Outposts._texture_id = texture
        return Outposts._texture_id
