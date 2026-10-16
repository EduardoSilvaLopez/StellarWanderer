"""Resource bars: the ship's resources, one row each, top to bottom: credits (a value), maintenance and energy (bars) and
temperature (a bar from 25 to its value, on its scale). Each row has its label on the left, and the rows line up with each other."""

from __future__ import annotations
from typing import Any, Optional, Tuple, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM, AMBER, BINDING_MARK_RED, BINDING_NEAR_GREEN

if TYPE_CHECKING:
    from spaceships.ship import Ship

# The bar's colour by how much is left: red when empty, amber at half, green when full.
GRADIENT = ((0.0, BINDING_MARK_RED), (0.5, AMBER), (1.0, BINDING_NEAR_GREEN))
WARNING_COLOUR = AMBER  # the maintenance warning level, a vertical line across its bar
TEMPERATURE_MIN_WIDTH = 3  # pixels: the bar's width when the temperature is the ideal one
TEMPERATURE_IDEAL = 25  # degrees: the green line. The colour moves away from it towards either extreme of the scale.
CREDIT_SYMBOL = 'Ȼ'
ROW_LABELS = ('Credits', 'Maintenance', 'Energy', 'Temperature')


def level_colour(fraction: float) -> Tuple[int, int, int]:
    """The colour of a bar at `fraction` of its maximum: a gradient through GRADIENT's stops."""
    f = max(0.0, min(1.0, fraction))
    for (low_at, low), (high_at, high) in zip(GRADIENT, GRADIENT[1:]):
        if f <= high_at:
            t = (f - low_at) / (high_at - low_at)
            return tuple(round(a + (b - a) * t) for a, b in zip(low, high))
    return GRADIENT[-1][1]


def format_credits(value: float) -> str:
    """Commas for thousands, a dot for decimals, at most three decimals and only the ones needed: 1234.5 -> '1,234.5 Ȼ'."""
    text = f'{value:,.3f}'.rstrip('0').rstrip('.')
    return f'{text} {CREDIT_SYMBOL}'


def temperature_stress(ship: Ship, temperature: float) -> float:
    """0 at TEMPERATURE_IDEAL, 1 at either end of the scale (Ship.TEMP_MIN, Ship.TEMP_MAX), linear on each side."""
    if temperature >= TEMPERATURE_IDEAL:
        stress = (temperature - TEMPERATURE_IDEAL) / (ship.TEMP_MAX - TEMPERATURE_IDEAL)
    else:
        stress = (TEMPERATURE_IDEAL - temperature) / (TEMPERATURE_IDEAL - ship.TEMP_MIN)
    return max(0.0, min(1.0, stress))


def _credits_shown() -> bool:
    """Credits are hidden in Those-Who-Share space. The row keeps its place, so the other rows do not move."""
    import game_environment as gem
    from galaxies.politics import political_entity
    return gem.current_environment.nearest_system.political_entity != political_entity.THOSE_WHO_SHARE


def _draw_bar(surface: pygame.Surface, track: pygame.Rect, fraction: float, warning: Optional[float] = None) -> None:
    """A bar filled to `fraction`, with a vertical line at `warning` (a fraction) if given."""
    pygame.draw.rect(surface, ACCENT_DIM, track, 1)
    inner = track.inflate(-4, -4)
    filled = int(inner.width * max(0.0, min(1.0, fraction)))
    pygame.draw.rect(surface, level_colour(fraction), (inner.left, inner.top, filled, inner.height))
    if warning is not None:
        x = inner.left + int(inner.width * warning)
        pygame.draw.line(surface, WARNING_COLOUR, (x, track.top - 3), (x, track.bottom + 2), 2)


def _draw_temperature(surface: pygame.Surface, track: pygame.Rect, ship: Ship, temperature: float) -> None:
    """The scale from Ship.TEMP_MIN to Ship.TEMP_MAX, with a bar from TEMPERATURE_IDEAL to the temperature, coloured by
    its stress. Equal values give a single line of TEMPERATURE_MIN_WIDTH pixels."""
    pygame.draw.rect(surface, ACCENT_DIM, track, 1)
    inner = track.inflate(-4, -4)

    def x_of(value: float) -> int:
        return inner.left + int(inner.width * max(0.0, min(1.0, (value - ship.TEMP_MIN) / (ship.TEMP_MAX - ship.TEMP_MIN))))

    x_ideal, x_now = x_of(TEMPERATURE_IDEAL), x_of(temperature)
    left, right = min(x_ideal, x_now), max(x_ideal, x_now)
    if right - left < TEMPERATURE_MIN_WIDTH:
        left = x_now - TEMPERATURE_MIN_WIDTH // 2
        right = left + TEMPERATURE_MIN_WIDTH
    colour = level_colour(1.0 - temperature_stress(ship, temperature))
    pygame.draw.rect(surface, colour, (left, inner.top, right - left, inner.height))


class ResourceBars:
    """The rows of resources, top to bottom: see ROW_LABELS. Credits is a value; the others are bars or a scale."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, rect: pygame.Rect) -> None:
        """The rows stack down from the top of `rect`, each with its label on the left. The group has no frame of its
        own: its rows are what the player sees, aligned with each other."""
        label_font = fonts.get(max(9, int(h * 0.017)))

        pad = max(6, rect.width // 16)
        bar_height = max(8, int(h * 0.02))
        row_pitch = max(bar_height, label_font.get_linesize()) + max(4, bar_height // 2)
        label_width = max(label_font.size(name)[0] for name in ROW_LABELS)
        bar_left = rect.left + pad + label_width + pad
        bar_right = rect.right - pad

        credits_shown = _credits_shown()
        for index, name in enumerate(ROW_LABELS):
            if name == 'Credits' and not credits_shown:
                continue  # the row is empty, but its place stays
            centre_y = rect.top + pad + row_pitch * index + bar_height // 2
            label = label_font.render(name, True, ACCENT)
            surface.blit(label, label.get_rect(midleft=(rect.left + pad, centre_y)))

            track = pygame.Rect(bar_left, centre_y - bar_height // 2, bar_right - bar_left, bar_height)
            if name == 'Credits':
                value = label_font.render(format_credits(ship.owner.credits), True, ACCENT)
                surface.blit(value, value.get_rect(midleft=(bar_left, centre_y)))
            elif name == 'Maintenance':
                # outposts only restore it to 0.8: that is intended
                _draw_bar(surface, track, max(0.0, min(1.0, ship.maintenance)), warning=ship.MAINTENANCE_WARNING)
            elif name == 'Energy':
                _draw_bar(surface, track, ship.energy / ship.ENERGY_MAX)
            else:
                _draw_temperature(surface, track, ship, ship.temperature)
