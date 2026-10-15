"""Resource bars: the ship's resources as horizontal bars, each with its label on the left."""

from __future__ import annotations
from typing import Any, List, Tuple, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM, AMBER, BINDING_MARK_RED, BINDING_NEAR_GREEN

if TYPE_CHECKING:
    from Spaceships.ship import Ship

# The bar's colour by how much is left: red when empty, amber at half, green when full.
GRADIENT = ((0.0, BINDING_MARK_RED), (0.5, AMBER), (1.0, BINDING_NEAR_GREEN))


def level_colour(fraction: float) -> Tuple[int, int, int]:
    """The colour of a bar at `fraction` of its maximum: a gradient through GRADIENT's stops."""
    f = max(0.0, min(1.0, fraction))
    for (low_at, low), (high_at, high) in zip(GRADIENT, GRADIENT[1:]):
        if f <= high_at:
            t = (f - low_at) / (high_at - low_at)
            return tuple(round(a + (b - a) * t) for a, b in zip(low, high))
    return GRADIENT[-1][1]


class ResourceBars:
    """One bar per resource, each showing the amount left against its maximum, with its label on the left."""

    @staticmethod
    def levels(ship: Ship) -> List[Tuple[str, float]]:
        """(label, fraction of the maximum left) for every resource shown, top to bottom."""
        return [('Energy', ship.energy / ship.energy_max)]

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, rect: pygame.Rect) -> None:
        """The bars stack down from the top of `rect`, each one right-aligned in it, its label on the left. The group
        has no frame of its own: its rows are what the player sees, aligned with each other."""
        label_font = fonts.get(max(9, int(h * 0.017)))

        levels = ResourceBars.levels(ship)
        pad = max(6, rect.width // 16)
        bar_height = max(8, int(h * 0.02))
        row_pitch = max(bar_height, label_font.get_linesize()) + max(4, bar_height // 2)
        label_width = max(label_font.size(name)[0] for name, _ in levels)
        bar_left = rect.left + pad + label_width + pad
        bar_right = rect.right - pad

        for index, (name, fraction) in enumerate(levels):
            centre_y = rect.top + pad + row_pitch * index + bar_height // 2
            label = label_font.render(name, True, ACCENT)
            surface.blit(label, label.get_rect(midleft=(rect.left + pad, centre_y)))

            track = pygame.Rect(bar_left, centre_y - bar_height // 2, bar_right - bar_left, bar_height)
            pygame.draw.rect(surface, ACCENT_DIM, track, 1)
            inner = track.inflate(-4, -4)
            filled = int(inner.width * max(0.0, min(1.0, fraction)))
            pygame.draw.rect(surface, level_colour(fraction), (inner.left, inner.top, filled, inner.height))
