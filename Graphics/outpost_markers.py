"""Outposts on planets, shown as tiny dots in the sky while unbound (labels: ObjectLabels)."""

from __future__ import annotations
from typing import List, TYPE_CHECKING
import pygame
from Vector3 import Vector3
from .Constants import OUTPOST_DOT_COLOR, OUTPOST_DOT_RADIUS_PX

if TYPE_CHECKING:
    from Galaxies.outpost import Outpost
    from GameEnvironment import GameEnvironment
    from Player import Player


class OutpostMarkers:
    """Outposts of the planets within braking distance of the ship."""

    @staticmethod
    def in_braking_distance(environment: GameEnvironment, player: Player) -> List[tuple]:
        """(outpost, stellar position, visible) for every outpost of a planet within braking distance.

        `visible` is False when the outpost is on the far side of its planet (its surface normal points
        away from the ship). Such outposts still get a label, but no dot."""
        import Player as player_module
        date_time = environment.date_time
        ship_position = player.stellar_position(date_time)
        result = []
        for planet in environment.nearest_system.get_all_worlds():
            if planet.parent_planet is not None or not planet.outposts:
                continue
            centre = planet.calculate_stellar_position(date_time)
            # Stellar distance, also while bound (Player._distance_to_world_centre assumes unbound).
            if (ship_position - centre).length() >= player_module.Player.BRAKING_RADIUS_MULTIPLE * planet.radius:
                continue
            for outpost in planet.outposts.values():
                point = outpost.stellar_position(date_time)
                normal = (point - centre).normalized()
                visible = (ship_position - point).dot(normal) > 0.0
                result.append((outpost, point, visible))
        return result

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """Draw a dot for every visible outpost in braking distance. Only while unbound, like labels."""
        if player.is_bound:
            return
        from .Instruments.common import view_geometry, project_to_camera
        _, horizon_y, focal_length_px = view_geometry(h)
        for _, point, visible in OutpostMarkers.in_braking_distance(environment, player):
            if not visible:
                continue
            projected = project_to_camera(player, player.direction_to_point(point, environment.date_time), w, horizon_y, focal_length_px)
            if projected is not None:
                pygame.draw.circle(surface, OUTPOST_DOT_COLOR, (int(projected[0]), int(projected[1])), OUTPOST_DOT_RADIUS_PX)
