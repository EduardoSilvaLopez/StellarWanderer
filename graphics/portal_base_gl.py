"""The portal base in space, drawn as OpenGL meshes while the ship is unbound (`PortalBase`; its shape is in
portal_base_shape.py and its textures in tools/generate_portal_base_texture.py).

Like the asteroids, it is drawn with its own perspective, whose near and far planes just hold it, and with its own depth
buffer (cleared before it): its size and its distance are too many orders of magnitude apart for one. Where it is, in
relation to the ship, is worked out in double precision before it goes to OpenGL. The ring, the spokes and the hub spin
(`PortalBase.spin`) and the hangar does not. The pieces are drawn in this order: the hull and the docking place with
the baked light of the star, the marks (numbers, hazard stripes, chevrons) over them, what shines (windows, lamps, the
red lights) added on top, and last the plumes of the four ion thrusters that hold the base against the pull of the star.
The spin is for the eyes: it is a function of the game's date (like the orbits), so it stops with the game, and at
high time compression it strobes, as the ring is drawn once a frame.

The plumes are camera-facing strips and sprites of light, added to the picture: nested, from violet and wide to white
and thin, as long as the pull of the star asks (`plume_length`: a base at a red dwarf burns hard, one at a hot star
gently), with a small flicker. They keep a minimum width in pixels, so that they show from far, and from where the
whole base is only a few pixels across it is drawn as a point of the colour of the plumes."""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime
from typing import Callable, TYPE_CHECKING

import numpy as np
import pygame
from OpenGL import GL, GLU

from common.frame_watch import frame_watch
from common.paths import resource_path
from .constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS
from .instruments.common import view_geometry
from .portal_base_shape import BaseModel, Mesh, make_model

if TYPE_CHECKING:
    from galaxies.portal_base import PortalBase
    from game_environment import GameEnvironment
    from spaceships.ship import Ship

logger = logging.getLogger(__name__)

TEXTURE_NAMES = ('hull', 'hull_glow', 'interior', 'interior_glow', 'marks', 'spoke', 'hangar', 'hangar_glow',
                 'side', 'side_glow')

# What a plume is made of, widest and faintest first: the width as a fraction of the nozzle's, the colour, the strength.
PLUME_LAYERS = (
    (1.7, (120, 96, 255), 0.32),
    (0.95, (84, 150, 255), 0.55),
    (0.38, (214, 236, 255), 0.95),
)
PLUME_COLOUR = (150, 175, 255)  # the plumes seen from afar, as a point


class PortalBaseGl:
    """Draws the portal base of the ship's system."""

    MIN_PIXELS = 6  # a base whose reach is smaller on the screen than this is a point
    POINT_SIZE = 5.0
    POINT_DISTANCE = 100.0  # where the point is drawn, in the direction of the base
    PLUME_REFERENCE_PULL = 2.7e-4  # m/s^2, that of a Sun-like star at the base's height: a plume 1.2 radii long
    PLUME_LENGTH_RADII = 1.2
    PLUME_SPREAD = 0.14  # the plume's half-width grows by this much of every metre of its length
    PLUME_SEGMENTS = 12
    MIN_PLUME_PIXELS = 1.6  # the half-width a plume keeps on the screen, however far
    MIN_SPRITE_PIXELS = 4.0

    _model: BaseModel | None = None
    _model_key: tuple[float, tuple[int, int, int]] | None = None
    _textures: dict[str, int] = {}
    _soft_textures: tuple[int, int] | None = None  # the gradient across a strip, and the round sprite
    _spin: float = 0.0  # the angle of the ring (rad), from the game's date
    _seconds: float = 0.0  # the game's date in seconds since the epoch, for the flicker of the plumes

    # region Frame
    @staticmethod
    def draw(width: int, height: int, ship: Ship, environment: GameEnvironment) -> None:
        """Draws the base of the system, if it is in front of the ship. Call while unbound, after the sky."""
        base = environment.nearest_system.portal_base
        date = environment.date_time
        position = ship.navigation.stellar_position(date)
        centre = base.calculate_stellar_position(date)
        relative = np.array([centre.x - position.x, centre.y - position.y, centre.z - position.z])
        distance = float(np.linalg.norm(relative))
        if distance == 0.0:
            return
        model = PortalBaseGl._get_model(base)
        plume_length = PortalBaseGl.plume_length(base)
        reach = math.hypot(model.radius, abs(model.plume_start_z) + plume_length)
        forward = ship.attitude.forward
        ahead = float(relative @ np.array([forward.x, forward.y, forward.z]))
        if distance > reach and math.acos(max(-1.0, min(1.0, ahead / distance))) > math.radians(75.0) + math.asin(
                reach / distance):
            return

        _, _, focal = view_geometry(height)
        view_height = int(height * CONSOLE_TOP)
        aspect = width / view_height
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        matrix = ship.attitude.camera_matrix()
        if 2.0 * reach * focal / distance < PortalBaseGl.MIN_PIXELS:
            PortalBaseGl._draw_point(matrix, relative, aspect)
        else:
            PortalBaseGl._set_clock(base, environment.date_time)
            PortalBaseGl._draw_base(model, base, ship, matrix, relative, distance, reach, plume_length, aspect, focal)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glViewport(0, 0, width, height)

    @staticmethod
    def plume_length(base: PortalBase) -> float:
        """How long the plumes are (m): `PLUME_LENGTH_RADII` radii for the pull of a Sun-like star, 20 % more or less
        for every power of ten of the pull above or below it, within limits (the pulls differ by orders of
        magnitude from star to star)."""
        strength = min(1.5, max(0.5, 1.0 + 0.2 * math.log10(base.pull / PortalBaseGl.PLUME_REFERENCE_PULL)))
        return PortalBaseGl.PLUME_LENGTH_RADII * base.radius * strength

    @staticmethod
    def preload_textures() -> None:
        """Loads the textures now, while the window is being set up. Needs the OpenGL window to exist."""
        for name in TEXTURE_NAMES:
            PortalBaseGl._texture(name)
        PortalBaseGl.soft_textures()

    @staticmethod
    def _set_clock(base: PortalBase, date: datetime) -> None:
        """The ring's angle and the plumes' flicker, from the game's date: they stop when the game does (a dialog pauses
        it), and follow the time scale."""
        # Local: the game imports this module before the environment exists.
        from game_environment import GameEnvironment
        PortalBaseGl._seconds = (date - GameEnvironment.EPOCH).total_seconds()
        PortalBaseGl._spin = (base.spin * PortalBaseGl._seconds) % math.tau
    # endregion

    # region Drawing
    @staticmethod
    def _perspective(matrix: list, near: float, far: float, aspect: float) -> None:
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GLU.gluPerspective(math.degrees(VIEW_VERTICAL_FOV_RADIANS), aspect, near, far)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glMultMatrixf(matrix)

    @staticmethod
    def _draw_base(model: BaseModel, base: PortalBase, ship: Ship, matrix: list, relative: np.ndarray, distance: float,
                   reach: float, plume_length: float, aspect: float, focal: float) -> None:
        margin = 1.05 * reach
        PortalBaseGl._perspective(matrix, max(0.05, distance - margin), distance + margin, aspect)
        GL.glTranslated(float(relative[0]), float(relative[1]), float(relative[2]))
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glDepthFunc(GL.GL_LESS)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        angle = math.degrees(PortalBaseGl._spin)

        def spinning(draw: Callable[[], None]) -> None:
            GL.glPushMatrix()
            GL.glRotated(angle, 0.0, 0.0, 1.0)
            draw()
            GL.glPopMatrix()

        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        draw_mesh = PortalBaseGl._draw_mesh
        draw_mesh(model.fixed_hull, 'hull')
        draw_mesh(model.hangar, 'hangar')
        draw_mesh(model.interior, 'interior')
        draw_mesh(model.doors, 'interior')
        spinning(lambda: draw_mesh(model.spinning_hull, 'hull'))
        # The spokes lie in the plane of the ring's walls, so their depth ties with the ring's glow behind them: they
        # are pulled a little toward the camera, so that the glow does not show through them.
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(-2.0, -8.0)
        spinning(lambda: draw_mesh(model.sides, 'side'))
        spinning(lambda: draw_mesh(model.spokes, 'spoke'))
        GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glDepthMask(GL.GL_FALSE)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(-1.0, -4.0)
        draw_mesh(model.fixed_marks, 'marks')
        spinning(lambda: draw_mesh(model.spinning_marks, 'marks'))

        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glColor3f(1.0, 1.0, 1.0)
        draw_mesh(model.fixed_hull, 'hull_glow')
        draw_mesh(model.hangar, 'hangar_glow')
        draw_mesh(model.interior, 'interior_glow')
        spinning(lambda: draw_mesh(model.spinning_hull, 'hull_glow'))
        spinning(lambda: draw_mesh(model.sides, 'side_glow'))
        GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

        GL.glDepthFunc(GL.GL_LESS)
        PortalBaseGl._draw_plumes(model, ship, relative, plume_length, focal)
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)

    @staticmethod
    def _draw_mesh(mesh: Mesh, texture: str) -> None:
        if len(mesh.positions) == 0:
            return
        GL.glBindTexture(GL.GL_TEXTURE_2D, PortalBaseGl._texture(texture))
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, mesh.positions)
        GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, mesh.uvs)
        if not texture.endswith('_glow'):
            GL.glColorPointer(3, GL.GL_UNSIGNED_BYTE, 0, mesh.colours)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(mesh.positions))

    @staticmethod
    def _draw_point(matrix: list, relative: np.ndarray, aspect: float) -> None:
        """The base too far to show its shape: a point of the colour of the plumes in its direction."""
        PortalBaseGl._perspective(matrix, 1.0, 10.0 * PortalBaseGl.POINT_DISTANCE, aspect)
        direction = relative / float(np.linalg.norm(relative)) * PortalBaseGl.POINT_DISTANCE
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)
        GL.glEnable(GL.GL_POINT_SMOOTH)
        GL.glPointSize(PortalBaseGl.POINT_SIZE)
        GL.glColor4ub(*PLUME_COLOUR, 255)
        GL.glBegin(GL.GL_POINTS)
        GL.glVertex3f(float(direction[0]), float(direction[1]), float(direction[2]))
        GL.glEnd()
        GL.glDisable(GL.GL_BLEND)
    # endregion

    # region Plumes
    @staticmethod
    def _draw_plumes(model: BaseModel, ship: Ship, relative: np.ndarray, length: float, focal: float) -> None:
        """The plumes and the glow at the nozzles, in the frame of the ring (which is turned by the spin), faced to
        the camera. Every strip of every nozzle and every glow is built in one numpy pass, and drawn in two calls."""
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)
        GL.glPushMatrix()
        GL.glRotated(math.degrees(PortalBaseGl._spin), 0.0, 0.0, 1.0)
        cos_a, sin_a = math.cos(-PortalBaseGl._spin), math.sin(-PortalBaseGl._spin)
        rotation = np.array([[cos_a, -sin_a, 0.0], [sin_a, cos_a, 0.0], [0.0, 0.0, 1.0]])
        camera = rotation @ -relative
        right = rotation @ np.array(tuple(ship.attitude.right))
        up = rotation @ np.array(tuple(ship.attitude.up))
        gradient, round_sprite = PortalBaseGl.soft_textures()

        nozzles = np.array(model.nozzles)  # (4, 3)
        now = PortalBaseGl._seconds
        index = np.arange(len(nozzles))
        flicker = 0.9 + 0.07 * np.sin(31.0 * now + 1.7 * index) + 0.03 * np.sin(83.0 * now + index)  # (4,)
        to_camera = camera[None, :] - nozzles
        distance = np.linalg.norm(to_camera, axis=1)  # (4,)
        axis = np.array([0.0, 0.0, -1.0])
        side = np.cross(axis, to_camera)  # (4, 3): across the view from each nozzle
        side_length = np.linalg.norm(side, axis=1)
        side = np.where((side_length < 1e-6 * np.maximum(distance, 1.0))[:, None], right[None, :],
                        side / np.maximum(side_length, 1e-12)[:, None])
        pixel = distance / focal  # (4,): metres a pixel covers at each nozzle

        strips = PortalBaseGl._strip_batch(nozzles, side, length, model.scale, pixel, flicker)
        glows = PortalBaseGl._glow_batch(nozzles, right, up, model.scale, pixel, flicker)

        GL.glBindTexture(GL.GL_TEXTURE_2D, gradient)
        PortalBaseGl._draw_triangles(*strips)
        GL.glBindTexture(GL.GL_TEXTURE_2D, round_sprite)
        PortalBaseGl._draw_triangles(*glows)
        GL.glPopMatrix()
        GL.glDisable(GL.GL_BLEND)

    @staticmethod
    def _strip_batch(nozzles: np.ndarray, side: np.ndarray, length: float, scale: float, pixel: np.ndarray,
                     flicker: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The triangles of every layer of every plume: a strip along -z from each nozzle, across the view (`side`),
        that widens and fades along its length. Returns the positions, texture coordinates and colours (RGBA)."""
        steps = PortalBaseGl.PLUME_SEGMENTS
        verts = 2 * (steps + 1)
        t = np.linspace(0.0, 1.0, steps + 1)  # (S,)
        widths = np.array([layer[0] for layer in PLUME_LAYERS])  # (3,)
        colours = np.array([layer[1] for layer in PLUME_LAYERS], np.float32) / 255.0  # (3, 3)
        strengths = np.array([layer[2] for layer in PLUME_LAYERS])  # (3,)
        nozzle_count, layer_count = len(nozzles), len(widths)
        count = nozzle_count * layer_count  # one strip per nozzle and layer

        half = widths[None, :, None] * (2.4 * scale + PortalBaseGl.PLUME_SPREAD * length * t)[None, None, :]
        half = np.maximum(half, PortalBaseGl.MIN_PLUME_PIXELS * pixel[:, None, None] * np.sqrt(widths)[None, :, None])
        centres = nozzles[:, None, :] + (length * t)[None, :, None] * np.array([0.0, 0.0, -1.0])  # (4, S, 3)
        offset = side[:, None, None, :] * half[..., None]  # (4, 3, S, 3)
        left = centres[:, None, :, :] - offset
        right_edge = centres[:, None, :, :] + offset
        vertices = np.stack([left, right_edge], axis=3).reshape(count, verts, 3)  # left, right, left, ...

        quads = np.arange(steps)
        pattern = np.stack([2 * quads, 2 * quads + 1, 2 * quads + 2, 2 * quads + 1, 2 * quads + 3, 2 * quads + 2],
                           axis=1).reshape(-1)
        index = (np.arange(count)[:, None] * verts + pattern[None, :]).reshape(-1)
        positions = vertices.reshape(-1, 3)[index]

        uv_pair = np.stack([np.stack([np.zeros_like(t), t], axis=1), np.stack([np.ones_like(t), t], axis=1)], axis=1)
        uvs = np.broadcast_to(uv_pair.reshape(1, verts, 2), (count, verts, 2)).reshape(-1, 2)[index]

        alpha = (strengths[None, :, None] * flicker[:, None, None]) * (1.0 - t) ** 1.4  # (4, 3, S)
        alpha = np.repeat(alpha, 2, axis=2).reshape(count, verts, 1)
        rgb = np.broadcast_to(colours[None, :, None, :], (nozzle_count, layer_count, verts, 3))
        rgba = np.concatenate([rgb.reshape(count, verts, 3), alpha], axis=2).reshape(-1, 4)[index]
        return positions.astype(np.float32), uvs.astype(np.float32), rgba.astype(np.float32)

    @staticmethod
    def _glow_batch(nozzles: np.ndarray, right: np.ndarray, up: np.ndarray, scale: float, pixel: np.ndarray,
                    flicker: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The round glows of every nozzle, two each (a small bright one and a wider violet halo), as triangles."""
        sprite = np.maximum(5.0 * scale, PortalBaseGl.MIN_SPRITE_PIXELS * pixel)
        halo = np.maximum(14.0 * scale, 3.0 * PortalBaseGl.MIN_SPRITE_PIXELS * pixel)
        radii = np.stack([sprite, halo], axis=1)  # (4, 2)
        colours = np.array([(230, 240, 255), (120, 110, 255)], np.float32) / 255.0  # (2, 3)
        strengths = np.array([0.95, 0.30])  # (2,)
        corners = np.array([(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)])  # (4, 2)
        order = [0, 1, 2, 0, 2, 3]
        offsets = corners[:, 0:1] * right[None, :] + corners[:, 1:2] * up[None, :]  # (4, 3)
        points = nozzles[:, None, None, :] + radii[:, :, None, None] * offsets[None, None, :, :]  # (4, 2, 4, 3)
        rgba = np.empty((len(nozzles), 2, 4, 4), np.float32)
        rgba[..., :3] = colours[None, :, None, :]
        rgba[..., 3] = (strengths[None, :] * flicker[:, None])[:, :, None]
        uvs = np.broadcast_to(0.5 + 0.5 * corners, (len(nozzles), 2, 4, 2))
        positions = points[:, :, order, :].reshape(-1, 3)
        return (positions.astype(np.float32), uvs[:, :, order, :].reshape(-1, 2).astype(np.float32),
                rgba[:, :, order, :].reshape(-1, 4))

    @staticmethod
    def _draw_triangles(positions: np.ndarray, uvs: np.ndarray, colours: np.ndarray) -> None:
        """Draws triangles with a texture, per-vertex colours (RGBA) and a vertex array."""
        positions = np.ascontiguousarray(positions, np.float32)
        uvs = np.ascontiguousarray(uvs, np.float32)
        colours = np.ascontiguousarray(colours, np.float32)
        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, positions)
        GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, uvs)
        GL.glColorPointer(4, GL.GL_FLOAT, 0, colours)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(positions))
        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
    # endregion

    # region Resources
    @staticmethod
    def _get_model(base: PortalBase) -> BaseModel:
        """The model of the base, made when it is first seen: the lighting in it depends on the colour of the star."""
        star_colour = tuple(int(channel) for channel in base.stellar_system.star.color)
        key = (base.radius, star_colour)
        if PortalBaseGl._model is None or PortalBaseGl._model_key != key:
            with frame_watch.timed('portal base model'):
                tint = tuple(int(255 * (0.7 + 0.3 * channel / 255.0)) for channel in star_colour)
                PortalBaseGl._model = make_model(base.radius, tint)
                PortalBaseGl._model_key = key
        return PortalBaseGl._model

    @staticmethod
    def _texture(name: str) -> int:
        """The texture of this name (portal_base_<name>.png), with mipmaps, loaded the first time."""
        if name not in PortalBaseGl._textures:
            with frame_watch.timed('portal base texture'):
                path = resource_path('textures', f'portal_base_{name}.png')
                if os.path.exists(path):
                    surface = pygame.image.load(path).convert_alpha()
                else:
                    logger.error(f"Portal base texture missing: {path}. Using a plain grey texture.")
                    surface = pygame.Surface((64, 64)).convert_alpha()
                    surface.fill((90, 94, 102, 255))
                width, height = surface.get_size()
                pixels = pygame.image.tostring(surface, 'RGBA', False)
                texture = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
                wrap = GL.GL_CLAMP_TO_EDGE if name == 'marks' else GL.GL_REPEAT
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, wrap)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, wrap)
                PortalBaseGl._anisotropy()
                GLU.gluBuild2DMipmaps(GL.GL_TEXTURE_2D, GL.GL_RGBA, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE,
                                      pixels)
                PortalBaseGl._textures[name] = texture
        return PortalBaseGl._textures[name]

    @staticmethod
    def _anisotropy() -> None:
        """Asks for the sharpest filtering at a slant (a ring seen edge-on), where the driver has it."""
        try:
            maximum = GL.glGetFloatv(0x84FF)  # GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT
            GL.glTexParameterf(GL.GL_TEXTURE_2D, 0x84FE, min(8.0, float(maximum)))
        except Exception:  # noqa: BLE001 - no such extension: the plain filter stays
            pass

    @staticmethod
    def soft_textures() -> tuple[int, int]:
        """The textures of the plumes, made here: a gradient across a strip (soft at both edges), and a round sprite."""
        if PortalBaseGl._soft_textures is None:
            across = np.exp(-(((np.arange(64) + 0.5) / 64.0 - 0.5) / 0.22) ** 2)
            gradient = np.zeros((2, 64, 4), np.uint8)
            gradient[..., :3] = 255
            gradient[..., 3] = (255 * across)[None, :]
            coordinates = (np.arange(64) + 0.5) / 32.0 - 1.0
            radius_squared = coordinates[None, :] ** 2 + coordinates[:, None] ** 2
            sprite = np.zeros((64, 64, 4), np.uint8)
            sprite[..., :3] = 255
            sprite[..., 3] = (255 * np.clip(1.0 - radius_squared, 0.0, 1.0) ** 2.2).astype(np.uint8)
            textures = []
            for pixels in (gradient, sprite):
                texture = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, pixels.shape[1], pixels.shape[0], 0, GL.GL_RGBA,
                                GL.GL_UNSIGNED_BYTE, pixels)
                textures.append(texture)
            PortalBaseGl._soft_textures = (textures[0], textures[1])
        return PortalBaseGl._soft_textures
    # endregion
