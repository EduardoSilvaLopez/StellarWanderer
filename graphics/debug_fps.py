"""Frames per second, for debugging: plain text in the top-left corner of the window, with no box or other element.

Shown in source runs only (SHOW_FPS). A packaged build (PyInstaller sets sys.frozen) has it off, so nothing is counted
and nothing is drawn there.
"""

from __future__ import annotations
import sys
import time
from typing import Any
import pygame
from .constants import ACCENT, DEBUG_FPS_WINDOW_SECONDS, DEBUG_FPS_POSITION

SHOW_FPS: bool = not getattr(sys, 'frozen', False)


class DebugFps:
    """Counts the frames drawn and gives their rate over the last DEBUG_FPS_WINDOW_SECONDS."""

    _frames: int = 0
    _since: float = 0.0
    _fps: float = 0.0

    @staticmethod
    def tick() -> None:
        """Call once per frame."""
        if not SHOW_FPS:
            return
        now = time.perf_counter()
        if DebugFps._frames == 0:
            DebugFps._since = now
        DebugFps._frames += 1
        elapsed = now - DebugFps._since
        if elapsed >= DEBUG_FPS_WINDOW_SECONDS:
            DebugFps._fps = DebugFps._frames / elapsed
            DebugFps._frames = 0

    @staticmethod
    def draw(surface: pygame.Surface, font: Any) -> None:
        """The rate, as text on `surface`, in the top-left corner. Nothing when SHOW_FPS is off."""
        if not SHOW_FPS:
            return
        text = font.render(f'{DebugFps._fps:.0f} FPS', True, ACCENT)
        surface.blit(text, DEBUG_FPS_POSITION)
