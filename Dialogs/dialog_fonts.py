"""Fonts for message dialogs: Orbitron for titles, Exo 2 for body text (Resources/fonts, SIL OFL)."""

from __future__ import annotations
from typing import Dict, Tuple
import logging
import os
import pygame

logger = logging.getLogger(__name__)

FONTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'Resources', 'fonts')
TITLE_FONT_FILE = 'Orbitron.ttf'
BODY_FONT_FILE = 'Exo2.ttf'

_cache: Dict[Tuple[str, int], pygame.font.Font] = {}


def _load(file_name: str, size: int) -> pygame.font.Font:
    key = (file_name, size)
    if key not in _cache:
        path = os.path.join(FONTS_DIR, file_name)
        try:
            _cache[key] = pygame.font.Font(path, size)
        except (FileNotFoundError, pygame.error) as error:
            logger.warning(f"Font {path} not available ({error}); using the system font.")
            _cache[key] = pygame.font.SysFont('consolas,dejavusansmono,couriernew,monospace', size)
    return _cache[key]


def title_font(size: int) -> pygame.font.Font:
    return _load(TITLE_FONT_FILE, size)


def body_font(size: int) -> pygame.font.Font:
    return _load(BODY_FONT_FILE, size)
