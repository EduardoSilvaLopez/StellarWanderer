"""The planet seen from the ship while it is bound: the world below the horizon, as a disc of the world's true size."""

from __future__ import annotations
from typing import TYPE_CHECKING, Tuple
import math
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
