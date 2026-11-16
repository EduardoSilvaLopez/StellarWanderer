"""What a leak does to the cockpit: a red light waving over the whole window while any leak is open (drawn on the GPU,
over the cockpit's layer), and for each leak a crack coming in from one side of the cockpit, drawn into the cockpit's
overlay. The crack's centre lies outside the window, so only its branches show, along the border. Its shape comes from
the leak's seed (see Ship.leaks), so it stays the same until the leak is sealed."""

from __future__ import annotations
import math
import random
from typing import Dict, Optional, Tuple, TYPE_CHECKING
from OpenGL import GL
import pygame

from universe.artifacts.spaceships.incident import Size

if TYPE_CHECKING:
    from universe.artifacts.spaceships.ship import Ship


class IncidentView:
    WAVE_RED = (255, 25, 15)
    WAVE_MAX_ALPHA = 150  # the red at its brightest, over the window
    WAVE_PERIOD = 1.6  # s: the light pulses once per period
    WAVE_SWAY = 0.05  # the share of the window the waves move sideways by (a share of the texture, which repeats)
    WAVE_COLUMNS = 64
    WAVE_ROWS = 36
    CRACK_LIGHT = (235, 240, 255, 230)
    CRACK_SHADOW = (0, 0, 0, 140)
    CRACK_OUT = 0.04  # the centre of a crack lies outside the window, by this share of its shorter side
    CRACK_REACH = 0.13  # the share of the shorter side that the branches of a crack reach from its centre
    CRACK_CACHE_SIZE = 16
    CRACK_SCALE: dict[Size, float] = {Size.BASE: 1.0, Size.MEDIUM: 2.0, Size.BIG: 4.0}  # times the reach

    _wave_texture: Optional[int] = None  # made on the first alarm, in the OpenGL window
    _cracks: Dict[Tuple[int, int, int, Size], Optional[Tuple[pygame.Surface, Tuple[int, int]]]] = {}

    @staticmethod
    def draw_alarm(width: int, height: int, ship: Ship) -> None:
        """The red light of the open leaks, over the whole window, waving: nothing while the hull is sealed. Drawn in
        the OpenGL pass, after the cockpit's layer, so it reaches the whole window at no cost on the processor."""
        if not ship.leaks:
            return
        if IncidentView._wave_texture is None:
            IncidentView._wave_texture = IncidentView._make_wave_texture()
        seconds = pygame.time.get_ticks() / 1000.0
        strength = max(leak.visibility() for leak in ship.leaks)  # the light fades once every leak is being sealed
        pulse = strength * (0.6 + 0.4 * math.sin(2 * math.pi * seconds / IncidentView.WAVE_PERIOD))
        sway = IncidentView.WAVE_SWAY * math.sin(2 * math.pi * seconds / (2 * IncidentView.WAVE_PERIOD))
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, IncidentView._wave_texture)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, width, height, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glColor4f(1, 1, 1, pulse)
        GL.glBegin(GL.GL_QUADS)
        GL.glTexCoord2f(sway, 0)
        GL.glVertex2f(0, 0)
        GL.glTexCoord2f(sway + 1, 0)
        GL.glVertex2f(width, 0)
        GL.glTexCoord2f(sway + 1, 1)
        GL.glVertex2f(width, height)
        GL.glTexCoord2f(sway, 1)
        GL.glVertex2f(0, height)
        GL.glEnd()
        GL.glColor4f(1, 1, 1, 1)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glDisable(GL.GL_TEXTURE_2D)

    @staticmethod
    def draw_cracks(overlay: pygame.Surface, ship: Ship, width: int, height: int) -> None:
        """A crack for each open leak, from the side of its seed, on the cockpit's overlay."""
        for leak in ship.leaks:
            crack = IncidentView._crack(leak.seed, leak.size, width, height)
            if crack is not None:
                crack[0].set_alpha(round(255 * leak.visibility()))
                overlay.blit(crack[0], crack[1])

    @staticmethod
    def _make_wave_texture() -> int:
        """The waves as a texture that repeats: a red whose alpha is a pattern of diagonal bands, periodic in both
        directions, so the sway and the window's size need no other texture."""
        pixels = bytearray()
        for row in range(IncidentView.WAVE_ROWS):
            for column in range(IncidentView.WAVE_COLUMNS):
                level = 0.5 + 0.5 * math.sin(2 * math.pi * (4 * column / IncidentView.WAVE_COLUMNS
                                                            + 2 * row / IncidentView.WAVE_ROWS))
                pixels += bytes((*IncidentView.WAVE_RED, int(IncidentView.WAVE_MAX_ALPHA * level)))
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, IncidentView.WAVE_COLUMNS, IncidentView.WAVE_ROWS, 0,
                        GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, bytes(pixels))
        return texture

    @staticmethod
    def _crack(seed: int, size: Size, width: int, height: int) -> Optional[Tuple[pygame.Surface, Tuple[int, int]]]:
        """The crack of a leak of `size` and `seed` over a window of this size, cut to the part it covers, with where it
        goes: its side, its
        place along that side and its branches are all drawn from the seed. None if none of it is in the window.
        Cached, as a leak keeps its crack for as long as it is open."""
        key = (seed, size, width, height)
        if key in IncidentView._cracks:
            return IncidentView._cracks[key]
        if len(IncidentView._cracks) >= IncidentView.CRACK_CACHE_SIZE:
            IncidentView._cracks.clear()
        surface = pygame.Surface((width, height), pygame.SRCALPHA, 32)
        rng = random.Random(seed)
        shorter = min(width, height)
        out = IncidentView.CRACK_OUT * shorter
        reach = IncidentView.CRACK_REACH * IncidentView.CRACK_SCALE[size] * shorter
        along = rng.uniform(0.15, 0.85)
        # the centre (outside the window) and the direction the crack comes in: top, right, bottom or left
        centre, inward = rng.choice([
            ((along * width, -out), math.pi / 2),
            ((width + out, along * height), math.pi),
            ((along * width, height + out), -math.pi / 2),
            ((-out, along * height), 0.0),
        ])

        def branch(x: float, y: float, angle: float, length: float, depth: int) -> None:
            if depth == 0 or length < 3:
                return
            end_x, end_y = x + math.cos(angle) * length, y + math.sin(angle) * length
            pygame.draw.line(surface, IncidentView.CRACK_SHADOW, (x + 1, y + 1), (end_x + 1, end_y + 1), depth + 2)
            pygame.draw.line(surface, IncidentView.CRACK_LIGHT, (x, y), (end_x, end_y), depth)
            for _ in range(rng.randint(1, 2)):
                branch(end_x, end_y, angle + rng.uniform(-0.8, 0.8), length * rng.uniform(0.45, 0.7), depth - 1)

        for _ in range(rng.randint(4, 6)):
            branch(centre[0], centre[1], inward + rng.uniform(-1.1, 1.1), reach * rng.uniform(0.7, 1.1), 4)
        covered = surface.get_bounding_rect()
        cut = None
        if covered.width > 0 and covered.height > 0:
            cut = (surface.subsurface(covered).copy(), covered.topleft)
        IncidentView._cracks[key] = cut
        return cut
