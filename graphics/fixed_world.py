"""The planet seen from the ship while it is bound: the world below the horizon, as a disc of the world's true size."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple
import math

import numpy as np
import pygame
from graphics.instruments.common import view_geometry

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class FixedWorld:
    """Renders the planet below the horizon, seen from the cockpit while bound (see draw_surface)."""

    @staticmethod
    def draw_surface(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship,
                     colour: Tuple[int, int, int]) -> None:
        """Draw the planet below the horizon as seen from the player's altitude.

        The camera looks horizontally, so the planet's centre lies straight down,
        off the bottom of the view. A pixel shows the planet when its view ray is
        within the sphere's angular radius of straight down. With sy measured below
        the horizon and sx sideways, that is sx^2 <= sy^2 * tan^2(a) - f^2, where a
        is the angular radius and f the focal length.

        The rows are worked out all at once with numpy and drawn as a few polygons (`_fill_rows`): row by row in
        Python, with a line each, it was one of the largest costs of a frame on the ground. The row-by-row way below is
        kept for the one case the polygons do not cover (the boundary's quadratic degenerating to a line).
        """
        view_h, centre_y, focal_length_px = view_geometry(h)
        world_radius = environment.fixed_world.radius
        distance_to_center = world_radius + ship.navigation.altitude_above_surface(environment.fixed_world)

        sin_angular = min(world_radius / distance_to_center, 0.9999)
        cos_angular = math.sqrt(1.0 - sin_angular * sin_angular)

        down_right, down_up, down_forward = ship.attitude.camera_components(
            ship.navigation.direction_down(environment.fixed_world, environment.date_time)
        )
        nadir_x, nadir_y, nadir_z = down_right, -down_up, down_forward

        center_x = w / 2
        focal = focal_length_px
        cos_sq = cos_angular * cos_angular
        if abs(nadir_x * nadir_x - cos_sq) > 1e-9:
            FixedWorld._fill_rows(surface, colour, w, view_h, centre_y, focal, cos_sq, (nadir_x, nadir_y, nadir_z))
            return

        def clamp_x(x: float) -> int:
            return int(max(-w, min(2 * w, x)))

        def visible_spans(sy: float) -> list:
            """Screen x offsets (from centre) inside the planet's disc on row sy."""
            a_term = nadir_y * sy + nadir_z * focal
            a = nadir_x * nadir_x - cos_sq
            b = 2.0 * nadir_x * a_term
            c = a_term * a_term - cos_sq * (sy * sy + focal * focal)
            if abs(a) < 1e-12:
                if abs(b) < 1e-12:
                    spans = [(-math.inf, math.inf)] if c >= 0 else []
                else:
                    root = -c / b
                    spans = [(root, math.inf)] if b > 0 else [(-math.inf, root)]
            else:
                disc = b * b - 4.0 * a * c
                if a < 0:
                    if disc < 0:
                        return []
                    root = math.sqrt(disc)
                    spans = [tuple(sorted(((-b - root) / (2 * a), (-b + root) / (2 * a))))]
                elif disc < 0:
                    spans = [(-math.inf, math.inf)]
                else:
                    root = math.sqrt(disc)
                    low, high = sorted(((-b - root) / (2 * a), (-b + root) / (2 * a)))
                    spans = [(-math.inf, low), (high, math.inf)]

            if abs(nadir_x) < 1e-12:
                allowed = (-math.inf, math.inf) if a_term > 0 else None
            elif nadir_x > 0:
                allowed = (-a_term / nadir_x, math.inf)
            else:
                allowed = (-math.inf, -a_term / nadir_x)
            if allowed is None:
                return []
            clipped = []
            for lo, hi in spans:
                start, end = max(lo, allowed[0]), min(hi, allowed[1])
                if start < end:
                    clipped.append((start, end))
            return clipped

        for y in range(view_h):
            for lo, hi in visible_spans(y - centre_y):
                pygame.draw.line(surface, colour, (clamp_x(center_x + lo), y), (clamp_x(center_x + hi), y))

    @staticmethod
    def _fill_rows(surface: pygame.Surface, colour: Tuple[int, int, int], w: int, view_h: int, centre_y: float,
                   focal: float, cos_sq: float, nadir: Tuple[float, float, float]) -> None:
        """The same spans as `visible_spans` in draw_surface, for every row at once: on each row at most two spans,
        each slot drawn as one polygon per run of rows where it exists."""
        nadir_x, nadir_y, nadir_z = nadir
        sy = np.arange(view_h, dtype=np.float64) - centre_y
        a_term = nadir_y * sy + nadir_z * focal
        a = nadir_x * nadir_x - cos_sq
        b = 2.0 * nadir_x * a_term
        c = a_term * a_term - cos_sq * (sy * sy + focal * focal)
        disc = b * b - 4.0 * a * c
        root = np.sqrt(np.maximum(disc, 0.0))
        low = np.minimum((-b - root) / (2 * a), (-b + root) / (2 * a))
        high = np.maximum((-b - root) / (2 * a), (-b + root) / (2 * a))
        inf = np.full(view_h, np.inf)
        if a < 0:   # inside the two roots, on the rows that have them
            slots = [(low, high, disc >= 0)]
        else:       # outside the two roots, or the whole row where there are none
            slots = [(-inf, np.where(disc < 0, inf, low), np.ones(view_h, dtype=bool)),
                     (high, inf, disc >= 0)]
        # Only the half of the view that faces the planet (the rays with a positive component towards its centre).
        if abs(nadir_x) < 1e-12:
            allowed_low, allowed_high = -inf, np.where(a_term > 0, inf, -inf)
        elif nadir_x > 0:
            allowed_low, allowed_high = -a_term / nadir_x, inf
        else:
            allowed_low, allowed_high = -inf, -a_term / nadir_x
        rows = np.arange(view_h)
        center_x = w / 2
        for lo, hi, present in slots:
            start = np.clip(center_x + np.maximum(lo, allowed_low), -w, 2 * w)
            end = np.clip(center_x + np.minimum(hi, allowed_high), -w, 2 * w)
            shown = present & (np.maximum(lo, allowed_low) < np.minimum(hi, allowed_high))
            for first, last in _runs(shown):
                left = list(zip(start[first:last].astype(int).tolist(), rows[first:last].tolist()))
                right = list(zip(end[first:last].astype(int).tolist(), rows[first:last].tolist()))
                if last - first == 1:
                    pygame.draw.line(surface, colour, left[0], right[0])
                else:
                    pygame.draw.polygon(surface, colour, left + right[::-1])


def _runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    """The (first, end) of each run of True in `mask`."""
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.nonzero(edges == 1)[0].tolist(), np.nonzero(edges == -1)[0].tolist()))
