"""Location information: the name of the reference body and system, then the position, attitude and speed readouts.
Shown beside the left cluster of the console (ALT or proximity meter), in the same column."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import pygame
from ..constants import CONSOLE_TOP, ACCENT
from common.units import format_compact_distance

if TYPE_CHECKING:
    from spaceships.ship import Ship


class LocationInfo:
    """Draw the reference body's name, the position of the ship (bound: altitude, longitude, latitude; unbound: x, y, z,
    each with its rate Δ), the attitude (yaw, pitch, roll, each with its rate Δ) and the speed: the length of the velocity
    vector over all three axes, shown without a sign."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, cluster_left: int, cluster_top: int, cluster_height: int) -> None:
        """Draw the location information above and beside the left cluster of the console."""
        top = int(h * CONSOLE_TOP)
        height = h - top

        label_font = fonts.get(max(9, int(h * 0.017)))
        world_font = fonts.get(max(12, int(h * 0.024)))

        bar_w = int(w * 0.028)
        coord_x = cluster_left + bar_w + int(w * 0.03)
        world_y = cluster_top - 40

        # The box follows the fixed body while the ship is fixed, else the star: its positions are in the star's frame and
        # its name is the system's. The target is not shown here (see ProximityMeter).
        import game_environment as gem
        environment = gem.current_environment
        reference = environment.fixed_body if environment.fixed_body is not None else environment.targeted_body.stellar_system.star
        stellar_system = reference.stellar_system
        stellar_label = reference.name + ", " + stellar_system.name \
            if reference.is_world else stellar_system.name
        world_text = world_font.render(stellar_label, True, ACCENT)
        surface.blit(world_text, (coord_x, world_y))

        # Position readouts
        coord_y = world_y + world_text.get_height() + int(height * 0.08)
        line_spacing = int(height * 0.06)

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

        for label, position, velocity in axis_lines:
            if ship.is_bound:
                text = f'{label}: {int(position)} Δ {int(velocity)}'
            else:
                text = f'{label}: {format_compact_distance(position)}  Δ {int(velocity)}'
            line_text = label_font.render(text, True, ACCENT)
            surface.blit(line_text, (coord_x, coord_y))
            coord_y += line_spacing

        body = reference  # pitch and roll: relative to the same body as the position box
        date_time = gem.current_environment.date_time
        speed = ship.velocity.as_vector().length()
        attitude_lines = (
            f'Yaw: {int(ship.attitude.yaw)}° Δ {int(ship.attitude.yaw_rate)}',
            f'Pitch: {int(ship.navigation.pitch_angle(body, date_time))}° Δ {int(ship.attitude.pitch_rate)}',
            f'Roll: {int(ship.navigation.roll_angle(body, date_time))}° Δ {int(ship.attitude.roll_rate)}',
            f'Speed: {format_compact_distance(speed)}/s',
        )
        for text in attitude_lines:
            surface.blit(label_font.render(text, True, ACCENT), (coord_x, coord_y))
            coord_y += line_spacing
