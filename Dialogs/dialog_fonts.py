"""Fonts for message dialogs: Orbitron for titles, the body font for text (Resources/fonts, SIL OFL)."""

from __future__ import annotations
from typing import Dict, Tuple
import logging
import os
import pygame

from Graphics.Constants import FONT_FILE
from Graphics.fallback_font import FALLBACK_FONTS, FallbackFont

logger = logging.getLogger(__name__)

FONTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'Resources', 'fonts')
TITLE_FONT_FILE = 'Orbitron.ttf'
# The body font is the same as the instruments' (Graphics/Constants.py), and its size goes with it: 20 for Oxanium,
# chosen by eye. Change the size here when the font changes.
BODY_FONT_FILE = FONT_FILE
BODY_FONT_SIZE = 20

_cache: Dict[Tuple[str, int], FallbackFont] = {}


def _load(file_name: str, size: int) -> FallbackFont:
    """The font file at `size`, with the system font for characters it lacks (see FallbackFont)."""
    key = (file_name, size)
    if key not in _cache:
        path = os.path.join(FONTS_DIR, file_name)
        try:
            primary = pygame.font.Font(path, size)
        except (FileNotFoundError, pygame.error) as error:
            logger.warning(f"Font {path} not available ({error}); using the system font.")
            primary = pygame.font.SysFont(FALLBACK_FONTS, size)
        _cache[key] = FallbackFont(primary, size)
    return _cache[key]


def title_font(size: int) -> FallbackFont:
    return _load(TITLE_FONT_FILE, size)


def body_font(size: int = BODY_FONT_SIZE) -> FallbackFont:
    return _load(BODY_FONT_FILE, size)
