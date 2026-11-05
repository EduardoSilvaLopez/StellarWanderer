"""The orbit of the targeted body, a thin line in the sky while unbound: where a moving target is going.

A world or an asteroid of a mission has one; the star does not. A giant hides the part of it that is behind."""

from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import pygame

from .constants import NEAR_CLIP, ORBIT_PATH_COLOR
from .giant_gl import GiantGl

if TYPE_CHECKING:
    from game_environment import GameEnvironment
    from spaceships.ship import Ship


class OrbitPath:
    """The line is round the star for a planet or an asteroid, and round the planet for a moon (it moves with the
    planet). Each piece
    is clipped to the view first: near the target, the pieces are far longer than the distance to them."""

    STEPS = 180
    PARTS = 12  # each piece is tested for a giant in front of it in this many parts
    MARGIN = 1.05  # the clip is this much wider than the view, so lines reach its border

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        from galaxies.asteroid import Asteroid
        from galaxies.people import player as pem  # local: the player's choice to show orbits (toggled with O)
        from galaxies.world import World
        body = environment.targeted_body
        if not pem.current_player.show_orbits or ship.is_bound or not isinstance(body, (World, Asteroid)):
            return  # the star has no orbit
            return
        from .instruments.common import view_geometry
        _, horizon_y, focal = view_geometry(h)
        date_time = environment.date_time

        centre = (body.parent_planet.calculate_stellar_position(date_time)
                  if isinstance(body, World) and body.parent_planet else (0.0, 0.0, 0.0))
        points = (body.orbit_points(date_time, OrbitPath.STEPS) + np.array(centre)
                  - np.array(ship.navigation.stellar_position(date_time)))
        axes = np.array([ship.attitude.right, ship.attitude.up, ship.attitude.forward])
        start = points @ axes.T  # (right, up, forward) of every point
        # Each piece runs to the next point, and the last back to the first.
        end = np.concatenate([start[1:], start[:1]])

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

        # The pieces that remain, each cut in parts: the parts a giant is in front of are not drawn.
        a = (start + (end - start) * t_in[:, None])[inside]
        b = (start + (end - start) * t_out[:, None])[inside]
        occluders = GiantGl.occluders(environment, ship)
        if occluders:
            shares = np.linspace(0.0, 1.0, OrbitPath.PARTS + 1)
            cuts = a[:, None, :] + (b - a)[:, None, :] * shares[None, :, None]
            parts_a, parts_b = cuts[:, :-1].reshape(-1, 3), cuts[:, 1:].reshape(-1, 3)
            shown = ~GiantGl.hidden((parts_a + parts_b) / 2.0, occluders)
            a, b = parts_a[shown], parts_b[shown]
        depth_a, depth_b = np.maximum(a[:, 2], NEAR_CLIP / 2), np.maximum(b[:, 2], NEAR_CLIP / 2)
        lines = np.rint(np.stack([
            w / 2 + focal * a[:, 0] / depth_a, horizon_y - focal * a[:, 1] / depth_a,
            w / 2 + focal * b[:, 0] / depth_b, horizon_y - focal * b[:, 1] / depth_b,
        ], axis=1)).astype(int).tolist()
        for x0, y0, x1, y1 in lines:
            pygame.draw.line(surface, ORBIT_PATH_COLOR, (x0, y0), (x1, y1), 1)
