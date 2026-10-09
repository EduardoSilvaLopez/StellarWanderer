"""Radar: the star and worlds around the ship on logarithmic scales, shown while unbound."""

from __future__ import annotations
from datetime import datetime
from typing import Any, List, Tuple, TYPE_CHECKING
import math
import pygame
from Vector3 import Vector3
from ..Constants import (
    ACCENT_DIM, RADAR_BAR_OVER, RADAR_BAR_UNDER, RADAR_WORLD_COLOR, RADAR_MOON_COLOR,
    RADAR_STAR_DOT_RADIUS, RADAR_WORLD_DOT_RADIUS, RADAR_MOON_DOT_RADIUS,
)

if TYPE_CHECKING:
    from Player import Player


class Radar:
    """Ellipse in the ship's forward/right plane, one bar per object (the star and every world).

    Forward is the top of the ellipse and right is its right side. An object's foot on the
    ellipse is its projection onto that plane: the angle is its bearing, the distance from
    the centre is logarithmic in its in-plane distance. The bar runs from the foot along the
    ship's up axis, upwards (white) when the object is above the plane, downwards (gray) when
    below, with a logarithmic length. A dot at the end of the bar marks the object.
    """

    MIN_DISTANCE = 1.0e5  # metres, mapped to the centre (and to a zero-length bar)
    MAX_DISTANCE = 100 * 1.496e11  # metres, 100 AU, mapped to the edge (and to a full bar)
    SQUASH = 0.32  # vertical radius of the ellipse relative to its horizontal radius
    BAR_FRACTION = 0.35  # full bar length relative to the usable half-height of the panel
    ELLIPSE_FRACTION = 0.55  # vertical radius of the ellipse relative to the same half-height

    @staticmethod
    def log_fraction(distance: float) -> float:
        """0 at MIN_DISTANCE or closer, 1 at MAX_DISTANCE or farther, logarithmic in between."""
        if distance <= Radar.MIN_DISTANCE:
            return 0.0
        fraction = math.log(distance / Radar.MIN_DISTANCE) / math.log(Radar.MAX_DISTANCE / Radar.MIN_DISTANCE)
        return min(1.0, fraction)

    @staticmethod
    def objects(date_time: datetime) -> List[Tuple[Vector3, Tuple[int, int, int], int]]:
        """Stellar-frame position, dot colour and dot radius of the star and of every world in its system.
        Moons get a different colour and a smaller dot than planets."""
        import GameEnvironment as gem
        system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        found: List[Tuple[Vector3, Tuple[int, int, int], int]] = [
            (Vector3(0.0, 0.0, 0.0), system.color, RADAR_STAR_DOT_RADIUS)
        ]
        for world in system.get_all_worlds():
            if world.parent_planet:
                found.append((world.calculate_stellar_position(date_time), RADAR_MOON_COLOR, RADAR_MOON_DOT_RADIUS))
            else:
                found.append((world.calculate_stellar_position(date_time), RADAR_WORLD_COLOR, RADAR_WORLD_DOT_RADIUS))
        return found

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, rect: pygame.Rect, player: Player, date_time: datetime) -> None:
        padding = max(6, int(rect.height * 0.04))
        half_height = rect.height / 2 - padding
        vertical_radius = half_height * Radar.ELLIPSE_FRACTION
        horizontal_radius = min(vertical_radius / Radar.SQUASH, rect.width / 2 - padding)
        bar_length = half_height * Radar.BAR_FRACTION
        centre_x, centre_y = rect.centerx, rect.centery

        pygame.draw.ellipse(
            surface, ACCENT_DIM,
            (centre_x - horizontal_radius, centre_y - vertical_radius, horizontal_radius * 2, vertical_radius * 2), 1
        )

        position = player.position.as_vector()
        previous_clip = surface.get_clip()
        surface.set_clip(rect.inflate(-2, -2))

        projected = []
        for object_position, colour, dot_radius in Radar.objects(date_time):
            relative = object_position - position
            if relative.length() > Radar.MAX_DISTANCE:
                continue
            right, up, forward = player.camera_components(relative)
            in_plane = Radar.log_fraction(math.hypot(right, forward))
            bearing = math.atan2(right, forward)
            foot = (centre_x + in_plane * horizontal_radius * math.sin(bearing),
                    centre_y - in_plane * vertical_radius * math.cos(bearing))
            height = math.copysign(Radar.log_fraction(abs(up)), up) * bar_length
            projected.append((foot, height, colour, dot_radius))

        for foot, height, colour, dot_radius in sorted(projected, key=lambda item: item[0][1]):
            tip = (foot[0], foot[1] - height)
            pygame.draw.line(surface, RADAR_BAR_OVER if height >= 0 else RADAR_BAR_UNDER, foot, tip, 2)
            pygame.draw.circle(surface, colour, tip, dot_radius)

        pygame.draw.circle(surface, RADAR_BAR_OVER, (centre_x, centre_y), 2)
        surface.set_clip(previous_clip)
