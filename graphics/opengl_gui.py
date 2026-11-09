"""OpenGL-backed frame composition for the cockpit view."""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional, List, Any, Tuple
import ctypes
import math

import numpy as np
import pygame
from OpenGL import GL

from common.frame_watch import frame_watch
from .constants import CONSOLE_TOP, SPACE_COLOR, MAX_DEPTH
from .cockpit import Cockpit
from .milky_way import MilkyWay
from .distant_stars import DistantStars
from .local_star import view_of, erase, sun_visibility
from .star_gl import StarGl
from .star_surface import visor_strength
from .starlight import Starlight, AtmosphereLight, HeatVignette
from .debug_fps import DebugFps
from .lit_worlds import LitWorlds
from .outpost_markers import OutpostMarkers
from .fixed_world import FixedWorld
from .orbit_path import OrbitPath
from .asteroids import Asteroids
from .portal_base_gl import PortalBaseGl
from .portal_gl import PortalGl
from .other_worlds import OtherWorlds
from .rocks import Rocks
from .rock_batches import RockBatches
from .terrain_gl import TerrainGl
from .ore_fields import OreFields
from .ore_mines import OreMines
from .outposts import Outposts
from .giant_gl import GiantGl
from .laser import Laser
from .surface_light import SurfaceLight
from .scoop_view import ScoopView
from .instruments.scanner import Scanner

if TYPE_CHECKING:
    from galaxies.people.player import Player
    from spaceships.ship import Ship
    from game_environment import GameEnvironment
    from galaxies.outpost import Outpost


class OpenGLGui:
    """Compose the software UI and depth-tested OpenGL rock pass.

    The sky is layered, from the back: the fixed stars (dots drawn straight in OpenGL), the giants (their haze and rings
    cover the stars; see graphics/giant_gl.py), the sun, and the rest of the sky (the worlds farther than the sun, a hole
    where the sun is, the worlds nearer than it, the targeted body), an RGBA texture with per-pixel alpha, transparent where
    nothing is drawn, so the sun shows through the hole, and the glare goes over the sky. Under the
    sun, straight on the black the window is cleared to, goes the Milky Way (graphics/milky_way.py). See
    graphics/star_gl.py. The giants (graphics/giant_gl.py) are under the sky too, after the sun: the sky is made
    transparent over each, once what is farther than it is drawn. The SurfaceLight is built once per frame here from
    `Navigation.direction_to_star` and passed down to the renderers. Software surfaces are uploaded to OpenGL as BGRA straight from `surface.get_buffer()`
    (`_upload_texture`; 32-bit BGRA surfaces only, other formats fall back to `image.tostring`). Both were measured at
    about 14 ms per frame, so avoid per-frame `pygame.transform.scale` of full-window surfaces and per-frame
    `image.tostring`.

    With the scoop open (Ship.scoop_open) the cockpit leaves the scanner's square empty and the scoop's view is drawn
    over it, after the cockpit (graphics/scoop_view.py), from the Km2s, outposts and asteroids of this frame's passes.

    What does not change from one frame to the next is not drawn nor uploaded again: the console is redrawn
    CONSOLE_REFRESH_FRAMES apart (at once when the mouse moves over it), and the sky's layer only when the view, the
    time or the ship has moved enough to show (`_sky_changed`). A texture is sent to the graphics card straight from the
    surface's memory, and only the rows that changed."""

    CONSOLE_REFRESH_FRAMES = 3  # the console shows nothing that needs to be faster than this
    SKY_TURN_TOLERANCE = 1e-4  # the view's axes may differ this much (about 0.006 degrees) from the sky as drawn
    SKY_SECONDS_TOLERANCE = 2.0  # game seconds the sky may be late
    SKY_HIGH_ALTITUDE = 1000.0  # m: above this, bound, the sky follows the ship's horizontal moves much more closely
    SKY_HIGH_SHIFT = 1.0  # m: the horizontal move (bound, above SKY_HIGH_ALTITUDE) that makes the sky to be drawn again

    def __init__(self) -> None:
        self.world_surface: Optional[pygame.Surface] = None
        self.overlay_surface: Optional[pygame.Surface] = None
        self.world_texture: Optional[int] = None
        self.overlay_texture: Optional[int] = None
        self.dialog_texture: Optional[int] = None
        self._uploaded_textures: set = set()
        self._sky_state: Optional[tuple] = None  # what the world layer was last drawn for (see _sky_changed)
        self._console_frames = self.CONSOLE_REFRESH_FRAMES  # frames since the console was drawn: due at the first
        self._console_mouse: Tuple[int, int] = (-1, -1)
        self._console_scoop_open = False
        # While the pilot is inside an outpost, what takes the whole window in place of the cockpit: it is given the
        # window's size and returns the layer to show. Dialogs are drawn over it (see draw).
        self.full_screen_source: Optional[Callable[[Tuple[int, int]], pygame.Surface]] = None

    @staticmethod
    def preload_textures() -> None:
        """Builds the textures of the ore fields, mines and outposts now, while the window is being set up, rather than
        on the first frame that shows one (a hang of about 0.1 s, see common/frame_watch.py), and starts the helper
        processes of the terrain. Needs the OpenGL window to exist; the textures are kept for the whole run."""
        OreFields._get_ore_field_texture()
        OreMines._get_mine_texture()
        OreMines._get_mine_texture(inactive=True)
        Outposts._get_texture()
        PortalBaseGl.preload_textures()
        TerrainGl.preload()

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
        # The sky and the cockpit's upper part only show above the console, which hides the rest
        console_top = int(height * CONSOLE_TOP)
        sky = pygame.Rect(0, 0, width, console_top)
        view = view_of(environment, ship, width, height)
        # The sun, for the surface while bound (the ground and the disc beyond it are lit by it).
        light = SurfaceLight.of(ship, environment) if ship.is_bound else None
        sky_redrawn = self._sky_changed(environment, ship, player, width, height)
        if sky_redrawn:
            self.world_surface.fill((0, 0, 0, 0), sky)  # transparent: what is behind the sky shows through
            frame_watch.mark('sky fill')
            erasers = GiantGl.sky_erasers(environment, ship, width, height)
            OtherWorlds.draw(self.world_surface, width, height, environment, ship, behind_star=True, erasers=erasers)
            if view is not None:
                erase(self.world_surface, view, width, height)  # the sun shows through the sky
            OtherWorlds.draw(self.world_surface, width, height, environment, ship, behind_star=False, erasers=erasers)
            frame_watch.mark('other worlds')
            OrbitPath.draw(self.world_surface, width, height, environment, ship)
            frame_watch.mark('orbit path')
            if light is not None:
                FixedWorld.draw_surface(self.world_surface, width, height, environment, ship, light.ground_colour())
            elif ship.is_bound:
                LitWorlds.draw_targeted(self.world_surface, width, height, environment, ship)
            frame_watch.mark('fixed world')
            OutpostMarkers.draw(self.world_surface, width, height, environment, ship)
            frame_watch.mark('outpost markers')

        overlay = self.overlay_surface
        upper = pygame.Rect(0, 0, width, console_top)
        lower = pygame.Rect(0, console_top, width, height - console_top)
        overlay.set_clip(upper)
        Cockpit.draw_upper(overlay, fonts, width, height, player, environment.date_time)
        frame_watch.mark('cockpit')
        self._tint_and_vignette(overlay, environment, ship, width, height)
        DebugFps.draw(overlay, fonts.get(max(9, int(height * 0.017))))
        frame_watch.mark('cockpit tint')
        console_redrawn = self._console_due(ship, lower)
        if console_redrawn:
            overlay.set_clip(lower)
            overlay.fill((0, 0, 0, 0), lower)
            Cockpit.draw_console(overlay, fonts, width, height, player, environment.date_time)
            self._tint_and_vignette(overlay, environment, ship, width, height)
        overlay.set_clip(None)

        GL.glViewport(0, 0, width, height)
        GL.glClearColor(SPACE_COLOR[0] / 255, SPACE_COLOR[1] / 255, SPACE_COLOR[2] / 255, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        MilkyWay.draw(width, height, ship, environment.date_time)
        frame_watch.mark('milky way')
        # The layers, from the back: the stars, the giants (their haze and rings cover the stars), the sun, the giants
        # in front of it, and then the rest of the sky (the worlds, moons and the orbit line, which the giants' erasers
        # cut)
        DistantStars.draw(width, height, environment, ship, view, sky_redrawn)
        frame_watch.mark('distant stars')
        GiantGl.draw(width, height, environment, ship, behind_star=True)
        if view is not None:
            seconds = (environment.date_time - environment.EPOCH).total_seconds()
            StarGl.draw_star(width, height, view, seconds, player.time_scale)
        GiantGl.draw(width, height, environment, ship, behind_star=False)
        frame_watch.mark('giants and sun')
        self._draw_texture(self.world_surface, self.world_texture, [(0, sky.height)] if sky_redrawn else [],
                           sky.height)
        frame_watch.mark('world layer')
        if view is not None:
            visibility = sun_visibility(environment, ship, view)
            StarGl.draw_glare(width, height, view, view.star, visibility)
            StarGl.draw_visor(width, height, visibility * visor_strength(view.disc_px))
        if not ship.is_bound and environment.nearest_system.portal is not None:
            # The Portal's glare hides the sky (the stars and the planets), not the base nor the asteroids, which come
            # after it; the Portal and the base are drawn the farthest first, as each is drawn over what is behind it.
            PortalGl.draw_glare(width, height, ship, environment)
            portal_first = PortalGl.is_behind_base(environment, ship)
            if portal_first:
                PortalGl.draw(width, height, ship, environment)
            PortalBaseGl.draw(width, height, ship, environment)
            if not portal_first:
                PortalGl.draw(width, height, ship, environment)
        sightings = [] if ship.is_bound else Asteroids.draw(width, height, ship, environment)
        frame_watch.mark('space')
        # Nothing is seen beyond MAX_DEPTH, so above it there are no rocks to draw (the ground of a world with relief is
        # seen from higher, see TerrainGl.reach); and a ship that outruns
        # the rocks (see Navigation.outruns_rocks) sees none either.
        km2s, outposts = None, []  # None: no rocks are drawn
        reach = TerrainGl.reach(environment.fixed_world)
        if light is not None and ship.navigation.altitude() <= reach and not ship.navigation.outruns_rocks:
            km2s = RockBatches.visible_km2s(environment.fixed_world, ship.position.x, ship.position.z)
            ore_fields = [field for km2 in km2s for field in km2.ore_fields + km2.external_fields]
            outposts = self._outposts(environment, ship)
            Rocks.draw(
                width, height, ship, km2s, ore_fields, [mine for field in ore_fields for mine in field.mines],
                outposts, light, environment.date_time,
            )
        frame_watch.mark('surface')
        Laser.draw(width, height, ship)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._draw_texture(self.overlay_surface, self.overlay_texture,
                           [(0, height if console_redrawn else console_top)])
        if Scanner.scoop_rect is not None:  # the cockpit has just left the scanner's square empty for it
            ScoopView.draw(Scanner.scoop_rect, (width, height), ship, environment, km2s, outposts, light, sightings)
            frame_watch.mark('scoop')
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
        """Outposts of the fixed world (of a planet or a moon) within draw distance of the ship.

        Taken from the world's own outposts, not from loaded Km2s, so they do not appear and disappear with
        the Km2 loading around the ship."""
        world = environment.fixed_world
        if not world.outposts:
            return []
        return [
            outpost for outpost in world.outposts.values()
            if math.hypot(outpost.longitude - ship.position.x, outpost.latitude - ship.position.z) < MAX_DEPTH
        ]
    # endregion

    def _tint_and_vignette(self, overlay: pygame.Surface, environment: GameEnvironment, ship: Ship, width: int,
                           height: int) -> None:
        """What the light and the heat do to the cockpit, within the surface's clip (the part being drawn)."""
        Starlight.tint_cockpit(overlay, environment, ship)
        AtmosphereLight.tint_cockpit(overlay, environment, ship)
        PortalGl.tint_cockpit(overlay, environment, ship)
        HeatVignette.draw(overlay, width, height, ship)

    def _console_due(self, ship: Ship, lower: pygame.Rect) -> bool:
        """Whether the console is redrawn in this frame: every CONSOLE_REFRESH_FRAMES, at once when the mouse moves
        over it (a button answers the pointer) or the scoop opens or closes (the cockpit leaves its square empty)."""
        self._console_frames += 1
        mouse = pygame.mouse.get_pos()
        moved = mouse != self._console_mouse and lower.collidepoint(mouse)
        if (self._console_frames < self.CONSOLE_REFRESH_FRAMES and not moved
                and ship.scoop_open == self._console_scoop_open):
            return False
        self._console_frames, self._console_mouse, self._console_scoop_open = 0, mouse, ship.scoop_open
        return True

    def _sky_changed(self, environment: GameEnvironment, ship: Ship, player: Player, width: int, height: int) -> bool:
        """Whether the world layer of the sky has to be drawn again: the view has turned, the time has moved or the ship
        has gone far enough for the sky to show it, compared with what it was last drawn for. While bound the ship's
        position matters little (the worlds are far, the ground is a disc under it), so it counts for a share of the
        world's radius, except high up, where the ground moves in the sky with every metre and any time passing counts;
        unbound, for a metre."""
        attitude = ship.attitude
        axes = np.array([attitude.right.x, attitude.right.y, attitude.right.z, attitude.up.x, attitude.up.y,
                         attitude.up.z, attitude.forward.x, attitude.forward.y, attitude.forward.z])
        position = np.array([ship.position.x, ship.position.y, ship.position.z])
        seconds = (environment.date_time - environment.EPOCH).total_seconds()
        kind = (width, height, ship.is_bound, id(environment.targeted_body), id(environment.fixed_world),
                player.show_orbits)
        last = self._sky_state
        altitude = ship.navigation.altitude() if ship.is_bound else 0.0
        high = altitude > self.SKY_HIGH_ALTITUDE
        seconds_tolerance = 0.0 if high else self.SKY_SECONDS_TOLERANCE
        if (last is None or last[3] != kind or abs(seconds - last[2]) > seconds_tolerance
                or float(np.abs(axes - last[0]).max()) > self.SKY_TURN_TOLERANCE):
            changed = True
        elif ship.is_bound:
            shift = self.SKY_HIGH_SHIFT if high else 1e-5 * environment.fixed_world.radius
            changed = (math.hypot(position[0] - last[1][0], position[2] - last[1][2]) > shift
                       or abs(position[1] - last[1][1]) > 0.05 * max(altitude, 20.0))
        else:
            changed = float(np.linalg.norm(position - last[1])) > 1.0
        if changed:
            self._sky_state = (axes, position, seconds, kind)
        return changed

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
            self._sky_state = None
            self._console_frames = self.CONSOLE_REFRESH_FRAMES

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

    def _send_rows(self, surface: pygame.Surface, texture: int, first: int, last: int) -> None:
        """Sends rows first..last of a BGRA surface to the texture, straight from the surface's memory (rows are
        contiguous, and the memory is only borrowed for the call: see `_draw_texture`)."""
        width, height = surface.get_size()
        pixels = np.frombuffer(memoryview(surface.get_buffer()), dtype=np.uint8)
        address = pixels.ctypes.data + first * width * 4
        GL.glViewport(0, 0, width, height)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, first, width, last - first, GL.GL_BGRA, GL.GL_UNSIGNED_BYTE,
                           ctypes.c_void_p(address))
        del pixels

    def _draw_texture(self, surface: pygame.Surface, texture: int, upload: Optional[List[Tuple[int, int]]] = None,
                      rows: Optional[int] = None) -> None:
        """Draws `surface` over the whole window, blended by its alpha, through `texture`. `upload` lists the (first,
        last) rows that have changed since the last time, the only ones sent (None: all, as is the first time); `rows`
        is how many rows from the top are drawn (None: all)."""
        width, height = surface.get_size()
        # Keep Pygame's top-to-bottom row order for the top-left screen quad.
        # A 32-bit surface laid out as BGRA is uploaded as a plain copy of its memory, about 2.5x faster than converting
        # with image.tostring on every frame. The memory is borrowed for the call and let go at once, never kept as a
        # memoryview: one can stay exported while OpenGL holds it (that raised BufferError at start, under the
        # debugger) and would keep the surface locked.
        bgra = self._is_bgra32(surface)
        if upload is None or not bgra or texture not in self._uploaded_textures:
            if bgra:
                self._upload_texture(texture, width, height, GL.GL_BGRA, surface.get_buffer().raw)
            else:
                self._upload_texture(texture, width, height, GL.GL_RGBA,
                                     pygame.image.tostring(surface, 'RGBA', False))
        else:
            for first, last in upload:
                self._send_rows(surface, texture, first, last)
        GL.glViewport(0, 0, width, height)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        self._draw_quad(width, height, rows or height)

    @staticmethod
    def _draw_quad(width: int, height: int, rows: int) -> None:
        """The textured quad of the top `rows` of a window-sized texture, at the top of the window."""
        share = rows / height
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
        GL.glTexCoord2f(1, share)
        GL.glVertex2f(width, rows)
        GL.glTexCoord2f(0, share)
        GL.glVertex2f(0, rows)
        GL.glEnd()
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glDisable(GL.GL_TEXTURE_2D)
    # endregion
