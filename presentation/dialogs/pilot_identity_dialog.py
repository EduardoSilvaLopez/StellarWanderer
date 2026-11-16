"""The pilot's identity dialog: names, date of birth, three traits, and the pronoun with the physiology and attraction
it sets. Asked at the start of a new game."""

from __future__ import annotations
import calendar
from typing import List, Optional, Tuple
import pygame

from galaxies.people.person import Person
from galaxies.people.pilot_identity import PilotIdentity
from .dialog import DialogResult
from .dialog_fonts import body_font
from .form_controls import NumberField, Slider, TextField, draw_box
from .message_dialog import ACCENT, MessageDialog, TEXT_COLOR
from .messages import Message

NAME_MAX_LENGTH = 20
# The dates of birth run from the first to the last date given here (year, month, day), inclusive.
EARLIEST_DATE_OF_BIRTH = (640, 1, 1)
LATEST_DATE_OF_BIRTH = (680, 1, 1)
DEFAULT_DATE_OF_BIRTH = (650, 1, 1)
TRAIT_TOTAL = 150  # beauty + perception + education
PRONOUNS = (Person.Pronoun.SHE, Person.Pronoun.THEY, Person.Pronoun.HE)
# What a pronoun sets: (physiology, attracted to). Both run from extreme female (0) to extreme male (100).
PRONOUN_SETTINGS = {
    Person.Pronoun.SHE: (20, 80),
    Person.Pronoun.THEY: (50, 50),
    Person.Pronoun.HE: (80, 20),
}
PRONOUN_MARKS = (20, 50, 80)  # the presets, drawn as ticks on the physiology and attraction tracks


class PilotIdentityDialog(MessageDialog):
    """Asks for the pilot's first name, surname, date of birth, beauty, perception, education, pronoun, physiology,
    attraction and sexuality. The left column holds the date and the three traits, the right one the pronoun and the
    three sliders that follow it.

    Results: ('done', PilotIdentity) when Continue is pressed (or Enter in the surname box) with both names and a
    pronoun given; ('exit', None) when the window is closed. Esc and a right-click do nothing: the pilot must say who
    they are.

    The three traits always add up to TRAIT_TOTAL: a slider moves the other two by half as much, the other way, and it
    stops where one of them would leave 0 to 100. A pronoun sets physiology and attraction (PRONOUN_SETTINGS), which the
    pilot can still change. The mouse does everything. The keys: Tab and Enter move on, Up and Down change a number or
    a slider, Left and Right move a slider; a number box is typed in too."""

    WIDTH = 960
    HEIGHT = 730
    COLUMN_WIDTH = 420
    COLUMN_GAP = 44
    LABEL_WIDTH = 120
    BOX_HEIGHT = 36
    HEADING_GAP = 26  # between a row and the heading of the next one
    CAPTION_GAP = 30  # between a heading and the caption of the boxes below it
    SLIDER_BLOCK = 104  # from one slider's title to the next one's
    TITLE_GAP = 30  # from a slider's title to its track
    TRACK_HEIGHT = 30
    PRONOUN_GAP = 10

    def __init__(self) -> None:
        super().__init__(Message(title='WHO ARE YOU?', text='', buttons=['Continue']))
        body = body_font(self.BODY_SIZE)
        left = self.text_rect.left
        right = left + self.COLUMN_WIDTH + self.COLUMN_GAP
        self.intro = self.wrap("Define yourself. This information is private.", body, self.text_rect.width)

        names_y = self.text_rect.top + len(self.intro) * self._line_height + 14
        heading_y = names_y + self.BOX_HEIGHT + self.HEADING_GAP
        caption_y = heading_y + self.CAPTION_GAP
        boxes_y = caption_y + self.HEADING_GAP
        sliders_y = boxes_y + self.BOX_HEIGHT + 34
        text_y = (self.BOX_HEIGHT - body.get_linesize()) // 2  # a label, centred on a box

        # the names share one row: first name, then surname, each with its label before it
        surname_label_x = left + self.LABEL_WIDTH + 300 + 30
        surname_x = surname_label_x + 100
        self.first_name_box = TextField(pygame.Rect(left + self.LABEL_WIDTH, names_y, 300, self.BOX_HEIGHT),
                                        NAME_MAX_LENGTH)
        self.surname_box = TextField(pygame.Rect(surname_x, names_y, right + self.COLUMN_WIDTH - surname_x,
                                                 self.BOX_HEIGHT), NAME_MAX_LENGTH)
        _, month, day = DEFAULT_DATE_OF_BIRTH
        self.month_box = NumberField(pygame.Rect(left, boxes_y, 120, self.BOX_HEIGHT), range(1, 13), 2, month)
        self.day_box = NumberField(pygame.Rect(left + 140, boxes_y, 90, self.BOX_HEIGHT), range(1, 32), 2, day)
        years = range(EARLIEST_DATE_OF_BIRTH[0], LATEST_DATE_OF_BIRTH[0] + 1)
        self.year_box = NumberField(pygame.Rect(left + 250, boxes_y, 110, self.BOX_HEIGHT), years, 3,
                                    DEFAULT_DATE_OF_BIRTH[0])

        pronoun_width = (self.COLUMN_WIDTH - 2 * self.PRONOUN_GAP) // len(PRONOUNS)
        self.pronoun_rects = {
            pronoun: pygame.Rect(right + index * (pronoun_width + self.PRONOUN_GAP), boxes_y, pronoun_width,
                                 self.BOX_HEIGHT)
            for index, pronoun in enumerate(PRONOUNS)
        }
        self.pronoun: Optional[Person.Pronoun] = None

        def track(x: int, row: int, marks: Tuple[int, ...] = ()) -> Slider:
            rect = pygame.Rect(x, sliders_y + row * self.SLIDER_BLOCK + self.TITLE_GAP, self.COLUMN_WIDTH,
                               self.TRACK_HEIGHT)
            return Slider(rect, 50.0, marks)

        self.beauty = track(left, 0)
        self.perception = track(left, 1)
        self.education = track(left, 2)
        self.physiology = track(right, 0, PRONOUN_MARKS)
        self.attracted_to = track(right, 1, PRONOUN_MARKS)
        self.sexuality = track(right, 2)
        self._traits: List[Slider] = [self.beauty, self.perception, self.education]
        # title, low end, high end, slider: the ends are the words at the track's two sides
        self._slider_specs: List[Tuple[str, str, str, Slider]] = [
            ("Beauty", "Low", "High", self.beauty),
            ("Perception", "Low", "High", self.perception),
            ("Education", "Low", "High", self.education),
            ("Physiology", "Female", "Male", self.physiology),
            ("Attracted to", "Female", "Male", self.attracted_to),
            ("Sexuality", "Low", "High", self.sexuality),
        ]

        self._labels: List[Tuple[str, int, int]] = [
            ("First name", left, names_y + text_y),
            ("Surname", surname_label_x, names_y + text_y),
            ("D.O.B.", left, heading_y),
            ("Month", left, caption_y),
            ("Day", left + 140, caption_y),
            ("Year", left + 250, caption_y),
            ("Pronoun", right, heading_y),
        ]
        # Tab order: the names, the date, the traits, the pronoun, then the sliders of the right column
        self._controls: List[object] = [
            self.first_name_box, self.surname_box, self.month_box, self.day_box, self.year_box,
            self.beauty, self.perception, self.education,
            *PRONOUNS,
            self.physiology, self.attracted_to, self.sexuality,
        ]
        self._control_index: int = 0
        self._drag: Optional[Slider] = None  # the slider the mouse is dragging
        self._mouse: Tuple[int, int] = (-1, -1)
        self._sync_days()

    @property
    def is_valid(self) -> bool:
        return (bool(self.first_name_box.text.strip()) and bool(self.surname_box.text.strip())
                and self.pronoun is not None)

    # region Rules
    def _sync_days(self) -> None:
        """The months and days the chosen year allows, leap years included, and a date past the latest one is brought
        back to it: the latest year has only its first month, and that month only its first day."""
        year = self.year_box.value
        self.month_box.set_options(range(1, (LATEST_DATE_OF_BIRTH[1] if year == LATEST_DATE_OF_BIRTH[0] else 12) + 1))
        month = self.month_box.value
        if (year, month) == LATEST_DATE_OF_BIRTH[:2]:
            days = LATEST_DATE_OF_BIRTH[2]
        else:
            days = calendar.monthrange(year, month)[1]
        self.day_box.set_options(range(1, days + 1))

    def _move_traits(self, slider: Slider, target: float) -> None:
        """Moves a trait to `target`, and the other two by half of the change the other way. The change is held to what
        keeps all three within 0 to 100, so that the total stays TRAIT_TOTAL."""
        others = [trait for trait in self._traits if trait is not slider]
        value = slider.value
        lowest_change = max(-value, 2 * max(other.value for other in others) - 200)
        highest_change = min(100 - value, 2 * min(other.value for other in others))
        change = min(max(target - value, lowest_change), highest_change)
        slider.value = value + change
        for other in others:
            other.value -= change / 2

    def _set_slider(self, slider: Slider, target: float) -> None:
        target = min(max(target, 0.0), 100.0)
        if slider in self._traits:
            self._move_traits(slider, target)
        else:
            slider.value = target

    def _choose_pronoun(self, pronoun: Person.Pronoun) -> None:
        self.pronoun = pronoun
        physiology, attracted_to = PRONOUN_SETTINGS[pronoun]
        self.physiology.value, self.attracted_to.value = float(physiology), float(attracted_to)
    # endregion

    # region Focus and typing
    def _clamp_date(self) -> None:
        """Brings the date of birth within the earliest and the latest one, and its day within its month."""
        year, month, day = min(max((self.year_box.value, self.month_box.value, self.day_box.value),
                                   EARLIEST_DATE_OF_BIRTH), LATEST_DATE_OF_BIRTH)
        self.year_box.value = year
        self.month_box.value = month
        self.day_box.value = min(day, calendar.monthrange(year, month)[1])
        self._sync_days()

    def _commit_all(self) -> None:
        """Ends the typing in the number boxes and closes their lists: what was typed is kept. The date is brought
        back into range only when the year was typed, since it comes last in the order of the boxes (Month, Day, Year):
        a day typed before the year is not cut down to the year that is about to change."""
        year_typed = self.year_box.typed is not None
        for number in (self.month_box, self.day_box, self.year_box):
            number.commit()
            number.is_open = False
        if year_typed:
            self._clamp_date()
        self._sync_days()

    def _focus_on(self, index: int) -> None:
        self._commit_all()
        self._control_index = index

    def _move_focus(self, step: int) -> None:
        self._focus_on((self._control_index + step) % len(self._controls))

    def _open_list(self) -> Optional[NumberField]:
        for control in self._controls:
            if isinstance(control, NumberField) and control.is_open:
                return control
        return None

    def _rect_of(self, control: object) -> pygame.Rect:
        if isinstance(control, Person.Pronoun):
            return self.pronoun_rects[control]
        return control.rect  # type: ignore[attr-defined]  # every other control has a rect

    def _key(self, event: pygame.event.Event) -> Optional[DialogResult]:
        control = self._controls[self._control_index]
        if event.key == pygame.K_TAB:
            self._move_focus(-1 if event.mod & pygame.KMOD_SHIFT else 1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if control is self.surname_box:
                return self._done()
            if isinstance(control, Person.Pronoun):
                self._choose_pronoun(control)
            self._move_focus(1)
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            step = 1 if event.key in (pygame.K_RIGHT, pygame.K_UP) else -1
            if isinstance(control, Slider):
                self._set_slider(control, control.value + step)
            elif isinstance(control, NumberField) and event.key in (pygame.K_UP, pygame.K_DOWN):
                control.step(step)
                self._clamp_date()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._move_focus(step)
        elif isinstance(control, (TextField, NumberField)):
            control.type(event)
        self._sync_days()
        return None

    def _press(self, pos: Tuple[int, int]) -> bool:
        """A left press. True when the dialog takes it; False when it is on no control (Continue may take it)."""
        open_list = self._open_list()
        if open_list is not None:  # a press on the list picks its option; any other press only closes the list
            value = open_list.value_at_row(pos)
            open_list.is_open = False
            if value is not None:
                open_list.choose(value)
                self._clamp_date()
            return True
        for index, control in enumerate(self._controls):
            if not self._rect_of(control).collidepoint(pos):
                continue
            self._focus_on(index)
            if isinstance(control, NumberField) and control.arrow_rect.collidepoint(pos):
                control.toggle_list()
            elif isinstance(control, Slider):
                self._drag = control
                self._set_slider(control, control.value_at(pos[0]))
            elif isinstance(control, Person.Pronoun):
                self._choose_pronoun(control)
            return True
        self._commit_all()
        return False

    def _wheel(self, rows: int) -> None:
        open_list = self._open_list()
        if open_list is not None and open_list.list_rect.collidepoint(self._mouse):
            open_list.scroll_list(-rows)

    def _done(self) -> Optional[DialogResult]:
        self._commit_all()
        self._clamp_date()
        if not self.is_valid:
            return None
        return ('done', PilotIdentity(
            first_name=self.first_name_box.text.strip(),
            surname=self.surname_box.text.strip(),
            date_of_birth=(self.year_box.value, self.month_box.value, self.day_box.value),
            beauty=self.beauty.value,
            perception=self.perception.value,
            education=self.education.value,
            pronoun=self.pronoun,
            physiology=self.physiology.value,
            attracted_to=self.attracted_to.value,
            sexuality=self.sexuality.value,
        ))
    # endregion

    # region Drawing
    def _draw_content(self, surface: pygame.Surface) -> None:
        font = body_font(self.BODY_SIZE)
        for index, line in enumerate(self.intro):
            surface.blit(font.render(line, True, TEXT_COLOR),
                         (self.text_rect.left, self.text_rect.top + index * self._line_height))
        for text, x, y in self._labels:
            surface.blit(font.render(text, True, TEXT_COLOR), (x, y))

        focused = self._controls[self._control_index]
        self.first_name_box.draw(surface, font, focused is self.first_name_box)
        self.surname_box.draw(surface, font, focused is self.surname_box)
        for number in (self.month_box, self.day_box, self.year_box):
            number.draw(surface, font, focused is number)
        for pronoun, rect in self.pronoun_rects.items():
            chosen = pronoun is self.pronoun
            draw_box(surface, rect, chosen or focused is pronoun)
            label = font.render(pronoun.name.capitalize(), True, ACCENT if chosen else TEXT_COLOR)
            surface.blit(label, label.get_rect(center=rect.center))
        for title, low, high, slider in self._slider_specs:
            surface.blit(font.render(title, True, TEXT_COLOR), (slider.rect.left, slider.rect.top - self.TITLE_GAP))
            ends_y = slider.rect.bottom + 4
            surface.blit(font.render(low, True, TEXT_COLOR), (slider.rect.left, ends_y))
            high_text = font.render(high, True, TEXT_COLOR)
            surface.blit(high_text, (slider.rect.right - high_text.get_width(), ends_y))
            slider.draw(surface, focused is slider)
        for number in (self.month_box, self.day_box, self.year_box):  # the open lists over everything else
            number.draw_list(surface, font)
    # endregion

    # region Events
    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Mouse positions are in dialog coordinates. The keys go to the focused control; the Continue button is the
        base dialog's."""
        if event.type == pygame.KEYDOWN:
            return self._key(event)
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            if self._drag is not None:
                self._set_slider(self._drag, self._drag.value_at(event.pos[0]))
                return None
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = None
            return None
        elif event.type == pygame.MOUSEWHEEL:
            self._wheel(event.y)
            return None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._press(event.pos):
            return None

        result = super().handle_event(event)
        if result is not None and result[0] == 'close':
            return self._done() if result[1] == 0 else None  # Esc and right-click are no answer
        return result
    # endregion
