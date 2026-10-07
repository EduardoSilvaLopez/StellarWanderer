"""Shared utilities and texture caching for cockpit instruments."""

from __future__ import annotations
import math
import os
import pygame
from typing import Optional, Tuple, TYPE_CHECKING
from Vector3 import Vector3
from ..Constants import (
    CANOPY_TOP, CONSOLE_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET,
    CONSOLE, HULL_EDGE_COLOR, HULL_DARK, READOUT_BG, CONSOLE_EDGE_COLOR,
    VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP,
)

if TYPE_CHECKING:
    from Player import Player


_cockpit_background: Optional[pygame.Surface] = None
_windshield_frame_texture: Optional[pygame.Surface] = None

COMPACT_DISTANCE_UNITS = (('m', 1.0), ('Km', 1e3), ('Mm', 1e6), ('Gm', 1e9), ('Tm', 1e12), ('Pm', 1e15))


def format_compact_distance(meters: float) -> str:
    """Compact format: whole metres below 10^6, then Km, Mm, Gm, Tm and Pm (the last unit), each rounded."""
    for symbol, scale in COMPACT_DISTANCE_UNITS:
        value = round(meters / scale)
        if abs(value) < 1_000_000 or symbol == 'Pm':
            return f'{value} {symbol}'
    return f'{value} {symbol}'


def view_geometry(h: int, horizon_fraction: float = 0.5) -> Tuple[int, int, float]:
    """(view_h, horizon_y, focal_length_px) for a view of window height h.

    horizon_fraction places the horizon within view_h; 0.5 is used by
    draw_surface, ObjectLabels and LocalStar. NearestWorld.draw_rocks/
    draw_ore_fields pass 0.52 instead — kept as a parameter so either
    value is preserved without forcing a behavior change.
    """
    view_h = int(h * CONSOLE_TOP)
    horizon_y = int(view_h * horizon_fraction)
    focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
    return view_h, horizon_y, focal_length_px


def project_to_camera(player: Player, vector: Vector3, w: int, horizon_y: int, focal_length_px: float) -> Optional[Tuple[float, float]]:
    """Pinhole-project a direction (in the frame consumed by player.camera_components)
    onto the screen. Returns None if the direction is behind the near-clip plane."""
    right, cam_up, cam_forward = player.camera_components(vector)
    if cam_forward <= NEAR_CLIP:
        return None
    screen_x = w / 2 + focal_length_px * right / cam_forward
    screen_y = horizon_y - focal_length_px * cam_up / cam_forward
    return screen_x, screen_y


def get_cockpit_background(w: int, h: int) -> pygame.Surface:
    """Load, scale, and apply gradient darkening to cockpit texture.

    Left side gradually darkened, right side normal brightness.
    """
    global _cockpit_background
    if _cockpit_background is None:
        texture_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Resources', 'textures', 'cockpit_background.png')
        try:
            image = pygame.image.load(texture_path)
            result = pygame.transform.scale(image, (w, h))

            # Apply gradient darkening: left side dark, right side normal.
            gradient_overlay = pygame.Surface((w, h))
            min_brightness = 90  # left edge: ~35% brightness
            for x in range(w):
                brightness = int(min_brightness + (255 - min_brightness) * (x / w))
                pygame.draw.line(gradient_overlay, (brightness, brightness, brightness), (x, 0), (x, h), 1)

            result.blit(gradient_overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            _cockpit_background = result
        except (pygame.error, FileNotFoundError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load cockpit background texture from {texture_path}: {e}")
            # Create fallback solid color surface
            fallback = pygame.Surface((w, h))
            fallback.fill((40, 50, 60))
            _cockpit_background = fallback
    return _cockpit_background


def get_windshield_frame_texture(w: int, h: int) -> pygame.Surface:
    """Cockpit texture masked to the windshield's opaque frame shapes
    (top rail, A-pillars, struts) only — the glass panes between them
    stay transparent so the 3D scene keeps showing through.
    """
    global _windshield_frame_texture
    if _windshield_frame_texture is None:
        top = int(h * CANOPY_TOP)
        bottom = int(h * CONSOLE_TOP)
        top_inset = w * CANOPY_TOP_INSET
        bottom_inset = w * CANOPY_BOTTOM_INSET

        mask = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, top))

        left = [(0, 0), (top_inset, top), (bottom_inset, bottom), (0, bottom)]
        right = [(w, 0), (w - top_inset, top), (w - bottom_inset, bottom), (w, bottom)]
        for pillar in (left, right):
            points = [(int(x), int(y)) for x, y in pillar]
            pygame.draw.polygon(mask, (255, 255, 255, 255), points)

        for frac in (1 / 3, 2 / 3):
            half = max(2, int(w * 0.004))
            x_top = top_inset + (w - 2 * top_inset) * frac
            x_bottom = bottom_inset + (w - 2 * bottom_inset) * frac
            strut = [
                (int(x_top - half), top), (int(x_top + half), top),
                (int(x_bottom + half), bottom), (int(x_bottom - half), bottom),
            ]
            pygame.draw.polygon(mask, (255, 255, 255, 255), strut)

        frame_texture = get_cockpit_background(w, h).convert_alpha()
        frame_texture.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        _windshield_frame_texture = frame_texture
    return _windshield_frame_texture


def draw_beveled_panel(surface: pygame.Surface, rect: pygame.Rect, depth: int | None = None, w: int | None = None, h: int | None = None) -> None:
    """Draw a recessed instrument screen: a raised bezel frame around a
    sunken readout, lit from the top-left (bezel highlight top/left,
    shadow bottom/right; screen shadow top/left, inner highlight
    bottom/right) instead of a single flat border line.

    When w and h are provided, the bezel background uses the cockpit texture
    instead of a solid color.
    """
    if depth is None:
        depth = max(2, rect.width // 24)
    outer = rect.inflate(depth * 2, depth * 2)

    if w is not None and h is not None:
        background = get_cockpit_background(w, h)
        try:
            texture_portion = background.subsurface((outer.left, outer.top, outer.width, outer.height))
            surface.blit(texture_portion, outer)
        except (ValueError, pygame.error):
            pygame.draw.rect(surface, CONSOLE, outer)
    else:
        pygame.draw.rect(surface, CONSOLE, outer)

    # Bezel: raised, so light catches top/left and shadow falls bottom/right.
    pygame.draw.line(surface, HULL_EDGE_COLOR, outer.topleft, (outer.right - 1, outer.top), depth)
    pygame.draw.line(surface, HULL_EDGE_COLOR, outer.topleft, (outer.left, outer.bottom - 1), depth)
    pygame.draw.line(surface, HULL_DARK, (outer.left, outer.bottom - depth), (outer.right - 1, outer.bottom - depth), depth)
    pygame.draw.line(surface, HULL_DARK, (outer.right - depth, outer.top), (outer.right - depth, outer.bottom - 1), depth)

    # Screen: sunken, so the shading is reversed — shadow top/left, a thin lit ridge bottom/right.
    pygame.draw.rect(surface, READOUT_BG, rect)
    pygame.draw.line(surface, HULL_DARK, rect.topleft, (rect.right - 1, rect.top), 2)
    pygame.draw.line(surface, HULL_DARK, rect.topleft, (rect.left, rect.bottom - 1), 2)
    pygame.draw.line(surface, HULL_EDGE_COLOR, (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
    pygame.draw.line(surface, HULL_EDGE_COLOR, (rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1), 1)
    pygame.draw.rect(surface, CONSOLE_EDGE_COLOR, rect, 1)
