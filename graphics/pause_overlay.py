"""The veil over a paused game (see Player.is_paused): a translucent layer over the whole window, with the word PAUSED and
how to resume. The main loop draws it above the frame while the game is paused and no dialog is open (a dialog has its own
backdrop, drawn instead of it)."""

from typing import Any, Dict, Tuple
import pygame
from .constants import ACCENT

HINT_COLOUR = (190, 205, 205)

VEIL_ALPHA = 110  # 0 is clear, 255 is solid black: the instruments stay readable through it
_layers: Dict[Tuple[int, int], pygame.Surface] = {}


def pause_layer(fonts: Any, width: int, height: int) -> pygame.Surface:
    """The veil for a window of width x height, built once per size."""
    if (width, height) not in _layers:
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        layer.fill((0, 0, 0, VEIL_ALPHA))
        title = fonts.get(max(28, int(height * 0.09)), bold=True).render('PAUSED', True, ACCENT)
        hint = fonts.get(max(12, int(height * 0.025))).render('Numpad + resumes the time', True, HINT_COLOUR)
        layer.blit(title, title.get_rect(center=(width // 2, height // 2 - title.get_height() // 2)))
        layer.blit(hint, hint.get_rect(center=(width // 2, height // 2 + title.get_height())))
        _layers[(width, height)] = layer
    return _layers[(width, height)]
