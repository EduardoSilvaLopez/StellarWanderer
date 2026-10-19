"""The orbit of the targeted body, a thin line in the sky while unbound: where a moving target is going."""

from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import pygame

from .constants import NEAR_CLIP, ORBIT_PATH_COLOR

if TYPE_CHECKING:
    from game_environment import GameEnvironment
    from spaceships.ship import Ship


class OrbitPath:
    """The line is round the star for a planet, and round the planet for a moon (it moves with the planet). Each piece is
    clipped to the view first: near the target, the pieces are far longer than the distance to them."""

    STEPS = 180
    MARGIN = 1.05  # the clip is this much wider than the view, so lines reach its border

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        from galaxies.world import World
        body = environment.targeted_body
        if ship.is_bound or not isinstance(body, World):  # the star has no orbit
            return
        from .instruments.common import view_geometry
        _, horizon_y, focal = view_geometry(h)
        date_time = environment.date_time

        centre = body.parent_planet.calculate_stellar_position(date_time) if body.parent_planet else (0.0, 0.0, 0.0)
        points = body.orbit_points(date_time, OrbitPath.STEPS) + np.array(centre) - np.array(ship.navigation.stellar_position(date_time))
        axes = np.array([ship.attitude.right, ship.attitude.up, ship.attitude.forward])
        start = points @ axes.T  # (right, up, forward) of every point
        end = np.concatenate([start[1:], start[:1]])  # each piece runs to the next point, and the last back to the first

        # Liang-Barsky against the view's pyramid: the part of each piece, from t_in to t_out, that is inside it.
        tan_x, tan_y = OrbitPath.MARGIN * (w / 2) / focal, OrbitPath.MARGIN * horizon_y / focal
        planes = (
            lambda c: c[:, 2] - NEAR_CLIP,
            lambda c: tan_x * c[:, 2] - c[:, 0], lambda c: tan_x * c[:, 2] + c[:, 0],
            lambda c: tan_y * c[:, 2] - c[:, 1], lambda c: tan_y * c[:, 2] + c[:, 1],
        )
        t_in, t_out = np.zeros(len(start)), np.ones(len(start))
        inside = np.ones(len(start), dtype=bool)
        for plane in planes:
            d0, d1 = plane(start), plane(end)
            outside0, outside1 = d0 < 0, d1 < 0
            inside &= ~(outside0 & outside1)
            with np.errstate(divide='ignore', invalid='ignore'):
                t = d0 / (d0 - d1)
            t_in = np.where(outside0 & ~outside1, np.maximum(t_in, t), t_in)
            t_out = np.where(outside1 & ~outside0, np.minimum(t_out, t), t_out)
        inside &= t_in < t_out
        if not inside.any():
            return

        # The ends of the pieces that remain, on the screen.
        a = (start + (end - start) * t_in[:, None])[inside]
        b = (start + (end - start) * t_out[:, None])[inside]
        depth_a, depth_b = np.maximum(a[:, 2], NEAR_CLIP / 2), np.maximum(b[:, 2], NEAR_CLIP / 2)
        lines = np.rint(np.stack([
            w / 2 + focal * a[:, 0] / depth_a, horizon_y - focal * a[:, 1] / depth_a,
            w / 2 + focal * b[:, 0] / depth_b, horizon_y - focal * b[:, 1] / depth_b,
        ], axis=1)).astype(int).tolist()
        for x0, y0, x1, y1 in lines:
            pygame.draw.line(surface, ORBIT_PATH_COLOR, (x0, y0), (x1, y1), 1)
