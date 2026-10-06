"""Radar: the star and worlds around the ship on logarithmic scales, shown while unbound."""

from __future__ import annotations
from datetime import datetime
from typing import Any, List, Tuple, TYPE_CHECKING
import math
import pygame
from ..Constants import ACCENT_DIM, RADAR_BAR_OVER, RADAR_BAR_UNDER, RADAR_WORLD_COLOR

if TYPE_CHECKING:
    from Player import Player

Vector3 = Tuple[float, float, float]


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
    def objects(date_time: datetime) -> List[Tuple[Vector3, Tuple[int, int, int]]]:
        """Stellar-frame position and colour of the star and of every world in its system."""
        import GameEnvironment as gem
        system = gem.current_environment.nearest_world.parent_orbit.parent_stellar_system
        found: List[Tuple[Vector3, Tuple[int, int, int]]] = [((0.0, 0.0, 0.0), system.color)]
        for orbit in system.orbits:
            for world in orbit.worlds:
                found.append((world.calculate_stellar_position(date_time), RADAR_WORLD_COLOR))
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

        position = (player.position.x, player.position.y, player.position.z)
        previous_clip = surface.get_clip()
        surface.set_clip(rect.inflate(-2, -2))

        projected = []
        for object_position, colour in Radar.objects(date_time):
            relative = tuple(o - p for o, p in zip(object_position, position))
            if math.hypot(*relative) > Radar.MAX_DISTANCE:
                continue
            right, up, forward = player.camera_components(relative)
            in_plane = Radar.log_fraction(math.hypot(right, forward))
            bearing = math.atan2(right, forward)
            foot = (centre_x + in_plane * horizontal_radius * math.sin(bearing),
                    centre_y - in_plane * vertical_radius * math.cos(bearing))
            height = math.copysign(Radar.log_fraction(abs(up)), up) * bar_length
            projected.append((foot, height, colour))

        for foot, height, colour in sorted(projected, key=lambda item: item[0][1]):
            tip = (foot[0], foot[1] - height)
            pygame.draw.line(surface, RADAR_BAR_OVER if height >= 0 else RADAR_BAR_UNDER, foot, tip, 2)
            pygame.draw.circle(surface, colour, tip, 3)

        pygame.draw.circle(surface, RADAR_BAR_OVER, (centre_x, centre_y), 2)
        surface.set_clip(previous_clip)
