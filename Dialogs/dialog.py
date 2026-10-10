"""Base class for modal dialogs, drawn above the game or alone in a window."""

from __future__ import annotations
from typing import Any, Optional, Tuple
import pygame

DialogResult = Tuple[str, Any]  # (action, value), e.g. ('new', 1) or ('exit', None)

BACKDROP_COLOR = (0, 0, 0, 150)
PANEL_BORDER_COLOR = (100, 150, 255)


class Dialog:
    """A modal dialog with a fixed logical size.

    A dialog never runs its own loop. The host feeds it events through handle_event
    (mouse positions already in dialog coordinates, see localize_event) and shows what
    draw renders: alone in a window (run_in_window) or as an overlay above the frozen
    game (compose_overlay). While a dialog is open the host must not advance game time.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width: int = width
        self.height: int = height

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the dialog onto `surface`, which has the dialog's logical size."""
        raise NotImplementedError

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Handle one event; return a result when the dialog is finished, else None."""
        raise NotImplementedError

    def panel_layout(self, window_size: Tuple[int, int]) -> Tuple[pygame.Rect, float]:
        """Where the panel sits in a window of `window_size`: centred, scaled down (never up) to fit."""
        window_width, window_height = window_size
        scale = min(1.0, window_width / self.width, window_height / self.height)
        rect = pygame.Rect(0, 0, int(self.width * scale), int(self.height * scale))
        rect.center = (window_width // 2, window_height // 2)
        return rect, scale

    def localize_event(self, event: pygame.event.Event, window_size: Tuple[int, int]) -> pygame.event.Event:
        """Copy of `event` with a mouse position mapped from window to dialog coordinates."""
        if not hasattr(event, 'pos'):
            return event
        rect, scale = self.panel_layout(window_size)
        x, y = event.pos
        attributes = {**event.dict, 'pos': (int((x - rect.left) / scale), int((y - rect.top) / scale))}
        return pygame.event.Event(event.type, attributes)

    def render_panel(self, window_size: Tuple[int, int]) -> Tuple[pygame.Surface, pygame.Rect]:
        """The drawn panel, already scaled for the window, and the rectangle where it goes."""
        rect, scale = self.panel_layout(window_size)
        panel = pygame.Surface((self.width, self.height))
        self.draw(panel)
        if scale != 1.0:
            panel = pygame.transform.smoothscale(panel, rect.size)
        return panel, rect

    def compose_overlay(self, window_size: Tuple[int, int]) -> pygame.Surface:
        """Window-sized RGBA layer to draw above the game: dimmed backdrop and the centred panel."""
        layer = pygame.Surface(window_size, pygame.SRCALPHA)
        layer.fill(BACKDROP_COLOR)
        panel, rect = self.render_panel(window_size)
        layer.blit(panel, rect)
        pygame.draw.rect(layer, PANEL_BORDER_COLOR, rect.inflate(4, 4), 2)
        return layer


def run_in_window(dialog: Dialog, surface: pygame.Surface) -> Optional[DialogResult]:
    """Run `dialog` alone on `surface` (the startup window) until it returns a result."""
    clock = pygame.time.Clock()
    while True:
        window_size = surface.get_size()
        for event in pygame.event.get():
            result = dialog.handle_event(dialog.localize_event(event, window_size))
            if result is not None:
                return result
        panel, rect = dialog.render_panel(window_size)
        surface.fill((0, 0, 0))
        surface.blit(panel, rect)
        pygame.display.flip()
        clock.tick(60)
