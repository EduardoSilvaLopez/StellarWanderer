"""The TRAVEL button, bottom left of the cockpit while the ship is unbound, the right half of the ORBIT button's row
(see orbit_button.py): it starts the TRAVEL autopilot (spaceships/travel_assist.py), which flies the ship to the
targeted body, or gives the controls back."""

from __future__ import annotations
from typing import Any, Tuple, TYPE_CHECKING
import pygame

from ..constants import ACCENT, ACCENT_DIM, BINDING_NEAR_GREEN, READOUT_BG
from .orbit_button import OrbitButton

if TYPE_CHECKING:
    from spaceships.ship import Ship


class TravelButton:
    """The TRAVEL button: lit while it can be pressed, pressed while the autopilot flies. Its place is that of the
    last draw, and a click counts only in the cockpit (see hit)."""

    rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

    @staticmethod
    def hit(position: Tuple[int, int], ship: Ship) -> bool:
        """Whether a click at `position` is on the button while it does something: lit, or flying (to give it up)."""
        from spaceships.travel_assist import TravelAssist
        if ship.owner.inside is not None:
            return False
        return TravelButton.rect.collidepoint(position) and (ship.navigation.travel is not None
                                                             or TravelAssist.enabled(ship))

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, left: int, bottom: int, width: int) -> None:
        """The button at the bottom, the right half of the row `width` wide from `left`."""
        from spaceships.travel_assist import TravelAssist
        if ship.is_bound:
            return
        label_font = fonts.get(max(9, int(h * 0.017)))
        height = label_font.get_height() + 6
        half = (width - OrbitButton.GAP) // 2
        TravelButton.rect = pygame.Rect(left + width - half, bottom - height, half, height)
        running = ship.navigation.travel is not None
        colour = ACCENT if running else (BINDING_NEAR_GREEN if TravelAssist.enabled(ship) else ACCENT_DIM)
        if running:
            pygame.draw.rect(surface, colour, TravelButton.rect, border_radius=3)
        pygame.draw.rect(surface, colour, TravelButton.rect, 1, border_radius=3)
        text = label_font.render('TRAVEL', True, READOUT_BG if running else colour)
        surface.blit(text, text.get_rect(center=TravelButton.rect.center))
