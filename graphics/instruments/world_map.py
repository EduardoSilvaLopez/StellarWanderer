"""World map display (multi-function display)."""

from __future__ import annotations
from typing import Any, Callable, List, Optional, Tuple, TYPE_CHECKING
import math
import pygame
from datetime import datetime
from ..constants import ACCENT, ACCENT_DIM

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from galaxies.world import World

MINE_MARK_COLOR = (255, 255, 0)

# Zoom: while the mouse is over the map, the wheel zooms in logarithmic steps, centred on the ship.
# The scales are fixed values in metres per pixel (1, 2, 5, 10, ...) down to MIN_SCALE, so a step means the same
# on every world; the coarsest level is the whole world. A zoomed map can be dragged with the left button, and
# recentres on the ship when the zoom changes or the button is released.
MIN_SCALE = 1.0
FIRST_ZOOM_RATIO = 1.5  # the first zoomed scale is at least this much finer than the whole-world map

# Where an object is on the screen, or None when it is outside what is drawn.
PixelFunction = Callable[[float, float], Optional[Tuple[int, int]]]


class WorldMap:
    """Draw a world map showing player position in the MFD (multi-function display).

    Bound only. It shows the outposts of the planet as white dots with their names (the name goes towards the middle
    of the map: left of the dot in its right half, below it in its upper half, and is kept inside the map), the ore
    mines of the world (`World.registered_mines`) as small yellow crosses, and the player as a bright dot. Rocks are
    not shown.

    With the mouse over the map, its header shows the scale instead of the world's name and the mouse wheel zooms,
    centred on the ship (the ship's dot stays at the middle until the map is dragged). The levels are fixed scales in
    metres per pixel (1, 2, 5, 10, ... down to MIN_SCALE, 1 m/px), after the whole-world map, which is level 0
    (`_scale_levels`); one step means the same on every world. A zoomed map uses the same scale on both axes and the
    flat offsets from the ship (as the 3D view does), wraps longitude around the world, and draws the world's boundary
    where it falls. A left-button drag over the zoomed map moves the content with the pointer, like a hand; releasing
    the button, and any zoom change, recentre it on the ship. When the mouse leaves, the map goes back to the whole
    world and the name returns (unless a drag is in progress). `main` polls the mouse once per frame (`set_mouse`)
    and routes MOUSEWHEEL to `zoom` while bound."""

    mouse: Optional[Tuple[int, int]] = None  # last mouse position, None when the window has no mouse focus
    hovered: bool = False  # whether, when the map was last drawn, the mouse was over it
    zoom_index: int = 0  # 0 = the whole world; each step is a finer scale
    dragging: bool = False  # a left-button drag that started over the zoomed map is in progress
    drag_position: Optional[Tuple[int, int]] = None  # the pointer at the previous frame of the drag
    pan: Tuple[float, float] = (0.0, 0.0)  # screen pixels the content has moved since the drag started
    area: Optional[pygame.Rect] = None  # the map's area, as last drawn
    _was_pressed: bool = False

    @staticmethod
    def set_mouse(position: Tuple[int, int], focused: bool, pressed: bool) -> None:
        """Called once per frame by the main loop: the mouse position, whether the window has the mouse, and whether
        the left button is down. A press starts a drag only when it begins over the zoomed map."""
        was_pressed = WorldMap._was_pressed
        WorldMap._was_pressed = pressed
        WorldMap.mouse = position if focused else None
        if not pressed:
            WorldMap.dragging = False
            WorldMap.drag_position = None
            WorldMap.pan = (0.0, 0.0)
            return
        if not was_pressed:
            over_zoomed_map = WorldMap.area is not None and WorldMap.area.collidepoint(position) and WorldMap.zoom_index > 0
            WorldMap.dragging = over_zoomed_map
            WorldMap.drag_position = position if WorldMap.dragging else None
            WorldMap.pan = (0.0, 0.0)
        elif WorldMap.dragging and WorldMap.drag_position is not None:
            pan_x, pan_y = WorldMap.pan
            WorldMap.pan = (pan_x + position[0] - WorldMap.drag_position[0],
                            pan_y + position[1] - WorldMap.drag_position[1])
            WorldMap.drag_position = position

    @staticmethod
    def zoom(steps: int) -> bool:
        """Step the zoom (positive = closer) while the mouse is over the map. Returns whether it was."""
        if not WorldMap.hovered:
            return False
        WorldMap._set_zoom(max(0, WorldMap.zoom_index + steps))  # draw() limits it to the finest level
        return True

    @staticmethod
    def _set_zoom(index: int) -> None:
        """Changes the zoom level; every change recentres the view on the ship."""
        if index != WorldMap.zoom_index:
            WorldMap.zoom_index = index
            WorldMap.pan = (0.0, 0.0)

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, mfd: pygame.Rect, h: int, ship: Ship, date_time: datetime) -> None:
        """Draw the world map.

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            mfd: Rectangle for the multi-function display
            h: Window height
            ship: Ship object with position and world info
            date_time: Current in-game date/time, for local year/day progress
        """
        import game_environment as gem
        world = gem.current_environment.nearest_world
        radius = world.radius

        # The header's height sets where the map starts; the header itself is drawn once the zoom is known.
        title_size = max(9, int(h * 0.017))
        world_name_text = fonts.render_to_fit(world.name, ACCENT, mfd.width - 12, title_size)

        # Map area below header — sits on the beveled mfd screen drawn by the caller.
        map_area = mfd.inflate(-8, 0)
        map_area.top = mfd.top + world_name_text.get_height() + 9
        map_area.height = mfd.bottom - 5 - map_area.top

        # World bounds rectangle (normalized to map area)
        # Longitude: -π*radius to +π*radius (horizontal)
        # Latitude: -π*radius/2 to +π*radius/2 (vertical)
        map_padding = 4
        inner_area = map_area.inflate(-map_padding * 2, -map_padding * 2)

        # The mouse over the map zooms it; leaving it goes back to the whole world.
        WorldMap.area = inner_area
        WorldMap.hovered = WorldMap.mouse is not None and inner_area.collidepoint(WorldMap.mouse)
        if not WorldMap.hovered and not WorldMap.dragging:
            WorldMap._set_zoom(0)
        levels = WorldMap._scale_levels(2.0 * math.pi * radius / inner_area.width)
        WorldMap._set_zoom(min(WorldMap.zoom_index, len(levels) - 1))
        scale = levels[WorldMap.zoom_index]

        # Header: the scale while the mouse is over the map, else the world's name; flanked by local year/day.
        header_text = world_name_text
        if WorldMap.hovered:
            header_text = fonts.render_to_fit(f'1 px = {WorldMap._format_scale(scale)}', ACCENT, mfd.width - 12, title_size)
        header_rect = header_text.get_rect(midtop=(mfd.centerx, mfd.top + 5))
        surface.blit(header_text, header_rect)

        side_font_size = max(8, int(h * 0.013))
        side_gap = max(6, int(h * 0.008))
        year_percent = int(100 * world.local_year_fraction(date_time))
        day_percent = int(100 * world.local_day_fraction(date_time))

        year_text = fonts.render_to_fit(
            f'Local Y: {year_percent}%', ACCENT_DIM, max(20, header_rect.left - mfd.left - side_gap), side_font_size
        )
        surface.blit(year_text, year_text.get_rect(midleft=(mfd.left + side_gap, header_rect.centery)))

        day_text = fonts.render_to_fit(
            f'Local D: {day_percent}%', ACCENT_DIM, max(20, mfd.right - header_rect.right - side_gap), side_font_size
        )
        surface.blit(day_text, day_text.get_rect(midright=(mfd.right - side_gap, header_rect.centery)))

        if WorldMap.zoom_index == 0:
            pygame.draw.rect(surface, ACCENT_DIM, inner_area, 1)  # the world rectangle

            def to_pixel(lon: float, lat: float) -> Optional[Tuple[int, int]]:
                return WorldMap._map_point(lon, lat, radius, inner_area)

            WorldMap._draw_contents(surface, fonts, h, world, ship, to_pixel, inner_area)
            return

        # Zoomed: the window around the ship, `scale` metres per pixel, the ship at its centre until dragged. The flat
        # offsets are what the 3D view shows. Longitude wraps around the world; latitude stops at the poles.
        half_world = math.pi * radius
        ship_lon, ship_lat = ship.position.x, ship.position.z
        pan_x, pan_y = WorldMap.pan
        # The content follows the pointer: moving it right or down moves the view's centre left or up.
        centre_lon, centre_lat = ship_lon - pan_x * scale, ship_lat + pan_y * scale
        centre_x, centre_y = inner_area.center

        def zoomed_pixel(lon: float, lat: float) -> Optional[Tuple[int, int]]:
            east = (lon - centre_lon + half_world) % (2.0 * half_world) - half_world  # the nearest copy of the point
            x = centre_x + east / scale
            y = centre_y - (lat - centre_lat) / scale
            return (int(x), int(y)) if inner_area.collidepoint(x, y) else None

        previous_clip = surface.get_clip()
        surface.set_clip(inner_area)
        left = centre_x + (-half_world - centre_lon) / scale
        right = centre_x + (half_world - centre_lon) / scale
        top = centre_y - (half_world / 2 - centre_lat) / scale
        bottom = centre_y - (-half_world / 2 - centre_lat) / scale
        pygame.draw.rect(surface, ACCENT_DIM, pygame.Rect(round(left), round(top), round(right - left), round(bottom - top)), 1)
        WorldMap._draw_contents(surface, fonts, h, world, ship, zoomed_pixel, inner_area)
        surface.set_clip(previous_clip)

    @staticmethod
    def _scale_levels(full_scale: float) -> List[float]:
        """Metres per pixel of each zoom level, coarsest first: the whole world (`full_scale`), then 1-2-5 steps
        from the first one clearly finer than the whole map down to MIN_SCALE."""
        steps = sorted((mantissa * 10.0 ** power for power in range(9) for mantissa in (1, 2, 5)), reverse=True)
        return [full_scale] + [step for step in steps if MIN_SCALE <= step < full_scale / FIRST_ZOOM_RATIO]

    @staticmethod
    def _format_scale(metres: float) -> str:
        """Metres per pixel with three significant figures, in m or Km."""
        return f'{metres / 1000:.3g} Km' if metres >= 1000 else f'{metres:.3g} m'

    @staticmethod
    def _draw_contents(surface: pygame.Surface, fonts: Any, h: int, world: World, ship: Ship,
                       to_pixel: PixelFunction, area: pygame.Rect) -> None:
        """Everything the map shows: the outposts (planets only; moons have none), the ore mines and the
        player. Rocks are not shown."""
        WorldMap._draw_outposts(surface, fonts, h, world, to_pixel, area)
        WorldMap._draw_mines(surface, world, to_pixel)

        # Player position as a brilliant dot
        player_pixel = to_pixel(ship.position.x, ship.position.z)
        if player_pixel is not None:
            dot_radius = max(2, int(h * 0.003))
            pygame.draw.circle(surface, ACCENT, player_pixel, dot_radius)
            pygame.draw.circle(surface, (255, 255, 255), player_pixel, max(1, dot_radius - 1))

    @staticmethod
    def _map_point(lon: float, lat: float, radius: float, area: pygame.Rect) -> Tuple[int, int]:
        """Pixel position of a surface point (longitude, latitude in metres) inside the map area."""
        lon_min = -math.pi * radius
        lon_max = math.pi * radius
        lat_min = -math.pi * radius / 2
        lat_max = math.pi * radius / 2
        # Normalize to [0, 1], clamped in case of floating point errors.
        norm_lon = max(0, min(1, (lon - lon_min) / (lon_max - lon_min)))
        norm_lat = max(0, min(1, (lat - lat_min) / (lat_max - lat_min)))
        # Top of the map is the maximum latitude.
        return int(area.left + norm_lon * area.width), int(area.top + (1 - norm_lat) * area.height)

    @staticmethod
    def _draw_mines(surface: pygame.Surface, world: World, to_pixel: PixelFunction) -> None:
        """A small yellow cross per ore mine of the world (its registered_mines)."""
        arm = 3
        for mine_pos in world.registered_mines:
            pixel = to_pixel(mine_pos[0], mine_pos[1])
            if pixel is None:
                continue
            x, y = pixel
            pygame.draw.line(surface, MINE_MARK_COLOR, (x - arm, y - arm), (x + arm, y + arm), 2)
            pygame.draw.line(surface, MINE_MARK_COLOR, (x - arm, y + arm), (x + arm, y - arm), 2)

    @staticmethod
    def _draw_outposts(surface: pygame.Surface, fonts: Any, h: int, world: World, to_pixel: PixelFunction,
                       area: pygame.Rect) -> None:
        """White dot per outpost, with its name beside it. The label goes towards the middle of `area`
        (left when the dot is in the right half, above when in the lower half), and is kept inside it."""
        if world.parent_planet is not None or not world.outposts:
            return
        font = fonts.get(max(9, int(h * 0.014)))
        gap_x, gap_y = 6, 4
        centre_x, centre_y = area.centerx, area.centery
        for outpost in world.outposts.values():
            pixel = to_pixel(outpost.longitude, outpost.latitude)
            if pixel is None:
                continue
            x, y = pixel
            text = font.render(outpost.name, True, (255, 255, 255))
            rect = text.get_rect()
            if x > centre_x:
                rect.right = x - gap_x  # right half: label on the left
            else:
                rect.left = x + gap_x  # left half: label on the right
            if y > centre_y:
                rect.bottom = y - gap_y  # lower half: label above
            else:
                rect.top = y + gap_y  # upper half: label below
            rect.clamp_ip(area)
            surface.blit(text, rect)
            pygame.draw.circle(surface, (255, 255, 255), (x, y), 2)
