"""Binding meter: distance from the ship to the nearest world's surface, shown while unbound."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..Constants import ACCENT, ACCENT_DIM, BINDING_MARK_RED
from .common import draw_beveled_panel

if TYPE_CHECKING:
    from Player import Player


class BindingMeter:
    """Bar filled by surface distance relative to the world radius, labelled NEAREST.

    Full at a distance of one radius or more. The red mark sits at half-full, the
    point where the ship binds to the world.
    """

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        import GameEnvironment as gem
        world = gem.current_environment.nearest_world

        bar_w = int(w * 0.028)
        bar_rect = pygame.Rect(cluster_left, cluster_top, bar_w, cluster_height)
        draw_beveled_panel(surface, bar_rect)

        distance_fraction = player.altitude_above_surface(world) / world.radius
        distance_fraction = min(1.0, max(0.0, distance_fraction))

        fill_pad = 3
        inner_height = cluster_height - fill_pad * 2
        filled = int(inner_height * distance_fraction)
        pygame.draw.rect(
            surface, ACCENT,
            (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_w - fill_pad * 2, filled)
        )

        mark_y = bar_rect.bottom - fill_pad - inner_height // 2
        pygame.draw.line(surface, BINDING_MARK_RED, (bar_rect.left, mark_y), (bar_rect.right - 1, mark_y), 2)

        label_font = fonts.get(max(9, int(h * 0.017)))
        label = label_font.render('NEAREST', True, ACCENT_DIM)
        surface.blit(label, label.get_rect(midtop=(cluster_left + bar_w // 2, cluster_top - 30)))
