"""The fixed stars within reach of the ship, drawn as dots where they are in the sky (labels: none yet)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from common.vector3 import Vector3
from galaxies.constants import FIXED_STAR_SHOW_RADIUS, LIGHT_YEAR_M

from .constants import FIXED_STAR_DOT_RADIUS_PX, NAKED_EYE_LIMIT_MAGNITUDE

if TYPE_CHECKING:
    from game_environment import GameEnvironment
    from spaceships.ship import Ship


class DistantStars:
    """Fixed stars within FIXED_STAR_SHOW_RADIUS of the ship, each as a dot in its own colour where it is in the sky.

    A star is only drawn when it is bright enough to see with the naked eye (apparent magnitude at most
    NAKED_EYE_LIMIT_MAGNITUDE), so the dim red dwarfs mostly stay out of the sky, as they do in the real one.

    Drawn bound or unbound, using the same directions as the other sky objects. Drawn first in the sky layer, so
    the sun's hole in the sky hides a star behind the sun, and the ground hides the stars below the horizon.
    """

    @staticmethod
    def visible_dots(environment: GameEnvironment, ship: Ship, w: int, h: int) -> list[tuple[tuple, tuple[int, int]]]:
        """(colour, screen position) for every fixed star in range, bright enough and in front of the camera."""
        from .instruments.common import project_to_camera, view_geometry
        _, horizon_y, focal_length_px = view_geometry(h)
        date_time = environment.date_time
        ship_position = ship.navigation.stellar_position(date_time)
        sx, sy, sz = ship_position.x, ship_position.y, ship_position.z
        radius_squared = (FIXED_STAR_SHOW_RADIUS * LIGHT_YEAR_M) ** 2
        # Unbound, a star behind the ship is not visible: its forward component is the dot product with the ship's
        # forward axis. Checked here, before any vector is built, since most stars in range are behind.
        forward = ship.attitude.forward
        check_forward = not ship.is_bound
        dots: list[tuple[tuple, tuple[int, int]]] = []
        for star, (x, y, z) in environment.galaxy.fixed_star_positions():
            dx, dy, dz = x - sx, y - sy, z - sz
            distance_squared = dx * dx + dy * dy + dz * dz
            if distance_squared > radius_squared:
                continue
            if star.apparent_magnitude(math.sqrt(distance_squared)) > NAKED_EYE_LIMIT_MAGNITUDE:
                continue
            if check_forward and dx * forward.x + dy * forward.y + dz * forward.z <= 0.0:
                continue
            direction = ship.navigation.direction_to_point(Vector3(x, y, z), date_time)
            projected = project_to_camera(ship, direction, w, horizon_y, focal_length_px)
            if projected is not None:
                dots.append((star.color, (int(projected[0]), int(projected[1]))))
        return dots

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        for colour, centre in DistantStars.visible_dots(environment, ship, w, h):
            pygame.draw.circle(surface, colour, centre, FIXED_STAR_DOT_RADIUS_PX)
