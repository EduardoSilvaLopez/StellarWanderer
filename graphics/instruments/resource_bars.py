"""Resource bars: the ship's resources, one row each, top to bottom: credits (a value), maintenance and energy (bars),
temperature (a bar from 25 to its value, on its scale) and gravity (the pull where the ship is, against the combined
thrust, green when low). Each row has its label on the left, and the rows line up with each other. The first row's
label sits on the top of the group's rect, where the scanner and cargo titles are."""

from __future__ import annotations
from typing import Any, Optional, Tuple, TYPE_CHECKING
import pygame
from ..constants import ACCENT, ACCENT_DIM, AMBER, BINDING_MARK_RED, BINDING_NEAR_GREEN, READOUT_BG

if TYPE_CHECKING:
    from spaceships.ship import Ship

# The bar's colour by how much is left: red when empty, amber at half, green when full.
GRADIENT = ((0.0, BINDING_MARK_RED), (0.5, AMBER), (1.0, BINDING_NEAR_GREEN))
WARNING_COLOUR = AMBER  # the maintenance warning level, a vertical line across its bar
TEMPERATURE_MIN_WIDTH = 3  # pixels: the bar's width when the temperature is the ideal one
TEMPERATURE_IDEAL = 25  # degrees: the green line. The colour moves away from it towards either extreme of the scale.
CREDIT_SYMBOL = 'Ȼ'
ROW_LABELS = ('Credits', 'Maintenance', 'Energy', 'Temperature', 'Gravity')


def level_colour(fraction: float) -> Tuple[int, int, int]:
    """The colour of a bar at `fraction` of its maximum: a gradient through GRADIENT's stops."""
    f = max(0.0, min(1.0, fraction))
    for (low_at, low), (high_at, high) in zip(GRADIENT, GRADIENT[1:]):
        if f <= high_at:
            t = (f - low_at) / (high_at - low_at)
            return tuple(round(a + (b - a) * t) for a, b in zip(low, high))
    return GRADIENT[-1][1]


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
    """The rows of resources, top to bottom: see ROW_LABELS. Credits is a value; the others are bars or a scale. Under
    them, the ORBIT button (see orbit_hit). Its place is that of the last draw."""

    orbit_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

    @staticmethod
    def orbit_enabled(ship: Ship) -> bool:
        """The ORBIT button lights up in a fixed zone that pulls, unbound."""
        return not ship.is_bound and ship.navigation.pull() > 0.0

    @staticmethod
    def orbit_hit(position: Tuple[int, int], ship: Ship) -> bool:
        """Whether a click at `position` is on the ORBIT button while it does something: lit, or running (to give it
        up). Only in the cockpit, where the button is drawn."""
        if ship.owner.inside is not None:
            return False
        return ResourceBars.orbit_rect.collidepoint(position) and (
            ship.navigation.orbit is not None or ResourceBars.orbit_enabled(ship))

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
        for index, name in enumerate(ROW_LABELS):
            if name == 'Credits' and not legal:
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
            else:
                # the pull against the most the engines give: green when low, red at the limit
                fraction = min(1.0, ship.navigation.pull() / ship.navigation.combined_thrust())
                _draw_bar(surface, track, fraction, colour=level_colour(1.0 - fraction))

        # The ORBIT button, under the gravity row: dimmed, green in a fixed zone that pulls, and filled while the
        # assist flies the ship.
        gravity_centre = rect.top + label_font.get_height() // 2 + row_pitch * (len(ROW_LABELS) - 1)
        button_top = gravity_centre + bar_height // 2 + max(4, bar_height // 2)
        ResourceBars.orbit_rect = pygame.Rect(bar_left, button_top, bar_right - bar_left,
                                              label_font.get_height() + 6)
        running = ship.navigation.orbit is not None
        colour = ACCENT if running else (BINDING_NEAR_GREEN if ResourceBars.orbit_enabled(ship) else ACCENT_DIM)
        if running:
            pygame.draw.rect(surface, colour, ResourceBars.orbit_rect, border_radius=3)
        pygame.draw.rect(surface, colour, ResourceBars.orbit_rect, 1, border_radius=3)
        text = label_font.render('ORBIT', True, READOUT_BG if running else colour)
        surface.blit(text, text.get_rect(center=ResourceBars.orbit_rect.center))
