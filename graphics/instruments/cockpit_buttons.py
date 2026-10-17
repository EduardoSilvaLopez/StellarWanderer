"""The two small buttons under the political entity's icon: what the pilot knows of the stellar systems, and of the people."""

from __future__ import annotations
from typing import Dict, Optional, Tuple
import pygame

from common.paths import resource_path
from ..constants import ACCENT, ACCENT_DIM, READOUT_BG
from .political_info import PoliticalInfo

SYSTEMS = 'systems'  # the names the buttons are known by (see hit)
PEOPLE = 'people'
ICON_FILES: Dict[str, str] = {SYSTEMS: 'stellar_system.png', PEOPLE: 'head.png'}  # white on transparent, in resources/icons


class CockpitButtons:
    """Two square buttons side by side, under the political icon: a miniature stellar system and a head. The cockpit
    only draws them; main opens the dialog when `hit` says one was pressed. Their places are those of the last draw."""

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
    def draw(surface: pygame.Surface, w: int, h: int, top: int) -> None:
        """Draw the buttons with their top edge `top` pixels down (the bottom of the political icon, plus the gap)."""
        x = PoliticalInfo.PADDING_X
        y = top + CockpitButtons.GAP
        size = CockpitButtons.SIZE
        while size > CockpitButtons.MIN_SIZE:  # both must fit the hull width at their bottom edge
            available = PoliticalInfo._hull_edge_x(y + size, w, h) - x - PoliticalInfo.EDGE_MARGIN
            if 2 * size + CockpitButtons.BUTTON_GAP <= available:
                break
            size -= 2

        mouse = pygame.mouse.get_pos() if pygame.mouse.get_focused() else None
        CockpitButtons.rects = {}
        for index, name in enumerate((SYSTEMS, PEOPLE)):
            rect = pygame.Rect(x + index * (size + CockpitButtons.BUTTON_GAP), y, size, size)
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
        """The button (SYSTEMS or PEOPLE) at a window position, or None."""
        return next((name for name, rect in CockpitButtons.rects.items() if rect.collidepoint(position)), None)
