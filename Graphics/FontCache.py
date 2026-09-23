from __future__ import annotations
from typing import Tuple, Dict
import pygame


class FontCache:
    """Fonts are rebuilt on resize, so keep one per pixel size."""

    def __init__(self) -> None:
        self._fonts: Dict[Tuple[int, bool], pygame.font.Font] = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont(
                'consolas,dejavusansmono,couriernew,monospace', size, bold=bold
            )
        return self._fonts[key]

    def render_to_fit(self, text: str, color: Tuple[int, int, int], max_width: int, size: int) -> pygame.Surface:
        """Render `text`, stepping the font down until it fits `max_width`."""
        while size > 7:
            surf = self.get(size).render(text, True, color)
            if surf.get_width() <= max_width:
                return surf
            size -= 1
        return self.get(size).render(text, True, color)
