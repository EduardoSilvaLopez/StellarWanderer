"""Proximity meter: the vicinity of the targeted body (distance, approach speed), shown while unbound. The bar and the
indicators are two columns of the console, drawn separately."""

from __future__ import annotations
from typing import Any, Tuple, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_LABEL, BINDING_NEAR_GREEN, SPEED_WARNING_RED
from .common import draw_beveled_panel, bezel_depth
from common.units import format_compact_distance, format_compact_speed

if TYPE_CHECKING:
    from spaceships.ship import Ship

Colour = Tuple[int, int, int]


class ProximityMeter:
    """Proximity meter showing the vicinity of the targeted body (`GameEnvironment.targeted_body`).

    The bar is a column of the full height of the map. Its fill is the scale of the fixed zone, drawn only while the
    ship is in that body's fixed zone, from the surface (bottom) to the fixed zone's edge (top): 1.0x radius distance
    from centre at the bottom, FIXED_ZONE_RADIUS_MULTIPLE x radius at the top. Outside the fixed zone the bar stays
    empty.

    The indicators are a column to the left of the bar, one row each, top down: the label FIXED, green, while the ship
    is in the fixed zone, else TARGET, then the target's name; "Distance:"; "Approaching:"; "Drift:". Each value sits on
    its label's row, after the label.

    The "Approaching" readout is the signed rate of change of the distance to the targeted body
    (`Navigation.approach_speed`: the velocity relative to the body along the line to its centre; positive approaching,
    negative moving away, sideways motion does not count), formatted with `format_compact_speed` (`+500 m/s`,
    `-3 Km/s`). "Drift" is the speed across that line (`Navigation.drift_speed`), unsigned. In the fixed zone the
    "Distance" and "Approaching:" labels and the Approaching readout turn red when `Navigation.collision_warning` holds:
    keeping its direction relative to the body, the ship reaches the surface even braking with only
    `Navigation.COLLISION_BRAKE_FRACTION` of `Ship.BRAKE_ACC` (a straight-line check, sideways dodging not considered).
    """

    @staticmethod
    def draw_bar(surface: pygame.Surface, h: int, ship: Ship, bar_rect: pygame.Rect) -> None:
        """The fixed zone's scale in `bar_rect`: a beveled panel, filled from the bottom while the ship is in the fixed
        zone."""
        import game_environment as gem
        from spaceships.navigation import Navigation
        body = gem.current_environment.targeted_body

        draw_beveled_panel(surface, bar_rect, depth=bezel_depth(h))
        if not ship.navigation.in_fixed_zone(body):
            return
        distance_from_centre = ship.navigation.distance_to_body_centre(body)
        distance_fraction = (distance_from_centre / body.radius - 1.0) / (Navigation.FIXED_ZONE_RADIUS_MULTIPLE - 1.0)
        distance_fraction = min(1.0, max(0.0, distance_fraction))

        fill_pad = 3
        inner_height = bar_rect.height - fill_pad * 2
        filled = int(inner_height * distance_fraction)
        pygame.draw.rect(
            surface, ACCENT,
            (bar_rect.left + fill_pad, bar_rect.bottom - fill_pad - filled, bar_rect.width - fill_pad * 2, filled)
        )

    @staticmethod
    def draw_indicators(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, column: pygame.Rect) -> None:
        """The target's state, the name on the first row, then the distance, approach and drift, each value on the same
        line after its label, from the top of `column`."""
        import game_environment as gem
        body = gem.current_environment.targeted_body

        label_font = fonts.get(max(9, int(h * 0.017)))
        row_height = label_font.get_height() + 2
        gap = label_font.size(' ')[0]
        pad = 4
        left = column.left + pad

        in_fixed_zone = ship.navigation.in_fixed_zone(body)
        collision_warning = in_fixed_zone and ship.navigation.collision_warning(body)
        label_colour = SPEED_WARNING_RED if collision_warning else ACCENT_LABEL  # the labels of distance and approach
        approach_colour = SPEED_WARNING_RED if collision_warning else ACCENT

        def draw_pair(row: int, label: str, label_col: Colour, value: str, value_col: Colour) -> None:
            """A label and its value on one row, the value right after the label."""
            label_surf = label_font.render(label, True, label_col)
            row_y = column.top + pad + row * row_height
            surface.blit(label_surf, (left, row_y))
            surface.blit(label_font.render(value, True, value_col), (left + label_surf.get_width() + gap, row_y))

        centre_dist = format_compact_distance(ship.navigation.distance_to_body_centre(body))
        draw_pair(0, 'FIXED' if in_fixed_zone else 'TARGET', BINDING_NEAR_GREEN if in_fixed_zone else ACCENT, body.name,
                  ACCENT)
        draw_pair(1, 'Distance:', label_colour, centre_dist, ACCENT)
        draw_pair(2, 'Approaching:', label_colour, format_compact_speed(ship.navigation.approach_speed(body)),
                  approach_colour)
        draw_pair(3, 'Drift:', ACCENT_LABEL, f'{format_compact_distance(ship.navigation.drift_speed(body))}/s', ACCENT)
