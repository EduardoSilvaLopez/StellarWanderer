"""Altitude meter: the altitude above the surface of the world the ship is bound to, shown while bound.
While unbound, the ProximityMeter is shown in its place."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM, SPEED_WARNING_RED
from .common import draw_beveled_panel, bezel_depth

if TYPE_CHECKING:
    from spaceships.ship import Ship


class AltitudeMeter:
    """Altitude bar labelled ALT: from the surface (altitude 0) to the unbinding altitude, which is
    (UNBIND_RADIUS_MULTIPLE - 1.0) × radius above the surface."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        bar_w = int(w * 0.028)
        bar_h = cluster_height
        bar_rect = pygame.Rect(cluster_left, cluster_top, bar_w, bar_h)
        draw_beveled_panel(surface, bar_rect, depth=bezel_depth(h))

        import game_environment as gem
        from spaceships.navigation import Navigation
        world = gem.current_environment.fixed_world
        # Meter spans from surface (altitude=0) to unbinding altitude
        unbinding_altitude = world.radius * (Navigation.UNBIND_RADIUS_MULTIPLE - 1.0)
        altitude_fraction = ship.position.y / unbinding_altitude if unbinding_altitude > 0 else 0
        altitude_fraction = min(1.0, max(0.0, altitude_fraction))

        fill_pad = 3
        filled = int((bar_h - fill_pad * 2) * altitude_fraction)
        pygame.draw.rect(
            surface, ACCENT,
            (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_w - fill_pad * 2, filled)
        )

        label_font = fonts.get(max(9, int(h * 0.017)))
        warning = ship.navigation.altitude_warning()
        alt_label = label_font.render('ALT', True, SPEED_WARNING_RED if warning else ACCENT_DIM)
        surface.blit(alt_label, alt_label.get_rect(midtop=(cluster_left + bar_w // 2, cluster_top - 30)))
