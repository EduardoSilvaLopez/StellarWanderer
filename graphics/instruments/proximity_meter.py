"""Proximity meter: the vicinity of the targeted body (distance, approach speed), shown while unbound."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM, BINDING_NEAR_GREEN, SPEED_WARNING_RED
from .common import draw_beveled_panel, bezel_depth
from common.units import format_compact_distance, format_compact_speed

if TYPE_CHECKING:
    from spaceships.ship import Ship


class ProximityMeter:
    """Proximity meter showing the vicinity of the targeted body (`GameEnvironment.targeted_body`). Labelled FIXED, green,
    while the ship is in that body's fixed zone, with the bar as its scale. Otherwise labelled TARGET, with no bar (the
    scale only means something inside the fixed zone), and the target's name under the label in the bar's place.

    Bottom at surface (1.0x radius distance from centre). Top at the fixed zone edge
    (FIXED_ZONE_RADIUS_MULTIPLE x radius distance).

    The "Approaching" readout is the signed rate of change of the distance to the targeted body
    (`Navigation.approach_speed`: the velocity relative to the body along the line to its centre; positive approaching,
    negative moving away, sideways motion does not count), formatted with `format_compact_speed` (`+500 m/s`,
    `-3 Km/s`). In the fixed zone the "Distance" and "Approaching:" labels and the Approaching readout turn red when
    `Navigation.collision_warning` holds: keeping its direction
    relative to the body, the ship reaches the surface even braking with only `Navigation.COLLISION_BRAKE_FRACTION` of
    `Ship.BRAKE_ACC` (a straight-line check, sideways dodging not considered).
    """

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        import game_environment as gem
        body = gem.current_environment.targeted_body

        bar_w = int(w * 0.028)
        label_font = fonts.get(max(9, int(h * 0.017)))
        row_height = label_font.get_height() + 2
        label_top = cluster_top - 46
        bar_top = label_top + label_font.get_height() + 6
        group_bottom = cluster_top + cluster_height + 22
        bar_height = group_bottom - bar_top - row_height * 5 - 2  # five rows below the bar: distance, approach, and the name while fixed

        bar_rect = pygame.Rect(cluster_left, bar_top, bar_w, bar_height)

        # The bar is the scale of the fixed zone: it exists only while the ship is in one. Outside, the bar's space is
        # left empty and the target's name goes there, under TARGET.
        # The target is never in a fixed zone unless it is the fixed body, so this is also "fixed" for the label.
        from spaceships.navigation import Navigation
        in_fixed_zone = ship.navigation.in_fixed_zone(body)
        distance_from_centre = ship.navigation.distance_to_body_centre(body)
        if in_fixed_zone:
            draw_beveled_panel(surface, bar_rect, depth=bezel_depth(h))
            distance_fraction = (distance_from_centre / body.radius - 1.0) / (Navigation.FIXED_ZONE_RADIUS_MULTIPLE - 1.0)
            distance_fraction = min(1.0, max(0.0, distance_fraction))

            fill_pad = 3
            inner_height = bar_height - fill_pad * 2
            filled = int(inner_height * distance_fraction)
            pygame.draw.rect(
                surface, ACCENT,
                (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_w - fill_pad * 2, filled)
            )

        label = label_font.render('FIXED' if in_fixed_zone else 'TARGET', True, BINDING_NEAR_GREEN if in_fixed_zone else ACCENT)
        surface.blit(label, label.get_rect(midtop=(cluster_left + bar_w // 2, label_top)))
        if not in_fixed_zone:
            name_text = label_font.render(body.name, True, ACCENT)
            surface.blit(name_text, name_text.get_rect(midtop=(cluster_left + bar_w // 2, bar_top)))

        centre_dist = format_compact_distance(distance_from_centre)

        # Below the bar while fixed; outside, directly under the target's name, which is in the bar's place.
        row_y = bar_rect.bottom + 2 if in_fixed_zone else bar_top + row_height
        # Red when, inside the fixed zone, a collision is unavoidable even braking part of the time.
        collision_warning = in_fixed_zone and ship.navigation.collision_warning(body)
        label_colour = SPEED_WARNING_RED if collision_warning else ACCENT_DIM  # both labels share it

        dist_label = label_font.render('Distance', True, label_colour)
        surface.blit(dist_label, dist_label.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        centre_text = label_font.render(f'{centre_dist}', True, ACCENT)
        surface.blit(centre_text, centre_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        speed_label = label_font.render('Approaching:', True, label_colour)
        surface.blit(speed_label, speed_label.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        row_y += row_height
        speed_text = label_font.render(
            format_compact_speed(ship.navigation.approach_speed(body)), True, SPEED_WARNING_RED if collision_warning else ACCENT
        )
        surface.blit(speed_text, speed_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))

        # While fixed, the bar is there, so the name goes below the readouts. Outside, it is drawn under TARGET (above).
        if in_fixed_zone:
            row_y += row_height
            name_text = label_font.render(body.name, True, ACCENT)
            surface.blit(name_text, name_text.get_rect(midtop=(cluster_left + bar_w // 2, row_y)))
