"""OpenGL-backed frame composition for the cockpit view."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Any
import pygame
from OpenGL import GL

from .Constants import SPACE_COLOR
from .Cockpit import Cockpit
from .DeepSpace import DeepSpace
from .LocalStar import LocalStar
from .lit_worlds import LitWorlds
from .NearestWorld import NearestWorld
from .other_worlds import OtherWorlds
from .Rocks import Rocks
from .Laser import Laser

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment
    from Galaxies.Rock import Rock
    from Galaxies.ore_fields import OreField
    from Galaxies.ore_mine import OreMine


class OpenGLGui:
    """Compose the software UI and depth-tested OpenGL rock pass."""

    def __init__(self) -> None:
        self.world_surface: Optional[pygame.Surface] = None
        self.overlay_surface: Optional[pygame.Surface] = None
        self.world_texture: Optional[int] = None
        self.overlay_texture: Optional[int] = None
        self.dialog_texture: Optional[int] = None
        self._uploaded_textures: set = set()

    def draw(self, screen: pygame.Surface, fonts: Any, environment: GameEnvironment, player: Player,
             dialog_surface: Optional[pygame.Surface] = None) -> None:
        """Render one complete frame into the active OpenGL window.

        dialog_surface, if given, is a window-sized RGBA layer (see Dialog.compose_overlay) drawn
        above everything else."""
        # The real window size, not screen.get_size(): for an OpenGL window pygame can keep returning
        # a surface of the size first requested, which then differs from the window's client area
        # (the window frame takes part of it), cropping the frame and shifting mouse positions.
        width, height = pygame.display.get_window_size()
        self._ensure_surfaces(width, height)

        self.world_surface.fill(SPACE_COLOR)
        DeepSpace.draw(self.world_surface, width, height)
        OtherWorlds.draw(self.world_surface, width, height, environment, player, behind_star=True)
        LocalStar.draw(self.world_surface, width, height, environment, player)
        OtherWorlds.draw(self.world_surface, width, height, environment, player, behind_star=False)
        if player.is_bound:
            NearestWorld.draw_surface(self.world_surface, width, height, environment, player)
        else:
            LitWorlds.draw_nearest(self.world_surface, width, height, environment, player)

        self.overlay_surface.fill((0, 0, 0, 0))
        Cockpit.draw(
            self.overlay_surface,
            fonts,
            width,
            height,
            player,
            environment.date_time,
            player.time_scale,
        )

        GL.glViewport(0, 0, width, height)
        GL.glClearColor(8 / 255, 10 / 255, 24 / 255, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(self.world_surface, self.world_texture)
        if player.is_bound:
            Rocks.draw(
                width, height, player,
                self._rocks(environment, player),
                self._ore_fields(environment, player),
                self._ore_mines(environment, player),
            )
        Laser.draw(width, height, player)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(self.overlay_surface, self.overlay_texture, blend=True)
        if dialog_surface is not None:
            self._draw_texture(dialog_surface, self.dialog_texture, blend=True)

    def _rocks(self, environment: GameEnvironment, player: Player) -> List[Rock]:
        rocks: List[Rock] = []
        for km2 in environment.nearest_world.km2s:
            if (km2.longitude - km2.SIZE * 2 <= player.position.x < km2.longitude + km2.SIZE * 2 and
                km2.latitude - km2.SIZE * 2 <= player.position.z < km2.latitude + km2.SIZE * 2):
                rocks.extend(km2.rocks)
        return rocks

    def _ore_fields(self, environment: GameEnvironment, player: Player) -> List[OreField]:
        ore_fields: List[OreField] = []
        for km2 in environment.nearest_world.km2s:
            if (km2.longitude - km2.SIZE * 2 <= player.position.x < km2.longitude + km2.SIZE * 2 and
                km2.latitude - km2.SIZE * 2 <= player.position.z < km2.latitude + km2.SIZE * 2):
                ore_fields.extend(km2.ore_fields)
        return ore_fields

    def _ore_mines(self, environment: GameEnvironment, player: Player) -> List[OreMine]:
        mines: List[OreMine] = []
        for km2 in environment.nearest_world.km2s:
            if (km2.longitude - km2.SIZE * 2 <= player.position.x < km2.longitude + km2.SIZE * 2 and
                km2.latitude - km2.SIZE * 2 <= player.position.z < km2.latitude + km2.SIZE * 2):
                for ore_field in km2.ore_fields:
                    mines.extend(ore_field.mines)
        return mines

    def _ensure_surfaces(self, width: int, height: int) -> None:
        size = (width, height)
        if self.world_surface is None or self.world_surface.get_size() != size:
            self.world_surface = pygame.Surface(size).convert()
            self.overlay_surface = pygame.Surface(size, pygame.SRCALPHA, 32).convert_alpha()
            self.world_texture = self._make_texture(width, height)
            self.overlay_texture = self._make_texture(width, height)
            self.dialog_texture = self._make_texture(width, height)
            self._uploaded_textures = set()

    @staticmethod
    def _make_texture(width: int, height: int) -> int:
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        return texture

    @staticmethod
    def _is_bgra32(surface: pygame.Surface) -> bool:
        """True if the surface's memory is tightly packed 32-bit BGRA (or BGRX), as OpenGL's GL_BGRA reads it."""
        return (
            surface.get_bytesize() == 4
            and surface.get_pitch() == surface.get_width() * 4
            and surface.get_masks()[:3] == (0x00FF0000, 0x0000FF00, 0x000000FF)
        )

    def _upload_texture(self, texture: int, width: int, height: int, pixel_format: int, pixels: Any) -> None:
        # The rock pass uses the canopy-height viewport; restore the full window
        # before drawing either 2D texture.
        GL.glViewport(0, 0, width, height)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        if texture in self._uploaded_textures:
            # Fast path: texture storage already exists, just update its contents.
            GL.glTexSubImage2D(
                GL.GL_TEXTURE_2D, 0, 0, 0, width, height,
                pixel_format, GL.GL_UNSIGNED_BYTE, pixels
            )
        else:
            # First upload: allocate storage and fill it in the same call. Allocating
            # blank storage (glTexImage2D with no data) and sub-imaging it in the very
            # next call, within the same frame, raced on some drivers and left parts
            # of the texture stale until something forced a full texture recreation
            # (e.g. a window resize) — symptoms were specific small UI regions missing
            # on the first rendered frame only.
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, width, height, 0,
                pixel_format, GL.GL_UNSIGNED_BYTE, pixels
            )
            self._uploaded_textures.add(texture)

    def _draw_texture(self, surface: pygame.Surface, texture: int, blend: bool = False) -> None:
        width, height = surface.get_size()
        # Keep Pygame's top-to-bottom row order for the top-left screen quad.
        # A 32-bit surface laid out as BGRA is uploaded as a plain copy of its memory (get_buffer().raw),
        # about 2.5x faster than converting with image.tostring on every frame. It is deliberately a bytes
        # copy and not a memoryview of the live buffer: a memoryview can stay exported while OpenGL holds
        # it (that raised BufferError at start, under the debugger) and would keep the surface locked.
        if self._is_bgra32(surface):
            self._upload_texture(texture, width, height, GL.GL_BGRA, surface.get_buffer().raw)
        else:
            self._upload_texture(texture, width, height, GL.GL_RGBA, pygame.image.tostring(surface, 'RGBA', False))
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
