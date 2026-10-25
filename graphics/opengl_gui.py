"""OpenGL-backed frame composition for the cockpit view."""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional, List, Any, Tuple
import math
import pygame
from OpenGL import GL

from common.frame_watch import frame_watch
from .constants import SPACE_COLOR, MAX_DEPTH
from .cockpit import Cockpit
from .milky_way import MilkyWay
from .distant_stars import DistantStars
from .local_star import view_of, erase, sun_visibility
from .star_gl import StarGl
from .star_surface import visor_strength
from .starlight import Starlight, HeatVignette, FrostVignette
from .debug_fps import DebugFps
from .lit_worlds import LitWorlds
from .outpost_markers import OutpostMarkers
from .fixed_world import FixedWorld
from .orbit_path import OrbitPath
from .asteroids import Asteroids
from .other_worlds import OtherWorlds
from .rocks import Rocks
from .rock_batches import RockBatches
from .ore_fields import OreFields
from .ore_mines import OreMines
from .outposts import Outposts
from .laser import Laser
from .surface_light import SurfaceLight

if TYPE_CHECKING:
    from galaxies.people.player import Player
    from spaceships.ship import Ship
    from game_environment import GameEnvironment
    from galaxies.outpost import Outpost


class OpenGLGui:
    """Compose the software UI and depth-tested OpenGL rock pass.

    The sun is drawn in OpenGL, under the sky: the sky (the fixed stars, the worlds farther than the sun, a hole
    where the sun is, the worlds nearer than the sun, the targeted body) is an RGBA texture with per-pixel alpha,
    transparent where nothing is drawn, so the sun shows through the hole, and the glare goes over the sky. Under the
    sun, straight on the black the window is cleared to, goes the Milky Way (graphics/milky_way.py). See
    graphics/star_gl.py. The SurfaceLight is built once per frame here from `Navigation.direction_to_star` and passed
    down to the renderers. Software surfaces are uploaded to OpenGL as BGRA straight from `surface.get_buffer()`
    (`_upload_texture`; 32-bit BGRA surfaces only, other formats fall back to `image.tostring`). Both were measured at
    about 14 ms per frame, so avoid per-frame `pygame.transform.scale` of full-window surfaces and per-frame
    `image.tostring`."""

    def __init__(self) -> None:
        self.world_surface: Optional[pygame.Surface] = None
        self.overlay_surface: Optional[pygame.Surface] = None
        self.world_texture: Optional[int] = None
        self.overlay_texture: Optional[int] = None
        self.dialog_texture: Optional[int] = None
        self._uploaded_textures: set = set()
        # While the pilot is inside an outpost, what takes the whole window in place of the cockpit: it is given the
        # window's size and returns the layer to show. Dialogs are drawn over it (see draw).
        self.full_screen_source: Optional[Callable[[Tuple[int, int]], pygame.Surface]] = None

    @staticmethod
    def preload_textures() -> None:
        """Builds the textures of the ore fields, mines and outposts now, while the window is being set up, rather than
        on the first frame that shows one (a hang of about 0.1 s, see common/frame_watch.py). Needs the OpenGL window
        to exist; the textures are kept for the whole run."""
        OreFields._get_ore_field_texture()
        OreMines._get_mine_texture()
        OreMines._get_mine_texture(inactive=True)
        Outposts._get_texture()

    # region Frame
    def draw(self, screen: pygame.Surface, fonts: Any, environment: GameEnvironment, player: Player,
             top_layer: Optional[pygame.Surface] = None) -> None:
        """Render one complete frame into the active OpenGL window.

        top_layer, if given, is a window-sized RGBA layer (a dialog, see Dialog.compose_overlay)
        drawn above everything else. With a `full_screen_source`, that layer is all there is to draw, and top_layer goes
        over it."""
        if self.full_screen_source is not None:
            layer = self.full_screen_source(pygame.display.get_window_size())
            if top_layer is not None:
                layer.blit(top_layer, (0, 0))
            self.draw_full_screen(layer)
            return
        # The real window size, not screen.get_size(): for an OpenGL window pygame can keep returning
        # a surface of the size first requested, which then differs from the window's client area
        # (the window frame takes part of it), cropping the frame and shifting mouse positions.
        width, height = pygame.display.get_window_size()
        self._ensure_surfaces(width, height)
        DebugFps.tick()

        ship = player.ship
        self.world_surface.fill((0, 0, 0, 0))  # transparent: what is behind the sky (the Milky Way) shows through
        frame_watch.mark('sky fill')
        DistantStars.draw(self.world_surface, width, height, environment, ship)
        frame_watch.mark('distant stars')
        OtherWorlds.draw(self.world_surface, width, height, environment, ship, behind_star=True)
        view = view_of(environment, ship, width, height)
        if view is not None:
            erase(self.world_surface, view, width, height)  # the sun shows through the sky here
        OtherWorlds.draw(self.world_surface, width, height, environment, ship, behind_star=False)
        frame_watch.mark('other worlds')
        OrbitPath.draw(self.world_surface, width, height, environment, ship)
        frame_watch.mark('orbit path')
        # The sun, for the surface while bound (the ground and the disc beyond it are lit by it).
        light = SurfaceLight.of(ship, environment) if ship.is_bound else None
        if light is not None:
            FixedWorld.draw_surface(self.world_surface, width, height, environment, ship, light.ground_colour())
        elif ship.is_bound:
            LitWorlds.draw_targeted(self.world_surface, width, height, environment, ship)
        frame_watch.mark('fixed world')
        OutpostMarkers.draw(self.world_surface, width, height, environment, ship)
        frame_watch.mark('outpost markers')

        self.overlay_surface.fill((0, 0, 0, 0))
        frame_watch.mark('overlay fill')
        Cockpit.draw(self.overlay_surface, fonts, width, height, player, environment.date_time)
        frame_watch.mark('cockpit')
        Starlight.tint_cockpit(self.overlay_surface, environment, ship)
        frame_watch.mark('cockpit tint')
        HeatVignette.draw(self.overlay_surface, width, height, ship)
        FrostVignette.draw(self.overlay_surface, width, height, ship)
        frame_watch.mark('vignettes')
        DebugFps.draw(self.overlay_surface, fonts.get(max(9, int(height * 0.017))))

        GL.glViewport(0, 0, width, height)
        GL.glClearColor(SPACE_COLOR[0] / 255, SPACE_COLOR[1] / 255, SPACE_COLOR[2] / 255, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        MilkyWay.draw(width, height, ship, environment.date_time)
        if view is not None:
            seconds = (environment.date_time - environment.EPOCH).total_seconds()
            StarGl.draw_star(width, height, view, seconds, player.time_scale)
        self._draw_texture(self.world_surface, self.world_texture)
        if view is not None:
            visibility = sun_visibility(environment, ship, view)
            StarGl.draw_glare(width, height, view, view.star, visibility)
            StarGl.draw_visor(width, height, visibility * visor_strength(view.disc_px))
        if not ship.is_bound:
            Asteroids.draw(width, height, ship, environment)
        frame_watch.mark('space')
        # Nothing is seen beyond MAX_DEPTH, so above it there is no ground and no rocks to draw; and a ship that outruns
        # the rocks (see Navigation.outruns_rocks) sees none either.
        if light is not None and ship.position.y <= MAX_DEPTH and not ship.navigation.outruns_rocks:
            km2s = RockBatches.visible_km2s(environment.fixed_world, ship.position.x, ship.position.z)
            ore_fields = [field for km2 in km2s for field in km2.ore_fields + km2.external_fields]
            Rocks.draw(
                width, height, ship, km2s, ore_fields, [mine for field in ore_fields for mine in field.mines],
                self._outposts(environment, ship), light, environment.date_time,
            )
        frame_watch.mark('surface')
        Laser.draw(width, height, ship)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(self.overlay_surface, self.overlay_texture)
        if top_layer is not None:
            self._draw_texture(top_layer, self.dialog_texture)

    def draw_full_screen(self, layer: pygame.Surface) -> None:
        """Renders `layer` alone over the whole window: no game frame and no cockpit (the host draws what it wants
        over it, such as the clock)."""
        width, height = pygame.display.get_window_size()
        self._ensure_surfaces(width, height)
        GL.glViewport(0, 0, width, height)
        GL.glClearColor(SPACE_COLOR[0] / 255, SPACE_COLOR[1] / 255, SPACE_COLOR[2] / 255, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(layer, self.dialog_texture)

    def _outposts(self, environment: GameEnvironment, ship: Ship) -> List[Outpost]:
        """Outposts of the fixed world (planets only) within draw distance of the ship.

        Taken from the world's own outposts, not from loaded Km2s, so they do not appear and disappear with
        the Km2 loading around the ship."""
        world = environment.fixed_world
        if world.parent_planet is not None or not world.outposts:
            return []
        return [
            outpost for outpost in world.outposts.values()
            if math.hypot(outpost.longitude - ship.position.x, outpost.latitude - ship.position.z) < MAX_DEPTH
        ]
    # endregion

    # region Textures
    def _ensure_surfaces(self, width: int, height: int) -> None:
        size = (width, height)
        if self.world_surface is None or self.world_surface.get_size() != size:
            self.world_surface = pygame.Surface(size, pygame.SRCALPHA, 32).convert_alpha()
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

    def _draw_texture(self, surface: pygame.Surface, texture: int) -> None:
        """Draws `surface` over the whole window, blended by its alpha, through `texture`."""
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
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
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
    # endregion
