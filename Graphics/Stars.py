"""Starfield rendering."""

import random
import pygame
from .Constants import STAR_COUNT, STAR_SEED, CONSOLE_TOP


class Stars:
    """Renders stars visible through the canopy."""

    @staticmethod
    def make_starfield(count=STAR_COUNT, seed=STAR_SEED):
        """Generate a starfield as (nx, ny, radius, brightness), normalised to canopy area.

        Args:
            count: Number of stars to generate
            seed: Random seed for reproducibility

        Returns:
            List of star tuples (nx, ny, radius, brightness)
        """
        rng = random.Random(seed)
        stars = []
        for _ in range(count):
            brightness = rng.randint(70, 255)
            # Bias small: a few bright stars read better than a uniform wash.
            radius = 1 if rng.random() < 0.82 else 2
            stars.append((rng.random(), rng.random(), radius, brightness))
        return stars

    @staticmethod
    def draw(surface, stars, w, h):
        """Draw stars as points or small circles.

        Args:
            surface: Pygame surface to draw on
            stars: List of star tuples from make_starfield()
            w: Window width
            h: Window height
        """
        view_h = int(h * CONSOLE_TOP)

        for nx, ny, radius, brightness in stars:
            x = int(nx * w)
            y = int(ny * view_h)

            # Slightly cool tint keeps the stars from looking like flat white dots.
            color = (brightness, brightness, min(255, brightness + 18))
            if radius == 1:
                surface.set_at((x, y), color)
            else:
                pygame.draw.circle(surface, color, (x, y), radius)
