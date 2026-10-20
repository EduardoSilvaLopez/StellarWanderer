"""The small buttons under the political entity's icon: what the pilot knows of the stellar systems and of the people, and,
when there is a mission to see (see shows_missions), the pending missions, below the stellar systems."""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Optional, Tuple
import pygame

from common.paths import resource_path
from ..constants import ACCENT, ACCENT_DIM, READOUT_BG
from .political_info import PoliticalInfo

if TYPE_CHECKING:
    from galaxies.people.player import Player

SYSTEMS = 'systems'  # the names the buttons are known by (see hit)
PEOPLE = 'people'
MISSIONS = 'missions'
ICON_FILES: Dict[str, str] = {SYSTEMS: 'stellar_system.png', PEOPLE: 'head.png', MISSIONS: 'missions.png'}  # white, in resources/icons


def shows_missions(player: Player) -> bool:
    """The missions button is there for a pilot the outposts trust (the mission board's rule) or with a mission to see."""
    from galaxies.missions import OPEN  # local: the missions import the player, which imports this package
    from galaxies.missions.mission_board import MissionBoard
    return MissionBoard.is_available(player) or any(m.status == OPEN for m in player.missions)


class CockpitButtons:
    """Square buttons under the political icon: a miniature stellar system and a head side by side, and the missions below
    the stellar system. The cockpit only draws them; main opens the dialog when `hit` says one was pressed. Their places are
    those of the last draw."""

    SIZE = 48
    MIN_SIZE = 28
    GAP = 10  # between the buttons and the political icon
    BUTTON_GAP = 6  # between the two buttons
    ICON_MARGIN = 7  # between a button's edge and its icon

    rects: Dict[str, pygame.Rect] = {}
    _icons: Dict[str, pygame.Surface] = {}
    _tinted: Dict[Tuple[str, int, Tuple[int, int, int]], pygame.Surface] = {}

    @staticmethod
    def _icon(name: str) -> Optional[pygame.Surface]:
        if name not in CockpitButtons._icons:
            try:
                CockpitButtons._icons[name] = pygame.image.load(resource_path('icons', ICON_FILES[name])).convert_alpha()
            except (FileNotFoundError, pygame.error):
                CockpitButtons._icons[name] = None  # the button is drawn without its icon
        return CockpitButtons._icons[name]

    @staticmethod
    def _tinted_icon(name: str, size: int, colour: Tuple[int, int, int]) -> Optional[pygame.Surface]:
        """The icon, scaled to `size` and painted `colour` (the files are white)."""
        key = (name, size, colour)
        if key not in CockpitButtons._tinted:
            icon = CockpitButtons._icon(name)
            if icon is None:
                return None
            scaled = pygame.transform.smoothscale(icon, (size, size))
            scaled.fill((*colour, 255), special_flags=pygame.BLEND_RGBA_MULT)
            CockpitButtons._tinted[key] = scaled
        return CockpitButtons._tinted[key]

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, top: int, player: Player) -> None:
        """Draw the buttons with their top edge `top` pixels down (the bottom of the political icon, plus the gap)."""
        x = PoliticalInfo.PADDING_X
        y = top + CockpitButtons.GAP
        size = CockpitButtons.SIZE
        missions = shows_missions(player)
        while size > CockpitButtons.MIN_SIZE:  # both must fit the hull width at their bottom edge, and the column below
            available = PoliticalInfo.hull_edge_x(y + size, w, h) - x - PoliticalInfo.EDGE_MARGIN
            fits = 2 * size + CockpitButtons.BUTTON_GAP <= available
            if missions:
                below = PoliticalInfo.hull_edge_x(y + 2 * size + CockpitButtons.BUTTON_GAP, w, h) - x - PoliticalInfo.EDGE_MARGIN
                fits = fits and size <= below
            if fits:
                break
            size -= 2

        mouse = pygame.mouse.get_pos() if pygame.mouse.get_focused() else None
        CockpitButtons.rects = {}
        places = [(SYSTEMS, pygame.Rect(x, y, size, size)), (PEOPLE, pygame.Rect(x + size + CockpitButtons.BUTTON_GAP, y, size, size))]
        if missions:
            places.append((MISSIONS, pygame.Rect(x, y + size + CockpitButtons.BUTTON_GAP, size, size)))
        for name, rect in places:
            CockpitButtons.rects[name] = rect
            hovered = mouse is not None and rect.collidepoint(mouse)
            colour = ACCENT if hovered else ACCENT_DIM
            pygame.draw.rect(surface, READOUT_BG, rect, border_radius=6)
            pygame.draw.rect(surface, colour, rect, 2, border_radius=6)
            icon = CockpitButtons._tinted_icon(name, size - 2 * CockpitButtons.ICON_MARGIN, ACCENT if hovered else (150, 215, 205))
            if icon is not None:
                surface.blit(icon, icon.get_rect(center=rect.center))

    @staticmethod
    def hit(position: Tuple[int, int]) -> Optional[str]:
        """The button (SYSTEMS, PEOPLE or MISSIONS) at a window position, or None."""
        return next((name for name, rect in CockpitButtons.rects.items() if rect.collidepoint(position)), None)
