"""Location information: the name of the reference body and system (drawn large, centred in the top bar), and the
position, attitude and speed readouts (drawn in whatever column the console gives them)."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import CANOPY_TOP, ACCENT
from common.units import format_compact_distance

if TYPE_CHECKING:
    from galaxies.body import Body
    from spaceships.ship import Ship


class LocationInfo:
    """The name of the reference body, and the readouts of the ship.

    The name is the reference body and its system: the fixed body while the ship is fixed, else the star. Its name is
    the system's alone when it is the star. It is drawn large and centred in the top bar, above the windshield. The
    readouts are the position of the ship (bound: altitude, longitude, latitude; unbound: x, y, z, each with its rate
    Δ), the attitude (yaw, pitch, roll, each with its rate Δ) and the speed: the length of the velocity vector over all
    three axes, shown without a sign. The target is not shown here (see ProximityMeter)."""

    @staticmethod
    def _reference_body() -> Body:
        """The fixed body while the ship is fixed, else the targeted body's star."""
        import game_environment as gem
        environment = gem.current_environment
        return (environment.fixed_body if environment.fixed_body is not None
                else environment.targeted_body.stellar_system.star)

    @staticmethod
    def draw_name(surface: pygame.Surface, fonts: Any, w: int, h: int) -> None:
        """Draw the reference body's name and its system's, centred in the top bar, as large as fits the bar's
        height."""
        reference = LocationInfo._reference_body()
        stellar_system = reference.stellar_system
        stellar_label = reference.name + ", " + stellar_system.name \
            if reference.is_world else stellar_system.name

        bar_height = int(h * CANOPY_TOP)
        name_text = fonts.render_to_fit(stellar_label, ACCENT, int(w * 0.6), int(bar_height * 0.63))
        # Centre the visible glyphs, not the font's box, which has space above the capitals and below the descenders.
        ink = name_text.get_bounding_rect()
        surface.blit(name_text, (w // 2 - ink.centerx, bar_height // 2 - ink.centery))

    @staticmethod
    def draw_readouts(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, left: int, top: int,
                      line_spacing: int) -> None:
        """Draw the position and attitude readouts, one per line from (left, top), `line_spacing` pixels apart."""
        label_font = fonts.get(max(9, int(h * 0.017)))

        if ship.is_bound:
            axis_lines = [
                ('Altitude', ship.position.y, ship.velocity.y),
                ('Longitude', ship.position.x, ship.velocity.x),
                ('Latitude', ship.position.z, ship.velocity.z),
            ]
        else:
            axis_lines = [
                ('x', ship.position.x, ship.velocity.x),
                ('y', ship.position.y, ship.velocity.y),
                ('z', ship.position.z, ship.velocity.z),
            ]

        import game_environment as gem
        body = LocationInfo._reference_body()  # pitch and roll: relative to the same body as the position box
        date_time = gem.current_environment.date_time
        speed = ship.velocity.as_vector().length()
        texts = []
        for label, position, velocity in axis_lines:
            if ship.is_bound:
                texts.append(f'{label}: {int(position)} Δ {int(velocity)}')
            else:
                texts.append(f'{label}: {format_compact_distance(position)}  Δ {int(velocity)}')
        texts += [
            f'Yaw: {int(ship.attitude.yaw)}° Δ {int(ship.attitude.yaw_rate)}',
            f'Pitch: {int(ship.navigation.pitch_angle(body, date_time))}° Δ {int(ship.attitude.pitch_rate)}',
            f'Roll: {int(ship.navigation.roll_angle(body, date_time))}° Δ {int(ship.attitude.roll_rate)}',
            f'Speed: {format_compact_distance(speed)}/s',
        ]
        for index, text in enumerate(texts):
            surface.blit(label_font.render(text, True, ACCENT), (left, top + index * line_spacing))
