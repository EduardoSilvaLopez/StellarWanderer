from __future__ import annotations
from typing import Tuple, Dict
import os
import pygame

from .constants import FONT_FILE
from .fallback_font import FALLBACK_FONTS, FallbackFont

FONTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'Resources', 'fonts')


class FontCache:
    """Fonts are rebuilt on resize, so keep one per pixel size.

    The body font is FONT_FILE (Oxanium), also used by the instruments and the message dialogs. Characters the font
    lacks, such as Δ, are drawn with the system monospace font by FallbackFont (see fallback_font.py), so every label
    that uses these fonts must go through FontCache (or dialog_fonts), not pygame.font directly."""

    def __init__(self) -> None:
        self._fonts: Dict[Tuple[int, bool], FallbackFont] = {}

    def get(self, size: int, bold: bool = False) -> FallbackFont:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = self._load(size, bold)
        return self._fonts[key]

    @staticmethod
    def _load(size: int, bold: bool) -> FallbackFont:
        """FONT_FILE from Resources/fonts, with the system font for characters it lacks. Bold is synthesised:
        pygame cannot pick a weight of a variable font."""
        try:
            primary = pygame.font.Font(os.path.join(FONTS_DIR, FONT_FILE), size)
        except (FileNotFoundError, pygame.error):
            primary = pygame.font.SysFont(FALLBACK_FONTS, size, bold=bold)
        primary.set_bold(bold)
        return FallbackFont(primary, size, bold)

    def render_to_fit(self, text: str, color: Tuple[int, int, int], max_width: int, size: int) -> pygame.Surface:
        """Render `text`, stepping the font down until it fits `max_width`."""
        while size > 7:
            surf = self.get(size).render(text, True, color)
            if surf.get_width() <= max_width:
                return surf
            size -= 1
        return self.get(size).render(text, True, color)
