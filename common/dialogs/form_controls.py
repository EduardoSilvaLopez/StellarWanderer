"""The controls of a form dialog: a text box, a number box with a list of its values, and a slider from 0 to 100.

They draw themselves and hold their own value. The dialog decides which one has the focus, and what a change means
(the rules between the values are the dialog's, not the control's)."""

from __future__ import annotations
from typing import Optional, Sequence, Tuple
import pygame

from .message_dialog import ACCENT, ACCENT_DIM, BUTTON_FILL, BUTTON_FILL_HOVER, TEXT_COLOR

CARET_BLINK_MS = 500
DIGITS = '0123456789'


def draw_box(surface: pygame.Surface, rect: pygame.Rect, active: bool) -> None:
    pygame.draw.rect(surface, BUTTON_FILL_HOVER if active else BUTTON_FILL, rect)
    pygame.draw.rect(surface, ACCENT if active else ACCENT_DIM, rect, 2)


def _draw_text_and_caret(surface: pygame.Surface, rect: pygame.Rect, text: pygame.Surface, active: bool) -> None:
    """The text at the left of its box, and the caret after it while the box has the focus (it blinks)."""
    surface.blit(text, (rect.x + 10, rect.y + (rect.height - text.get_height()) // 2))
    if active and (pygame.time.get_ticks() // CARET_BLINK_MS) % 2 == 0:
        caret_x = rect.x + 12 + text.get_width()
        pygame.draw.line(surface, TEXT_COLOR, (caret_x, rect.y + 7), (caret_x, rect.bottom - 8), 2)


class TextField:
    """A box of text, typed in while it has the focus."""

    def __init__(self, rect: pygame.Rect, max_length: int) -> None:
        self.rect: pygame.Rect = rect
        self.max_length: int = max_length
        self.text: str = ''

    def type(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
            self.text += event.unicode

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, active: bool) -> None:
        draw_box(surface, self.rect, active)
        _draw_text_and_caret(surface, self.rect, font.render(self.text, True, TEXT_COLOR), active)


class NumberField:
    """A whole number in a box. It is typed in (at most `digits` digits) or picked from a list of the values it can
    take, opened by the arrow at the box's right. Its values are `options`, which the dialog may change: the value is
    kept within them. A typed number takes effect when the typing ends (commit)."""

    ROW_HEIGHT = 30
    VISIBLE_ROWS = 6
    ARROW_WIDTH = 26

    def __init__(self, rect: pygame.Rect, options: range, digits: int, value: int) -> None:
        self.rect: pygame.Rect = rect
        self.options: range = options  # the values the list offers; the dialog may narrow them
        self.limits: range = options  # the values a typed number can take, whatever the list offers
        self.digits: int = digits
        self.value: int = value
        self.typed: Optional[str] = None  # the digits being typed, None while the box shows the value
        self.is_open: bool = False
        self.first_row: int = 0  # the index of the first option the list shows

    @property
    def arrow_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.right - self.ARROW_WIDTH, self.rect.top, self.ARROW_WIDTH, self.rect.height)

    @property
    def list_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.left, self.rect.bottom, self.rect.width,
                           min(self.VISIBLE_ROWS, len(self.options)) * self.ROW_HEIGHT)

    def clamp(self, value: int) -> int:
        return min(max(value, self.options[0]), self.options[-1])

    def set_options(self, options: range) -> None:
        """The list's values. The value is left as it is: the dialog brings the whole date back to what is allowed."""
        self.options = options

    def choose(self, value: int) -> None:
        self.value = self.clamp(value)
        self.typed = None

    def commit(self) -> None:
        """Ends the typing: the number typed is kept, within the limits. An empty box gives back the value."""
        if self.typed is not None:
            if self.typed.isdigit():
                self.value = min(max(int(self.typed), self.limits[0]), self.limits[-1])
            self.typed = None

    def step(self, delta: int) -> None:
        self.commit()
        self.choose(self.value + delta)

    def type(self, event: pygame.event.Event) -> None:
        """A key typed into the box: Backspace, or a digit. Other keys are no typing."""
        if event.key == pygame.K_BACKSPACE:
            self.typed = '' if self.typed is None else self.typed[:-1]
        elif len(event.unicode) == 1 and event.unicode in DIGITS:
            typed = '' if self.typed is None else self.typed
            if len(typed) < self.digits:
                self.typed = typed + event.unicode

    def toggle_list(self) -> None:
        self.is_open = not self.is_open
        index = self.options.index(self.value)
        self.first_row = min(max(index - self.VISIBLE_ROWS // 2, 0), max(0, len(self.options) - self.VISIBLE_ROWS))

    def scroll_list(self, rows: int) -> None:
        self.first_row = min(max(self.first_row + rows, 0), max(0, len(self.options) - self.VISIBLE_ROWS))

    def value_at_row(self, pos: Tuple[int, int]) -> Optional[int]:
        """The option of the list under `pos`, None when the list is not there."""
        rect = self.list_rect
        if not self.is_open or not rect.collidepoint(pos):
            return None
        return self.options[self.first_row + (pos[1] - rect.top) // self.ROW_HEIGHT]

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, active: bool) -> None:
        draw_box(surface, self.rect, active or self.is_open)
        shown = self.typed if self.typed is not None else str(self.value)
        _draw_text_and_caret(surface, self.rect, font.render(shown, True, TEXT_COLOR), active)
        arrow = self.arrow_rect
        centre_x = arrow.centerx
        up, down = (4, -4) if self.is_open else (-4, 4)
        points = [(centre_x - 7, arrow.centery - up), (centre_x + 7, arrow.centery - up),
                  (centre_x, arrow.centery + down)]
        pygame.draw.polygon(surface, ACCENT, points)

    def draw_list(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.is_open:
            return
        rect = self.list_rect
        pygame.draw.rect(surface, BUTTON_FILL, rect)
        for row in range(rect.height // self.ROW_HEIGHT):
            value = self.options[self.first_row + row]
            row_rect = pygame.Rect(rect.left, rect.top + row * self.ROW_HEIGHT, rect.width, self.ROW_HEIGHT)
            chosen = value == self.value
            if chosen:
                pygame.draw.rect(surface, BUTTON_FILL_HOVER, row_rect)
            text = font.render(str(value), True, ACCENT if chosen else TEXT_COLOR)
            surface.blit(text, text.get_rect(center=row_rect.center))
        pygame.draw.rect(surface, ACCENT, rect, 2)


class Slider:
    """A value from 0 to 100 on a track: the mouse drags the thumb, the arrow keys move it by one. `marks` are the
    values shown as ticks above the track, for the presets of the dialog. `rect` is the track's zone, the thumb's width
    included at both ends."""

    THUMB_WIDTH = 14
    THUMB_HEIGHT = 26
    TRACK_THICKNESS = 4

    def __init__(self, rect: pygame.Rect, value: float, marks: Sequence[float] = ()) -> None:
        self.rect: pygame.Rect = rect
        self.value: float = value
        self.marks: Sequence[float] = marks

    def x_of(self, value: float) -> float:
        return self.rect.left + self.THUMB_WIDTH / 2 + value / 100 * (self.rect.width - self.THUMB_WIDTH)

    def value_at(self, x: float) -> float:
        """The value under the screen position `x`, clamped to 0 to 100."""
        fraction = (x - self.rect.left - self.THUMB_WIDTH / 2) / (self.rect.width - self.THUMB_WIDTH)
        return min(max(fraction * 100, 0.0), 100.0)

    def draw(self, surface: pygame.Surface, focused: bool) -> None:
        y = self.rect.centery
        thumb_x = self.x_of(self.value)
        start_x = self.x_of(0)
        end_x = self.x_of(100)
        pygame.draw.line(surface, ACCENT_DIM, (start_x, y), (end_x, y), self.TRACK_THICKNESS)
        pygame.draw.line(surface, ACCENT, (start_x, y), (thumb_x, y), self.TRACK_THICKNESS)
        for mark in self.marks:
            mark_x = round(self.x_of(mark))
            pygame.draw.line(surface, ACCENT, (mark_x, y - self.THUMB_HEIGHT // 2 - 6),
                             (mark_x, y - self.THUMB_HEIGHT // 2 - 1), 2)
        thumb = pygame.Rect(0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT)
        thumb.center = (round(thumb_x), y)
        pygame.draw.rect(surface, BUTTON_FILL_HOVER, thumb)
        pygame.draw.rect(surface, ACCENT, thumb, 2)
        if focused:
            pygame.draw.rect(surface, ACCENT, self.rect.inflate(8, 8), 1)
