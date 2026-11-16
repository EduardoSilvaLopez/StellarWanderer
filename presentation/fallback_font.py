"""A font with a fallback for the characters it lacks.

The game's fonts (Oxanium, Orbitron) have no Greek Δ, so it would be drawn as an empty box. FallbackFont draws
just those characters with the system monospace font (Consolas on Windows, which has them), and everything else
with the game's font. It has the same methods the callers of pygame fonts use."""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import pygame

FALLBACK_FONTS = 'consolas,dejavusansmono,couriernew,monospace'
# A code point no font has: its rendering is the "missing glyph" box, to compare other glyphs against.
_NOT_A_CHARACTER = '\U0010FFFF'
_WHITE = (255, 255, 255)


class FallbackFont:
    def __init__(self, primary: pygame.font.Font, size: int, bold: bool = False) -> None:
        self.primary: pygame.font.Font = primary
        self.fallback: pygame.font.Font = pygame.font.SysFont(FALLBACK_FONTS, size, bold=bold)
        self._missing: Dict[str, bool] = {}
        self._missing_box: bytes = self._pixels(self.primary.render(_NOT_A_CHARACTER, True, _WHITE))

    @staticmethod
    def _pixels(surface: pygame.Surface) -> bytes:
        return pygame.image.tobytes(surface, 'RGBA')

    def _is_missing(self, character: str) -> bool:
        """Whether the primary font draws `character` as the missing-glyph box. Checked once per character."""
        if character.isascii():
            return False
        if character not in self._missing:
            glyph = self._pixels(self.primary.render(character, True, _WHITE))
            self._missing[character] = glyph == self._missing_box
        return self._missing[character]

    def _runs(self, text: str) -> List[Tuple[str, pygame.font.Font]]:
        """`text` split into runs, each with the font that draws it."""
        runs: List[Tuple[str, pygame.font.Font]] = []
        for character in text:
            font = self.fallback if self._is_missing(character) else self.primary
            if runs and runs[-1][1] is font:
                runs[-1] = (runs[-1][0] + character, font)
            else:
                runs.append((character, font))
        return runs

    def render(self, text: str, antialias: bool, color: Tuple[int, int, int],
               background: Optional[Tuple[int, int, int]] = None) -> pygame.Surface:
        if all(font is self.primary for _, font in self._runs(text)):
            return self.primary.render(text, antialias, color, background)
        parts = [(font.render(run, antialias, color), font) for run, font in self._runs(text)]
        ascent = max(font.get_ascent() for _, font in parts)
        width = sum(part.get_width() for part, _ in parts)
        height = max(ascent - font.get_ascent() + part.get_height() for part, font in parts)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        if background is not None:
            surface.fill(background)
        x = 0
        for part, font in parts:
            surface.blit(part, (x, ascent - font.get_ascent()))
            x += part.get_width()
        return surface

    def size(self, text: str) -> Tuple[int, int]:
        widths = [font.size(run)[0] for run, font in self._runs(text)]
        return sum(widths), self.primary.get_height()

    def get_height(self) -> int:
        return self.primary.get_height()

    def get_linesize(self) -> int:
        return self.primary.get_linesize()

    def get_ascent(self) -> int:
        return self.primary.get_ascent()

    def set_bold(self, bold: bool) -> None:
        self.primary.set_bold(bold)
        self.fallback.set_bold(bold)
