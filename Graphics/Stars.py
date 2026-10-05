"""Starfield rendering."""

from __future__ import annotations
from typing import List, Tuple
import random
import math
import pygame
from .Constants import STAR_COUNT, STAR_SEED, CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS


class Stars:
    """Renders stars visible through the canopy."""

    @staticmethod
    def make_starfield(count: int = STAR_COUNT, seed: int = STAR_SEED) -> List[Tuple[float, float, int, int]]:
        """Generate a starfield as (nx, ny, radius, brightness), normalised to canopy area.

        Args:
            count: Number of stars to generate
            seed: Random seed for reproducibility

        Returns:
            List of star tuples (nx, ny, radius, brightness)
        """
        rng = random.Random(seed)
        stars: List[Tuple[float, float, int, int]] = []
        for _ in range(count):
            brightness = rng.randint(70, 255)
            radius = 1 if rng.random() < 0.82 else 2
            stars.append((rng.random(), rng.random(), radius, brightness))
        return stars

    @staticmethod
    def draw(surface: pygame.Surface, stars: List[Tuple[float, float, int, int]], w: int, h: int, yaw: float = 0.0, pitch: float = 0.0) -> None:
        """Draw stars as points or small circles.

        Args:
            surface: Pygame surface to draw on
            stars: List of star tuples from make_starfield()
            w: Window width
            h: Window height
            yaw: Ship heading in degrees
            pitch: Ship pitch in degrees, positive nose up
        """
        view_h = int(h * CONSOLE_TOP)
        angle = math.radians(-yaw)
        sin_angle = math.sin(angle)
        cos_angle = math.cos(angle)
        pitch_shift = view_h * 0.5 * math.tan(math.radians(pitch)) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)

        for nx, ny, radius, brightness in stars:
            centered_x = nx - 0.5
            centered_y = ny - 0.5
            rotated_x = centered_x * cos_angle + centered_y * sin_angle
            rotated_y = -centered_x * sin_angle + centered_y * cos_angle
            x = int((rotated_x + 0.5) * w)
            y = int((rotated_y + 0.5) * view_h + pitch_shift)

            if not (0 <= x < w and 0 <= y < view_h):
                continue

            # Slightly cool tint keeps the stars from looking like flat white dots.
            color = (brightness, brightness, min(255, brightness + 18))
            if radius == 1:
                surface.set_at((x, y), color)
            else:
                pygame.draw.circle(surface, color, (x, y), radius)
