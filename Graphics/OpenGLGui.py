"""OpenGL-backed frame composition for the cockpit view."""

import pygame
from OpenGL import GL

from .Constants import SPACE
from .Cockpit import Cockpit
from .DeepSpace import DeepSpace
from .NearestWorld import NearestWorld
from .OpenGLRocks import OpenGLRocks
from .Stars import Stars


class OpenGLGui:
    """Compose the software UI and depth-tested OpenGL rock pass."""

    def __init__(self):
        self.stars = Stars.make_starfield()
        self.world_surface = None
        self.overlay_surface = None
        self.world_texture = None
        self.overlay_texture = None

    def draw(self, screen, fonts, environment, player):
        """Render one complete frame into the active OpenGL window."""
        width, height = screen.get_size()
        self._ensure_surfaces(width, height)

        self.world_surface.fill(SPACE)
        DeepSpace.draw(self.world_surface, width, height)
        Stars.draw(self.world_surface, self.stars, width, height, player.orientation)
        NearestWorld.draw_surface(self.world_surface, width, height, environment, player)

        self.overlay_surface.fill((0, 0, 0, 0))
        Cockpit.draw(
            self.overlay_surface,
            fonts,
            width,
            height,
            player,
            player.date_time,
            player.time_scale,
        )

        GL.glViewport(0, 0, width, height)
        GL.glClearColor(8 / 255, 10 / 255, 24 / 255, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(self.world_surface, self.world_texture)
        OpenGLRocks.draw(width, height, player, self._rocks(environment, player))
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(self.overlay_surface, self.overlay_texture, blend=True)

    def _rocks(self, environment, player):
        rocks = []
        for km2 in environment.current_world.Km2s:
            if (km2.longitude - km2.SIZE * 2 <= player.position.x < km2.longitude + km2.SIZE * 2 and
                km2.latitude - km2.SIZE * 2 <= player.position.z < km2.latitude + km2.SIZE * 2):
                rocks.extend(km2.rocks)
        return rocks

    def _ensure_surfaces(self, width, height):
        size = (width, height)
        if self.world_surface is None or self.world_surface.get_size() != size:
            self.world_surface = pygame.Surface(size).convert()
            self.overlay_surface = pygame.Surface(size, pygame.SRCALPHA, 32).convert_alpha()
            self.world_texture = self._make_texture()
            self.overlay_texture = self._make_texture()

    @staticmethod
    def _make_texture():
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        return texture

    @staticmethod
    def _draw_texture(surface, texture, blend=False):
        width, height = surface.get_size()
        # Keep Pygame's top-to-bottom row order for the top-left screen quad.
        pixels = pygame.image.tostring(surface, 'RGBA', False)
        # The rock pass uses the canopy-height viewport; restore the full window
        # before drawing either 2D texture.
        GL.glViewport(0, 0, width, height)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, width, height, 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels
        )
        if blend:
            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        else:
            GL.glDisable(GL.GL_BLEND)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, width, height, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glColor4f(1, 1, 1, 1)
        GL.glBegin(GL.GL_QUADS)
        GL.glTexCoord2f(0, 0)
        GL.glVertex2f(0, 0)
        GL.glTexCoord2f(1, 0)
        GL.glVertex2f(width, 0)
        GL.glTexCoord2f(1, 1)
        GL.glVertex2f(width, height)
        GL.glTexCoord2f(0, 1)
        GL.glVertex2f(0, height)
        GL.glEnd()
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glDisable(GL.GL_TEXTURE_2D)
