"""Proximity meter: the vicinity of the targeted body (distance, approach speed), shown while unbound. The bar and the
instruments that read the target are drawn separately, in the columns the console gives them."""

from __future__ import annotations
import math
from typing import Any, Tuple, TYPE_CHECKING
import pygame
from ..constants import (ACCENT, ACCENT_DIM, ACCENT_LABEL, ADVICE_ACCELERATE_COLOR, ADVICE_COLOR,
                         ADVICE_DECELERATE_COLOR, ADVICE_STAY_COLOR, BINDING_NEAR_GREEN, SPEED_WARNING_RED)
from .common import draw_beveled_panel, bezel_depth
from common.units import format_compact_distance, format_compact_duration, format_compact_speed
from spaceships.long_distance_advice import Advice, LongDistanceAdvisor

if TYPE_CHECKING:
    from galaxies.body import Body
    from spaceships.ship import Ship

Colour = Tuple[int, int, int]


def _draw_pair(surface: pygame.Surface, label_font: Any, left: int, top: int, label: str, label_col: Colour,
               value: str, value_col: Colour) -> None:
    """A label and its value on one row, the value right after the label."""
    label_surf = label_font.render(label, True, label_col)
    surface.blit(label_surf, (left, top))
    value_left = left + label_surf.get_width() + label_font.size(' ')[0]
    surface.blit(label_font.render(value, True, value_col), (value_left, top))


class ProximityMeter:
    """Proximity meter showing the vicinity of the targeted body (`GameEnvironment.targeted_body`).

    The bar is a column of the full height of the map. Its fill is the scale of the fixed zone, drawn only while the
    ship is in that body's fixed zone, from the surface (bottom) to the fixed zone's edge (top): 1.0x radius distance
    from centre at the bottom, FIXED_ZONE_RADIUS_MULTIPLE x radius at the top. Outside the fixed zone the bar stays
    empty.

    The instruments that read the target are drawn beside it: `draw_approach` (Distance, Approaching, Drift) above the
    ship's readouts, `draw_target` (the label FIXED, green, while the target is the body the frame is fixed on, else
    TARGET, then the target's name) in the left column, and `draw_advice` under the ORBIT and TRAVEL buttons.

    The "Approaching" readout is the signed rate of change of the distance to the targeted body
    (`Navigation.approach_speed`: the velocity relative to the body along the line to its centre; positive approaching,
    negative moving away, sideways motion does not count), formatted with `format_compact_speed` (`+500 m/s`,
    `-3 Km/s`). "Drift" is the speed across that line (`Navigation.drift_speed`), unsigned. In the fixed zone the
    "Distance" and "Approaching:" labels and the Approaching readout turn red when `Navigation.collision_warning` holds:
    keeping its direction relative to the body, the ship reaches the surface even braking with only
    `Navigation.COLLISION_BRAKE_FRACTION` of `Ship.BRAKE_ACC` (a straight-line check, sideways dodging not considered).

    The long distance advice, while `LongDistanceAdvisor.current` holds it: "Long distance advice:" in the advice
    colour,
    then ACCELERATE, STAY or DECELERATE, each in its own colour, with the time left of that phase
    (`Advisory.phase_time`),
    and under it the ETA, the date and time of arrival as the clock shows them; "Too far" when no plan keeps the
    reserves.
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
        if body.gravitational_parameter > 0.0 and not ship.navigation.compensates_pull():
            ProximityMeter._draw_apsides(surface, ship, body, bar_rect, fill_pad, inner_height)

    @staticmethod
    def _draw_apsides(surface: pygame.Surface, ship: Ship, body: Body, bar_rect: pygame.Rect, fill_pad: int,
                      inner_height: int) -> None:
        """Marks on the scale for the path about the body: its lowest point (red under the bind shell, else green), its
        highest point (only while the path is closed and inside the fixed zone), and the bind shell, a thin line. The
        lowest point is what the ORBIT assist needs above the shell (see OrbitAssist.begin). Drawn only while the ship
        falls freely: compensating the pull, it moves in a straight line, not along that path."""
        from galaxies.kepler import apsides
        from spaceships.navigation import Navigation
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        periapsis, apoapsis, _ = apsides(body.gravitational_parameter, r_vec, v_vec)
        shell = Navigation.BIND_RADIUS_MULTIPLE * body.radius
        zone = Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius
        left, right = bar_rect.left + fill_pad, bar_rect.right - fill_pad

        def y_of(distance: float) -> int:
            fraction = (distance / body.radius - 1.0) / (Navigation.FIXED_ZONE_RADIUS_MULTIPLE - 1.0)
            return bar_rect.bottom - fill_pad - round(inner_height * max(0.0, min(1.0, fraction)))

        pygame.draw.line(surface, ACCENT_DIM, (left, y_of(shell)), (right, y_of(shell)))
        low_colour = SPEED_WARNING_RED if periapsis < shell else BINDING_NEAR_GREEN
        pygame.draw.line(surface, low_colour, (left, y_of(periapsis)), (right, y_of(periapsis)), 2)
        if apoapsis <= zone:
            pygame.draw.line(surface, ACCENT_LABEL, (left, y_of(apoapsis)), (right, y_of(apoapsis)), 2)

    @staticmethod
    def draw_target(surface: pygame.Surface, fonts: Any, h: int, left: int, top: int) -> None:
        """The target's state and name on one row at `top`."""
        import game_environment as gem
        body = gem.current_environment.targeted_body
        is_fixed = body is gem.current_environment.fixed_body
        label_font = fonts.get(max(9, int(h * 0.017)))
        _draw_pair(surface, label_font, left, top, 'FIXED' if is_fixed else 'TARGET',
                   BINDING_NEAR_GREEN if is_fixed else ACCENT, body.name, ACCENT)

    @staticmethod
    def draw_approach(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, left: int, top: int,
                      row_height: int) -> None:
        """The distance, approach and drift of the target, one per row from `top`, `row_height` apart."""
        import game_environment as gem
        body = gem.current_environment.targeted_body
        label_font = fonts.get(max(9, int(h * 0.017)))

        collision_warning = ship.navigation.in_fixed_zone(body) and ship.navigation.collision_warning(body)
        label_colour = SPEED_WARNING_RED if collision_warning else ACCENT_LABEL  # the labels of distance and approach
        approach_colour = SPEED_WARNING_RED if collision_warning else ACCENT

        centre_dist = format_compact_distance(ship.navigation.distance_to_body_centre(body))
        _draw_pair(surface, label_font, left, top, 'Distance:', label_colour, centre_dist, ACCENT)
        _draw_pair(surface, label_font, left, top + row_height, 'Approaching:', label_colour,
                   format_compact_speed(ship.navigation.approach_speed(body)), approach_colour)
        _draw_pair(surface, label_font, left, top + 2 * row_height, 'Drift:', ACCENT_LABEL,
                   f'{format_compact_distance(ship.navigation.drift_speed(body))}/s', ACCENT)

    @staticmethod
    def draw_advice(surface: pygame.Surface, fonts: Any, h: int, left: int, top: int, row_height: int) -> None:
        """The long distance advice, while there is one: its heading, then the advice with its phase time, then the ETA
        (see the class docstring)."""
        advisory = LongDistanceAdvisor.current
        if advisory is None:
            return
        label_font = fonts.get(max(9, int(h * 0.017)))
        _draw_pair(surface, label_font, left, top, 'Long distance advice:', ADVICE_COLOR, '', ACCENT)
        if advisory.advice is None:
            _draw_pair(surface, label_font, left, top + row_height, 'Too far', SPEED_WARNING_RED, '', ACCENT)
            return
        word_colour = {Advice.ACCELERATE: ADVICE_ACCELERATE_COLOR, Advice.STAY: ADVICE_STAY_COLOR,
                       Advice.DECELERATE: ADVICE_DECELERATE_COLOR}[advisory.advice]
        phase = '' if advisory.phase_time is None else format_compact_duration(advisory.phase_time)
        _draw_pair(surface, label_font, left, top + row_height, advisory.advice.name, word_colour, phase, ACCENT)
        if advisory.arrival is not None:
            arrival = advisory.arrival
            stamp = (f'{arrival.year}-{arrival.month:02d}-{arrival.day:02d} '
                     f'{arrival.hour:02d}:{arrival.minute:02d}')
            _draw_pair(surface, label_font, left, top + 2 * row_height, 'ETA:', ACCENT_LABEL, stamp, ACCENT)
