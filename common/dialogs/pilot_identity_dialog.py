"""The pilot's identity dialog: first name, surname and gender, asked at the start of a new game."""

from __future__ import annotations
from typing import List, Optional
import pygame

from galaxies.people.person import Person
from .dialog import DialogResult
from .dialog_fonts import body_font
from .message_dialog import ACCENT, ACCENT_DIM, BUTTON_FILL, BUTTON_FILL_HOVER, MessageDialog, TEXT_COLOR
from .messages import Message

CARET_BLINK_MS = 500
NAME_MAX_LENGTH = 20


class PilotIdentityDialog(MessageDialog):
    """Asks for the pilot's first name, surname and gender, in the look of a message dialog.

    Results: ('done', (first_name, surname, gender)) when Continue is pressed (or Enter in the surname box) with both
    names filled in, gender being a Person.GenderGroup; ('exit', None) when the window is closed. Esc and a right-click
    do nothing: the pilot must say who they are. Click a box to type in it (Tab and Enter move on); the gender is a
    click on one of its two buttons."""

    FIELD_HEIGHT = 36
    FIELD_WIDTH = 360
    ROW_GAP = 22

    def __init__(self) -> None:
        super().__init__(Message(
            title='WHO ARE YOU, PILOT?',
            text='',
            buttons=['Continue'],
        ))
        self.first_name: str = ''
        self.surname: str = ''
        self.gender: Person.GenderGroup = Person.GenderGroup.MALE
        self.active: int = 0  # 0 the first name box, 1 the surname box

        left = self.text_rect.left
        self.intro = self.wrap(
            "The registry needs your name before you set off. Write it as it shall be remembered.",
            body_font(self.BODY_SIZE), self.text_rect.width)
        top = self.text_rect.top + len(self.intro) * self._line_height + 24
        label_width = 150
        self.field_rects: List[pygame.Rect] = []
        for row in range(2):
            y = top + row * (self.FIELD_HEIGHT + self.ROW_GAP)
            self.field_rects.append(pygame.Rect(left + label_width, y, self.FIELD_WIDTH, self.FIELD_HEIGHT))
        gender_y = top + 2 * (self.FIELD_HEIGHT + self.ROW_GAP)
        half = (self.FIELD_WIDTH - 10) // 2
        self.gender_rects = {
            Person.GenderGroup.MALE: pygame.Rect(left + label_width, gender_y, half, self.FIELD_HEIGHT),
            Person.GenderGroup.FEMALE: pygame.Rect(left + label_width + half + 10, gender_y, half, self.FIELD_HEIGHT),
        }
        self.labels = ['First name', 'Surname', 'Gender']
        self.label_ys = [rect.y for rect in self.field_rects] + [gender_y]

    @property
    def is_valid(self) -> bool:
        return bool(self.first_name.strip()) and bool(self.surname.strip())

    @property
    def _active_text(self) -> str:
        return self.surname if self.active else self.first_name

    def _set_active_text(self, text: str) -> None:
        if self.active:
            self.surname = text
        else:
            self.first_name = text

    def _done(self) -> Optional[DialogResult]:
        if not self.is_valid:
            return None
        return ('done', (self.first_name.strip(), self.surname.strip(), self.gender))

    # region Drawing
    def _draw_content(self, surface: pygame.Surface) -> None:
        font = body_font(self.BODY_SIZE)
        for index, line in enumerate(self.intro):
            surface.blit(font.render(line, True, TEXT_COLOR),
                         (self.text_rect.left, self.text_rect.top + index * self._line_height))
        for label, y in zip(self.labels, self.label_ys):
            text = font.render(label, True, TEXT_COLOR)
            surface.blit(text, (self.text_rect.left, y + (self.FIELD_HEIGHT - text.get_height()) // 2))
        for index, (rect, value) in enumerate(zip(self.field_rects, (self.first_name, self.surname))):
            active = index == self.active
            pygame.draw.rect(surface, BUTTON_FILL_HOVER if active else BUTTON_FILL, rect)
            pygame.draw.rect(surface, ACCENT if active else ACCENT_DIM, rect, 2)
            text = font.render(value, True, TEXT_COLOR)
            surface.blit(text, (rect.x + 10, rect.y + (rect.height - text.get_height()) // 2))
            if active and (pygame.time.get_ticks() // CARET_BLINK_MS) % 2 == 0:
                caret_x = rect.x + 12 + text.get_width()
                pygame.draw.line(surface, TEXT_COLOR, (caret_x, rect.y + 7), (caret_x, rect.bottom - 8), 2)
        for gender, rect in self.gender_rects.items():
            chosen = gender == self.gender
            pygame.draw.rect(surface, BUTTON_FILL_HOVER if chosen else BUTTON_FILL, rect)
            pygame.draw.rect(surface, ACCENT if chosen else ACCENT_DIM, rect, 2)
            text = font.render(gender.name.capitalize(), True, ACCENT if chosen else TEXT_COLOR)
            surface.blit(text, text.get_rect(center=rect.center))
    # endregion

    # region Events
    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Typing goes to the active box; the mouse picks a box or a gender; the Continue button needs both names."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.active = (self.active + 1) % 2
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.active == 0:
                    self.active = 1
                else:
                    return self._done()
            elif event.key == pygame.K_BACKSPACE:
                self._set_active_text(self._active_text[:-1])
            elif event.unicode and event.unicode.isprintable() and len(self._active_text) < NAME_MAX_LENGTH:
                self._set_active_text(self._active_text + event.unicode)
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self.field_rects):
                if rect.collidepoint(event.pos):
                    self.active = index
                    return None
            for gender, rect in self.gender_rects.items():
                if rect.collidepoint(event.pos):
                    self.gender = gender
                    return None

        result = super().handle_event(event)
        if result is not None and result[0] == 'close':
            return self._done() if result[1] == 0 else None  # Esc and right-click are no answer
        return result
    # endregion
