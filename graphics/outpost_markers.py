"""Outposts on planets, shown as tiny dots in the sky while unbound (labels: ObjectLabels)."""

from __future__ import annotations
from typing import List, TYPE_CHECKING
import pygame
from .constants import OUTPOST_DOT_COLOR, OUTPOST_DOT_RADIUS_PX

if TYPE_CHECKING:
    from game_environment import GameEnvironment
    from spaceships.ship import Ship


class OutpostMarkers:
    """Outposts of the planets within the fixed zone of the ship, as dots where each outpost faces the ship.

    Drawn in the sky while unbound (after the worlds). While bound, ObjectLabels draws the dot on the surface instead.
    `in_fixed_zone` is the sphere's visibility test, so outposts on the far side of their planet get no dot.
    """

    @staticmethod
    def in_fixed_zone(environment: GameEnvironment, ship: Ship) -> List[tuple]:
        """(outpost, stellar position, visible) for every outpost of a planet within the fixed zone. Bound to a world,
        only that world's outposts are listed (a moon has none): the outposts of the planet it orbits are not.

        `visible` is False when the outpost is on the far side of its planet (its surface normal points
        away from the ship). Such outposts still get a label, but no dot."""
        from spaceships.navigation import Navigation
        date_time = environment.date_time
        ship_position = ship.navigation.stellar_position(date_time)
        result = []
        bound_world = environment.fixed_world if ship.is_bound else None
        for planet in environment.nearest_system.get_all_worlds():
            if planet.parent_planet is not None or not planet.outposts:
                continue
            if ship.is_bound and planet is not bound_world:
                continue
            centre = planet.calculate_stellar_position(date_time)
            # Stellar distance, also while bound (Navigation.distance_to_body_centre assumes unbound).
            if (ship_position - centre).length() >= Navigation.FIXED_ZONE_RADIUS_MULTIPLE * planet.radius:
                continue
            for outpost in planet.outposts.values():
                point = outpost.stellar_position(date_time)
                normal = (point - centre).normalized()
                visible = (ship_position - point).dot(normal) > 0.0
                result.append((outpost, point, visible))
        return result

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        """Draw a dot for every visible outpost in the fixed zone. Only while unbound, like labels."""
        if ship.is_bound:
            return
        from .instruments.common import view_geometry, project_to_camera
        _, horizon_y, focal_length_px = view_geometry(h)
        for _, point, visible in OutpostMarkers.in_fixed_zone(environment, ship):
            if not visible:
                continue
            projected = project_to_camera(ship, ship.navigation.direction_to_point(point, environment.date_time), w,
                                          horizon_y, focal_length_px)
            if projected is not None:
                pygame.draw.circle(surface, OUTPOST_DOT_COLOR, (int(projected[0]), int(projected[1])),
                                   OUTPOST_DOT_RADIUS_PX)
