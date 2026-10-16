"""The sun in the OpenGL pass: its disc and corona as one textured quad, its sunspots and flares, and the glare around it.

The quad is a texture made once per star colour (local_star.star_rgba), so the GPU does the scaling and the sun costs
little at any distance. OpenGLGui draws it under the sky: the sky is transparent where the sun is (local_star.erase), so
the worlds in front of the sun cover it and the worlds behind it are not there. The glare goes over the sky, under the
cockpit. Flares are in game time (star_flares), and not drawn above FLARE_MAX_TIME_SCALE.
"""

from __future__ import annotations
import math
from typing import Callable, Dict, Tuple, TYPE_CHECKING
import numpy as np
from OpenGL import GL
from .constants import (
    STAR_CORONA_EXTENT, FLARE_SIZE_SHARE, FLARE_MAX_TIME_SCALE, GLARE_MAX, GLARE_RADIUS_SHARE,
    GLARE_SIZE_OF_CORONA, SPOT_DEPTH, SPOT_FRAME_SECONDS, SPOT_MAX_TURN_PER_FRAME,
)
from .local_star import StarView, star_rgba
from .star_surface import granulation, sunspots, sunspot_quads
from .star_flares import flares_active

if TYPE_CHECKING:
    from galaxies.star import Star

STAR_TEXTURE_DISC = 192  # the disc's radius in the star's texture, in texels; its corona reaches STAR_CORONA_EXTENT times that
PROMINENCE_TEXTURE_SIZE = 64
PROMINENCE_COLOUR = (1.0, 0.55, 0.25)
FLARE_COLOUR = (1.0, 0.85, 0.6)
SPOT_TEXTURE_SIZE = 32  # a sunspot is a soft dark blob, this many texels across

_textures: Dict[Tuple, int] = {}


def _texture(key: Tuple, make_array: Callable[[], np.ndarray]) -> int:
    """The texture for `key`, made from make_array() the first time (in the current OpenGL context)."""
    texture = _textures.get(key)
    if texture is None:
        array = np.ascontiguousarray(make_array(), dtype=np.uint8)
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, array.shape[1], array.shape[0], 0,
                        GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, array.tobytes())
        _textures[key] = texture
    return texture


def _star_texture(colour: Tuple[int, int, int], star_seed: float, detailed: bool = True) -> int:
    """The sun's texture; `detailed` adds the granulation (not for the glare, which draws it at another scale)."""
    size = 2 * int(STAR_CORONA_EXTENT * STAR_TEXTURE_DISC)
    centre = size / 2

    def make() -> np.ndarray:
        rgba = star_rgba(size, size, centre, centre, STAR_TEXTURE_DISC, STAR_CORONA_EXTENT * STAR_TEXTURE_DISC, colour)
        if detailed:
            detail = granulation(size, size, centre, centre, STAR_TEXTURE_DISC, star_seed)
            rgba[..., :3] = np.clip(rgba[..., :3] * detail[..., None], 0, 255).astype(np.uint8)
        return rgba

    return _texture(('star', tuple(colour), star_seed if detailed else None), make)


def _spot_texture() -> int:
    """A sunspot: black, with an opacity falling off from its centre (SPOT_DEPTH at the centre)."""
    def make() -> np.ndarray:
        axis = np.linspace(-1.0, 1.0, SPOT_TEXTURE_SIZE, dtype=np.float32)
        r2 = axis[None, :] ** 2 + axis[:, None] ** 2
        array = np.zeros((SPOT_TEXTURE_SIZE, SPOT_TEXTURE_SIZE, 4), dtype=np.uint8)
        array[..., 3] = np.clip(255 * SPOT_DEPTH * np.exp(-3.0 * r2), 0, 255).astype(np.uint8)
        return array
    return _texture(('spot',), make)


def _begin_2d(width: int, height: int) -> None:
    """The window as a 2D canvas with the top-left corner at (0, 0), blended, textured."""
    GL.glViewport(0, 0, width, height)
    GL.glEnable(GL.GL_TEXTURE_2D)
    GL.glEnable(GL.GL_BLEND)
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
    GL.glTexEnvi(GL.GL_TEXTURE_ENV, GL.GL_TEXTURE_ENV_MODE, GL.GL_MODULATE)
    GL.glMatrixMode(GL.GL_PROJECTION)
    GL.glPushMatrix()
    GL.glLoadIdentity()
    GL.glOrtho(0, width, height, 0, -1, 1)
    GL.glMatrixMode(GL.GL_MODELVIEW)
    GL.glPushMatrix()
    GL.glLoadIdentity()


def _end_2d() -> None:
    GL.glMatrixMode(GL.GL_PROJECTION)
    GL.glPopMatrix()
    GL.glMatrixMode(GL.GL_MODELVIEW)
    GL.glPopMatrix()
    GL.glDisable(GL.GL_TEXTURE_2D)


def _quad(x0: float, y0: float, x1: float, y1: float) -> None:
    """A textured rectangle, the whole texture on it, top row at the top (as the sky's texture)."""
    GL.glBegin(GL.GL_QUADS)
    GL.glTexCoord2f(0, 0)
    GL.glVertex2f(x0, y0)
    GL.glTexCoord2f(1, 0)
    GL.glVertex2f(x1, y0)
    GL.glTexCoord2f(1, 1)
    GL.glVertex2f(x1, y1)
    GL.glTexCoord2f(0, 1)
    GL.glVertex2f(x0, y1)
    GL.glEnd()


class StarGl:
    """Draws the sun in the OpenGL pass. Call with the depth test off, from OpenGLGui.draw."""

    @staticmethod
    def draw_star(width: int, height: int, view: StarView, game_seconds: float, time_scale: float) -> None:
        """The disc and corona, then the sunspots and the flares. The spots are not drawn when, at this time scale, they
        would turn more than SPOT_MAX_TURN_PER_FRAME of a turn between two frames (they would jump). The flares are not
        drawn above FLARE_MAX_TIME_SCALE."""
        star: Star = view.star
        disc = view.disc_px
        _begin_2d(width, height)
        GL.glColor4f(1.0, 1.0, 1.0, 1.0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, _star_texture(star.color, star.seed))
        _quad(view.x - view.corona_px, view.y - view.corona_px, view.x + view.corona_px, view.y + view.corona_px)

        turn_per_frame = time_scale * SPOT_FRAME_SECONDS / star.rotation_period
        if turn_per_frame <= SPOT_MAX_TURN_PER_FRAME:
            GL.glBindTexture(GL.GL_TEXTURE_2D, _spot_texture())
            for quad in sunspot_quads(sunspots(star.seed), game_seconds, star.rotation_period):
                px = view.x + disc * quad.dx
                py = view.y + disc * quad.dy
                half_w = disc * quad.half_width
                half_h = disc * quad.half_height
                _quad(px - half_w, py - half_h, px + half_w, py + half_h)

        if time_scale <= FLARE_MAX_TIME_SCALE:
            size = FLARE_SIZE_SHARE * disc
            for longitude, intensity in flares_active(star.seed, game_seconds):
                px = view.x + disc * math.sin(longitude)
                py = view.y - 0.2 * disc
                GL.glColor4f(*FLARE_COLOUR, min(1.0, intensity))
                _quad(px - size / 2, py - size / 2, px + size / 2, py + size / 2)
        _end_2d()

    @staticmethod
    def glare_half_px(view: StarView) -> float:
        """The glare's half-size in pixels: a multiple of the corona, so it is as big as the sun looks (and shrinks
        with it, as the sun gets farther away)."""
        return GLARE_SIZE_OF_CORONA * view.corona_px

    @staticmethod
    def draw_glare(width: int, height: int, view: StarView, star: Star) -> None:
        """Light spilling from the sun over the view, stronger the nearer the sun is to the middle of the screen. Its size
        follows the sun's apparent size (glare_half_px). Added to what is drawn (additive), so it brightens the sky and
        the worlds, and is under the cockpit."""
        distance = math.hypot(view.x - width / 2, view.y - height / 2)
        reach = GLARE_RADIUS_SHARE * height
        strength = GLARE_MAX * max(0.0, 1.0 - distance / reach) ** 2
        if strength <= 0.0:
            return
        half = StarGl.glare_half_px(view)
        _begin_2d(width, height)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)  # additive
        GL.glColor4f(star.color[0] / 255 * strength, star.color[1] / 255 * strength, star.color[2] / 255 * strength, 1.0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, _star_texture(star.color, star.seed, detailed=False))
        _quad(view.x - half, view.y - half, view.x + half, view.y + half)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)  # back to the blending the rest of the frame uses
        _end_2d()

    @staticmethod
    def draw_visor(width: int, height: int, strength: float) -> None:
        """The visor: the view darkened by `strength` (0 to 1). Drawn over the sky and the sun, under the cockpit."""
        if strength <= 0.0:
            return
        GL.glViewport(0, 0, width, height)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, width, height, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glColor4f(0.0, 0.0, 0.0, strength)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex2f(0, 0)
        GL.glVertex2f(width, 0)
        GL.glVertex2f(width, height)
        GL.glVertex2f(0, height)
        GL.glEnd()
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_MODELVIEW)
