"""The fixed stars within reach of the ship, drawn as dots where they are in the sky (labels: none yet)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
import pygame

from common.vector3 import Vector3
from galaxies.constants import ABSOLUTE_MAGNITUDE_DISTANCE_LY, FIXED_STAR_SHOW_RADIUS, LIGHT_YEAR_M

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

    The range, brightness and in-front tests run on numpy arrays of all the stars, made once for the galaxy's list
    of fixed stars (their positions do not change); only the stars that pass are projected one by one.
    """

    _source: Optional[list] = None  # the galaxy's list the arrays were made from
    _positions: Optional[np.ndarray] = None  # (n, 3), in meters, in the stellar frame
    _absolute_magnitudes: Optional[np.ndarray] = None  # (n,)

    @staticmethod
    def _star_arrays(environment: GameEnvironment) -> tuple[list, np.ndarray, np.ndarray]:
        """The galaxy's fixed stars, their positions and their absolute magnitudes, as arrays in the same order."""
        stars = environment.galaxy.fixed_star_positions()
        if DistantStars._source is not stars:
            DistantStars._source = stars
            DistantStars._positions = np.array([position for _, position in stars], dtype=float).reshape(-1, 3)
            DistantStars._absolute_magnitudes = np.array([star.absolute_magnitude for star, _ in stars], dtype=float)
        return stars, DistantStars._positions, DistantStars._absolute_magnitudes

    @staticmethod
    def visible_dots(environment: GameEnvironment, ship: Ship, w: int, h: int) -> list[tuple[tuple, tuple[int, int]]]:
        """(colour, screen position) for every fixed star in range, bright enough and in front of the camera."""
        from .instruments.common import project_to_camera, view_geometry
        _, horizon_y, focal_length_px = view_geometry(h)
        date_time = environment.date_time
        ship_position = ship.navigation.stellar_position(date_time)
        stars, positions, absolute_magnitudes = DistantStars._star_arrays(environment)
        offsets = positions - np.array([ship_position.x, ship_position.y, ship_position.z])
        distance_squared = np.einsum('ij,ij->i', offsets, offsets)
        # The same brightness as Star.apparent_magnitude, for every star at once.
        distance_ly = np.sqrt(distance_squared) / LIGHT_YEAR_M
        apparent_magnitudes = absolute_magnitudes + 5 * np.log10(distance_ly / ABSOLUTE_MAGNITUDE_DISTANCE_LY)
        visible = (distance_squared <= (FIXED_STAR_SHOW_RADIUS * LIGHT_YEAR_M) ** 2) & \
            (apparent_magnitudes <= NAKED_EYE_LIMIT_MAGNITUDE)
        # Unbound, a star behind the ship is not visible: its forward component is the dot product with the ship's
        # forward axis.
        if not ship.is_bound:
            forward = ship.attitude.forward
            visible &= offsets @ np.array([forward.x, forward.y, forward.z]) > 0.0
        dots: list[tuple[tuple, tuple[int, int]]] = []
        for index in np.flatnonzero(visible):
            star, (x, y, z) = stars[index]
            direction = ship.navigation.direction_to_point(Vector3(x, y, z), date_time)
            projected = project_to_camera(ship, direction, w, horizon_y, focal_length_px)
            if projected is not None:
                dots.append((star.color, (int(projected[0]), int(projected[1]))))
        return dots

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        for colour, centre in DistantStars.visible_dots(environment, ship, w, h):
            pygame.draw.circle(surface, colour, centre, FIXED_STAR_DOT_RADIUS_PX)
