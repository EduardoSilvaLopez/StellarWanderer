"""Binding meter: the vicinity of the nearest body (distance, approach speed), shown while unbound."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM, BINDING_NEAR_GREEN, SPEED_WARNING_RED
from .common import draw_beveled_panel, bezel_depth
from common.units import format_compact_distance, format_compact_speed

if TYPE_CHECKING:
    from spaceships.ship import Ship


class BindingMeter:
    """Binding meter showing the vicinity of the nearest body, labelled NEAREST.

    Bottom at surface (1.0x radius distance from centre). Top at braking zone threshold
    (BRAKING_RADIUS_MULTIPLE x radius distance).

    The "Approaching" readout is the signed rate of change of the distance to the nearest body
    (`Navigation.approach_speed`: the velocity relative to the body along the line to its centre; positive approaching,
    negative moving away, sideways motion does not count), formatted with `format_compact_speed` (`+500 m/s`,
    `-3 Km/s`). In the braking zone it turns red when `Navigation.collision_warning` holds: keeping its direction
    relative to the body, the ship reaches the surface even braking with only `Navigation.COLLISION_BRAKE_FRACTION` of
    `Ship.BRAKE_ACC` (a straight-line check, sideways dodging not considered).
    """

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        import game_environment as gem
        body = gem.current_environment.nearest_body

        bar_w = int(w * 0.028)
        label_font = fonts.get(max(9, int(h * 0.017)))
        row_height = label_font.get_height() + 2
        label_top = cluster_top - 46
        bar_top = label_top + label_font.get_height() + 6
        group_bottom = cluster_top + cluster_height + 22
        bar_height = group_bottom - bar_top - row_height * 4 - 2

        bar_rect = pygame.Rect(cluster_left, bar_top, bar_w, bar_height)
        draw_beveled_panel(surface, bar_rect, depth=bezel_depth(h))

        # Meter spans from surface (1.0x radius distance) to braking zone (BRAKING_RADIUS_MULTIPLE x radius)
        from spaceships.navigation import Navigation
        distance_from_centre = ship.navigation.distance_to_body_centre(body)
        distance_fraction = (distance_from_centre / body.radius - 1.0) / (Navigation.BRAKING_RADIUS_MULTIPLE - 1.0)
        distance_fraction = min(1.0, max(0.0, distance_fraction))

        fill_pad = 3
        inner_height = bar_height - fill_pad * 2
        filled = int(inner_height * distance_fraction)
        pygame.draw.rect(
            surface, ACCENT,
            (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_w - fill_pad * 2, filled)
        )

        in_braking_zone = ship.navigation.in_braking_zone(body)
        label = label_font.render('NEAREST', True, BINDING_NEAR_GREEN if in_braking_zone else ACCENT_DIM)
        surface.blit(label, label.get_rect(midtop=(cluster_left + bar_w // 2, label_top)))

        centre_dist = format_compact_distance(distance_from_centre)

        row_y = bar_rect.bottom + 2
        dist_label = label_font.render('Distance', True, ACCENT_DIM)
        surface.blit(dist_label, dist_label.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        centre_text = label_font.render(f'{centre_dist}', True, ACCENT)
        surface.blit(centre_text, centre_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        # Red when, inside the braking zone, a collision is unavoidable even braking part of the time.
        collision_warning = in_braking_zone and ship.navigation.collision_warning(body)

        row_y += row_height
        speed_label = label_font.render('Approaching:', True, SPEED_WARNING_RED if collision_warning else ACCENT_DIM)
        surface.blit(speed_label, speed_label.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        speed_text = label_font.render(
            format_compact_speed(ship.navigation.approach_speed(body)), True, SPEED_WARNING_RED if collision_warning else ACCENT
        )
        surface.blit(speed_text, speed_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))
