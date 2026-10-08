"""Altitude meter: displays altitude above the nearest world's surface, shown while unbound."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..Constants import ACCENT, ACCENT_DIM, BINDING_MARK_RED, BINDING_NEAR_GREEN
from .common import draw_beveled_panel, format_compact_distance

if TYPE_CHECKING:
    from Player import Player


class AltitudeMeter:
    """Altitude meter showing the delicate low-altitude zone, labelled NEAREST.

    Bottom at surface (0 altitude). Top at 0.1x radius altitude (unbinding threshold).
    Red mark shows the binding threshold at 0.05x radius altitude (1.5x radius distance).
    """

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        import GameEnvironment as gem
        world = gem.current_environment.nearest_world

        bar_w = int(w * 0.028)
        label_font = fonts.get(max(9, int(h * 0.017)))
        row_height = label_font.get_height() + 2
        label_top = cluster_top - 46
        bar_top = label_top + label_font.get_height() + 6
        group_bottom = cluster_top + cluster_height + 22
        bar_height = group_bottom - bar_top - row_height * 4 - 2

        bar_rect = pygame.Rect(cluster_left, bar_top, bar_w, bar_height)
        draw_beveled_panel(surface, bar_rect)

        # Meter spans from surface (altitude=0) to unbinding altitude
        from Player import Player
        altitude_above_surface = player.altitude_above_surface(world)
        max_altitude = world.radius * Player.UNBINDING_ALTITUDE_MULTIPLIER
        distance_fraction = altitude_above_surface / max_altitude if max_altitude > 0 else 0

        # DEBUG: log the calculation values
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"AltitudeMeter: altitude={altitude_above_surface:.1f}, radius={world.radius:.1f}, max={max_altitude:.1f}, fraction={distance_fraction:.4f}")

        distance_fraction = min(1.0, max(0.0, distance_fraction))

        fill_pad = 3
        inner_height = bar_height - fill_pad * 2
        filled = int(inner_height * distance_fraction)
        pygame.draw.rect(
            surface, ACCENT,
            (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_w - fill_pad * 2, filled)
        )

        # Red mark at binding threshold: 1.5x radius = (UNBINDING_ALTITUDE_MULTIPLIER / 2) of radius altitude
        mark_fraction = (Player.BIND_RADIUS_MULTIPLE - 1.0) / Player.UNBINDING_ALTITUDE_MULTIPLIER
        mark_y = bar_rect.bottom - fill_pad - int(inner_height * mark_fraction)
        pygame.draw.line(surface, BINDING_MARK_RED, (bar_rect.left, mark_y), (bar_rect.right - 1, mark_y), 2)

        # Green when in the braking zone (within 10x radius, not bound): the reference frame
        # uses the planet's velocity, so braking/markers show direction relative to the planet.
        in_braking_zone = (not player.is_bound and
                           player._distance_to_world_centre(world) < 10 * world.radius)
        label = label_font.render('NEAREST', True, BINDING_NEAR_GREEN if in_braking_zone else ACCENT_DIM)
        surface.blit(label, label.get_rect(midtop=(cluster_left + bar_w // 2, label_top)))

        centre_dist = format_compact_distance(player.altitude_above_surface(world) + world.radius)

        row_y = bar_rect.bottom + 2
        dist_label = label_font.render('Distance', True, ACCENT_DIM)
        surface.blit(dist_label, dist_label.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        centre_text = label_font.render(f'{centre_dist}', True, ACCENT)
        surface.blit(centre_text, centre_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        speed_label = label_font.render('Speed', True, ACCENT_DIM)
        surface.blit(speed_label, speed_label.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        speed_text = label_font.render(f'{int(player.speed_relative_to_world(world))}', True, ACCENT)
        surface.blit(speed_text, speed_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))
