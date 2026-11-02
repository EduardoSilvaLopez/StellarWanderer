"""Resource bars: the ship's resources, one row each, top to bottom: credits (a value), maintenance and energy (bars),
temperature (a bar from 25 to its value, on its scale) and gravity (a bar of the pull where the ship is against the combined thrust, green when low, labelled
with the pull in m/s^2), then, in the atmosphere of a giant only, the pressure (a bar of the outside pressure above the
atmosphere inside the hull, up to the ship's PRESSURE_MAX, as gravity is drawn, labelled with the whole pressure in
atmospheres) and the temperature of the gas outside (K, a plain
value). Each row has its label on the left, and the rows line up with each other. The first row's
label sits on the top of the group's rect, where the scanner and cargo titles are."""

from __future__ import annotations
from typing import Any, Optional, Tuple, TYPE_CHECKING
import pygame
from ..constants import (ACCENT, ACCENT_DIM, AMBER, BINDING_MARK_RED, BINDING_NEAR_GREEN, GRAVITY_AMBER,
                         GRAVITY_GREEN, GRAVITY_RED)

if TYPE_CHECKING:
    from spaceships.ship import Ship

# The bar's colour by how much is left: red when empty, amber at half, green when full.
GRADIENT = ((0.0, BINDING_MARK_RED), (0.5, AMBER), (1.0, BINDING_NEAR_GREEN))
# the gravity bar: green when the pull is low, red at the limit of the thrust
GRAVITY_GRADIENT = ((0.0, GRAVITY_GREEN), (0.5, GRAVITY_AMBER), (1.0, GRAVITY_RED))
WARNING_COLOUR = AMBER  # the maintenance warning level, a vertical line across its bar
TEMPERATURE_MIN_WIDTH = 3  # pixels: the bar's width when the temperature is the ideal one
TEMPERATURE_IDEAL = 25  # degrees: the green line. The colour moves away from it towards either extreme of the scale.
CREDIT_SYMBOL = 'Ȼ'
ROW_LABELS = ('Credits', 'Maintenance', 'Energy', 'Temperature', 'Gravity', 'Pressure', 'Outside')
ATMOSPHERE_ROWS = ('Pressure', 'Outside')  # the gas around the ship (a bar, and a value in K), shown only while in one
ATMOSPHERE = 1.0e5  # Pa: one atmosphere as the ship configurations count it (PRESSURE_MAX): the air inside the hull


Stops = Tuple[Tuple[float, Tuple[int, int, int]], ...]


def level_colour(fraction: float, gradient: Stops = GRADIENT) -> Tuple[int, int, int]:
    """The colour of a bar at `fraction` of its maximum: a gradient through the stops of `gradient`."""
    f = max(0.0, min(1.0, fraction))
    for (low_at, low), (high_at, high) in zip(gradient, gradient[1:]):
        if f <= high_at:
            t = (f - low_at) / (high_at - low_at)
            return tuple(round(a + (b - a) * t) for a, b in zip(low, high))
    return gradient[-1][1]


def format_credits(value: float) -> str:
    """Commas for thousands, a dot for decimals, at most three decimals and only the ones needed: 1234.5 -> '1,234.5
    Ȼ'."""
    text = f'{value:,.3f}'.rstrip('0').rstrip('.')
    return f'{text} {CREDIT_SYMBOL}'


def temperature_stress(ship: Ship) -> float:
    """How far the ship's temperature is from TEMPERATURE_IDEAL: 0 there, 1 at either end of the scale (Ship.TEMP_MIN,
    Ship.TEMP_MAX), linear on each side."""
    temperature = ship.temperature
    if temperature >= TEMPERATURE_IDEAL:
        stress = (temperature - TEMPERATURE_IDEAL) / (ship.TEMP_MAX - TEMPERATURE_IDEAL)
    else:
        stress = (TEMPERATURE_IDEAL - temperature) / (TEMPERATURE_IDEAL - ship.TEMP_MIN)
    return max(0.0, min(1.0, stress))


def format_atmospheres(pressure: float) -> str:
    """A pressure (Pa) in atmospheres, in the digits that read well: 0.52 atm, 12.3 atm, 4,500 atm, 1.2e+09 atm."""
    atmospheres = pressure / ATMOSPHERE
    if atmospheres < 0.01 or atmospheres >= 1e6:
        return f'{atmospheres:.1e} atm'
    if atmospheres >= 1000:
        return f'{atmospheres:,.0f} atm'
    return f'{atmospheres:.1f} atm' if atmospheres >= 10 else f'{atmospheres:.2f} atm'


def credits_shown() -> bool:
    """Credits are hidden in Those-Who-Share space, where they are illegal (the cargo list then shows them, in red, as
    contraband). The row keeps its place, so the other rows do not move."""
    import game_environment as gem
    from galaxies.politics import political_entity
    return gem.current_environment.nearest_system.political_entity != political_entity.THOSE_WHO_SHARE


def _draw_bar(surface: pygame.Surface, track: pygame.Rect, fraction: float, warning: Optional[float] = None,
              colour: Optional[Tuple[int, int, int]] = None) -> None:
    """A bar filled to `fraction`, in `colour` (else the level's colour), with a vertical line at `warning` (a fraction)
    if given."""
    pygame.draw.rect(surface, ACCENT_DIM, track, 1)
    inner = track.inflate(-4, -4)
    filled = int(inner.width * max(0.0, min(1.0, fraction)))
    pygame.draw.rect(surface, colour or level_colour(fraction), (inner.left, inner.top, filled, inner.height))
    if warning is not None:
        x = inner.left + int(inner.width * warning)
        pygame.draw.line(surface, WARNING_COLOUR, (x, track.top - 3), (x, track.bottom + 2), 2)


def _draw_over_bar(surface: pygame.Surface, font: Any, text: str, origin: Tuple[int, int]) -> None:
    """A value over a bar, from `origin` (its left middle), with a dark shadow under it so it reads over the filled part."""
    shadow = font.render(text, True, (0, 0, 0))
    surface.blit(shadow, shadow.get_rect(midleft=(origin[0] + 1, origin[1] + 1)))
    value = font.render(text, True, ACCENT)
    surface.blit(value, value.get_rect(midleft=origin))


def _draw_temperature(surface: pygame.Surface, track: pygame.Rect, ship: Ship) -> None:
    """The scale from Ship.TEMP_MIN to Ship.TEMP_MAX, with a bar from TEMPERATURE_IDEAL to the ship's temperature,
    coloured by its stress. Equal values give a single line of TEMPERATURE_MIN_WIDTH pixels."""
    temperature = ship.temperature
    pygame.draw.rect(surface, ACCENT_DIM, track, 1)
    inner = track.inflate(-4, -4)

    def x_of(value: float) -> int:
        return inner.left + int(inner.width * max(0.0, min(1.0, (value - ship.TEMP_MIN)
                                                           / (ship.TEMP_MAX - ship.TEMP_MIN))))

    x_ideal, x_now = x_of(TEMPERATURE_IDEAL), x_of(temperature)
    left, right = min(x_ideal, x_now), max(x_ideal, x_now)
    if right - left < TEMPERATURE_MIN_WIDTH:
        left = x_now - TEMPERATURE_MIN_WIDTH // 2
        right = left + TEMPERATURE_MIN_WIDTH
    colour = level_colour(1.0 - temperature_stress(ship))
    pygame.draw.rect(surface, colour, (left, inner.top, right - left, inner.height))


class ResourceBars:
    """The rows of resources, top to bottom: see ROW_LABELS. Credits is a value; the others are bars or a scale."""


    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, rect: pygame.Rect) -> None:
        """The rows stack down from the top of `rect`, each with its label on the left. The first label's top is the
        top of `rect`, the line of the scanner and cargo titles. The group has no frame of its own: its rows are what
        the player sees, aligned with each other."""
        label_font = fonts.get(max(9, int(h * 0.017)))

        pad = max(6, rect.width // 16)
        bar_height = max(8, int(h * 0.02))
        row_pitch = max(bar_height, label_font.get_linesize()) + max(4, bar_height // 2)
        label_width = max(label_font.size(name)[0] for name in ROW_LABELS)
        bar_left = rect.left + pad + label_width + pad
        bar_right = rect.right - pad

        legal = credits_shown()
        ambient = ship.navigation.ambient()
        for index, name in enumerate(ROW_LABELS):
            if name == 'Credits' and not legal or name in ATMOSPHERE_ROWS and ambient is None:
                continue  # the row is empty, but its place stays
            centre_y = rect.top + label_font.get_height() // 2 + row_pitch * index
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
                _draw_bar(surface, track, ship.energy / ship.energy_max)
            elif name == 'Temperature':
                _draw_temperature(surface, track, ship)
            elif name == 'Pressure':
                # the outside pressure against the one the hull is built for, counted from the atmosphere inside it
                # (the hull feels only the excess): green when low, red at the limit; its value in atmospheres over it
                fraction = max(0.0, min(1.0, (ambient[0] - ATMOSPHERE) / max(ship.PRESSURE_MAX - ATMOSPHERE, 1.0)))
                _draw_bar(surface, track, fraction, colour=level_colour(fraction, GRAVITY_GRADIENT))
                _draw_over_bar(surface, label_font, format_atmospheres(ambient[0]), (bar_left + pad // 2, centre_y))
            elif name == 'Outside':
                value = label_font.render(f'{ambient[1]:.0f} K', True, ACCENT)
                surface.blit(value, value.get_rect(midleft=(bar_left, centre_y)))
            else:
                # the pull against the most the engines give: green when low, red at the limit; its value in m/s^2 over it
                pull = ship.navigation.pull()
                fraction = min(1.0, pull / ship.navigation.combined_thrust())
                _draw_bar(surface, track, fraction, colour=level_colour(fraction, GRAVITY_GRADIENT))
                _draw_over_bar(surface, label_font, f'{pull:.2f} m/s²', (bar_left + pad // 2, centre_y))
