"""The instructions screen: the controls and how the game works, read-only and scrollable.

The text is INSTRUCTIONS below: a list of sections, each a heading and its paragraphs. Each paragraph is wrapped to the
box. Edit the text there; the layout does not depend on it.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import pygame

from .dialog import Dialog, DialogResult
from .dialog_fonts import body_font, title_font
from .message_dialog import MessageDialog

INSTRUCTIONS: List[Tuple[str, List[str]]] = [
    ("Flying", [
        "A / D: thrust left / right. W / X: thrust forward / back. Numpad 8 / 2: climb / descend (while bound to a world).",
        "Numpad 4 / 6: turn left / right. Numpad 8 / 2 (while unbound): nose up / down. E / Q (while unbound): roll right / left.",
        "S: brake on all axes, and stop all turning.",
        "Numpad + / -: faster / slower time. Turning is off above normal speed, so the ship holds its attitude.",
    ]),
    ("Worlds", [
        "Fly close to a planet or moon to bind to its surface. Fly away from it to be free again.",
        "While bound, the map in the middle shows the world: the mouse wheel zooms when the pointer is over it, and a left-button drag moves the view. Releasing the button centres it on the ship again.",
        "The scanner shows what is in the crosshair. Hold Space to fire the laser at it.",
    ]),
    ("Mining", [
        "M: place an ore mine where the ship is. It needs a mine in the cargo hold, and there must be no rock nearby.",
    ]),
    ("Keeping alive", [
        "Maintenance and energy run down over time, and so do the air, water and food in the cargo hold.",
        "Outposts restore them. Watch the bars and the cargo: a critical warning means go to an outpost now.",
    ]),
    ("Game", [
        "Esc: open the menu, where you can resume, start a new game, load or save. F5: save now, under the default name. F6: load the last save.",
    ]),
]

BODY_SIZE = 18
HEADING_SIZE = 22
TITLE_SIZE = 44
TITLE_COLOUR = (100, 200, 255)
HEADING_COLOUR = (150, 200, 255)
TEXT_COLOUR = (200, 200, 200)
BOX_COLOUR = (30, 30, 50)
BOX_EDGE_COLOUR = (80, 80, 120)
SCROLL_STEP = 30  # pixels per wheel notch or arrow key
PAGE_KEYS = {pygame.K_PAGEUP: -1, pygame.K_PAGEDOWN: 1}


class InstructionsDialog(Dialog):
    """The instructions screen, opened from the starting dialog. Result: ('back', None)."""

    WIDTH = 800
    HEIGHT = 600
    MARGIN = 24
    TITLE_TOP = 12
    BOX_GAP = 24  # between the bottom of the title's letters and the text box
    BACK_HEIGHT = 52  # the bottom row for the Back button

    def __init__(self) -> None:
        super().__init__(self.WIDTH, self.HEIGHT)
        title_ink = title_font(TITLE_SIZE).render("Instructions", True, TITLE_COLOUR).get_bounding_rect()
        box_top = self.TITLE_TOP + title_ink.bottom + self.BOX_GAP
        self.box_rect = pygame.Rect(self.MARGIN, box_top, self.WIDTH - 2 * self.MARGIN,
                                    self.HEIGHT - box_top - self.BACK_HEIGHT)
        self.back_rect = pygame.Rect(self.WIDTH // 2 - 100, self.HEIGHT - self.BACK_HEIGHT + 12, 200, 32)
        self.scroll: int = 0  # pixels the text is moved up
        self._lines: List[Tuple[str, pygame.Surface]] = []  # (kind, rendered line)
        self._text_height: int = 0
        self._build_lines()

    def _build_lines(self) -> None:
        """Wrap and render the whole text once, as the box is fixed in size."""
        body = body_font(BODY_SIZE)
        heading = body_font(HEADING_SIZE)
        width = self.box_rect.width - 60  # the text's left padding, and room for the scrollbar on the right
        lines: List[Tuple[str, pygame.Surface]] = []
        for title, paragraphs in INSTRUCTIONS:
            lines.append(('gap', pygame.Surface((1, body.get_linesize() // 2))))
            lines.append(('heading', heading.render(title, True, HEADING_COLOUR)))
            for paragraph in paragraphs:
                for line in MessageDialog.wrap('- ' + paragraph, body, width):
                    lines.append(('text', body.render(line, True, TEXT_COLOUR)))
        self._lines = lines
        self._text_height = sum(surface.get_height() + 4 for _, surface in lines)

    def _max_scroll(self) -> int:
        return max(0, self._text_height - (self.box_rect.height - 16))

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll + pixels))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((20, 20, 30))

        title = title_font(TITLE_SIZE).render("Instructions", True, TITLE_COLOUR)
        surface.blit(title, title.get_rect(topleft=(self.MARGIN, self.TITLE_TOP)))

        pygame.draw.rect(surface, BOX_COLOUR, self.box_rect)
        pygame.draw.rect(surface, BOX_EDGE_COLOUR, self.box_rect, 2)
        previous_clip = surface.get_clip()
        surface.set_clip(self.box_rect.inflate(-4, -4))
        y = self.box_rect.top + 8 - self.scroll
        x = self.box_rect.left + 14
        for kind, line in self._lines:
            if kind != 'gap':
                surface.blit(line, (x, y))
            y += line.get_height() + 4
        surface.set_clip(previous_clip)

        if self._max_scroll() > 0:
            track = pygame.Rect(self.box_rect.right - 16, self.box_rect.top + 6, 8, self.box_rect.height - 12)
            pygame.draw.rect(surface, (60, 60, 80), track)
            thumb_height = max(20, track.height * self.box_rect.height // max(1, self._text_height))
            thumb_top = track.top + (track.height - thumb_height) * self.scroll // self._max_scroll()
            pygame.draw.rect(surface, (100, 150, 200), (track.left, thumb_top, track.width, thumb_height))

        pygame.draw.rect(surface, (110, 50, 50), self.back_rect)
        pygame.draw.rect(surface, (190, 110, 110), self.back_rect, 2)
        back = body_font(20).render("Back", True, (255, 255, 255))
        surface.blit(back, back.get_rect(center=self.back_rect.center))

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if event.type == pygame.QUIT:
            return ('exit', None)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.back_rect.collidepoint(event.pos):
            return ('back', None)
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * SCROLL_STEP)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                return ('back', None)
            if event.key == pygame.K_UP:
                self._scroll_by(-SCROLL_STEP)
            elif event.key == pygame.K_DOWN:
                self._scroll_by(SCROLL_STEP)
            elif event.key in PAGE_KEYS:
                self._scroll_by(PAGE_KEYS[event.key] * self.box_rect.height)
            elif event.key == pygame.K_HOME:
                self.scroll = 0
            elif event.key == pygame.K_END:
                self.scroll = self._max_scroll()
        return None
