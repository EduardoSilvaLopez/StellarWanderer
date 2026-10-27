"""The people of an outpost that can be chatted with now, as a list of cards (the Chat of the outpost screen, see
outpost_screen.py). Who is listed is Outpost.available_staff: not on vacation, not working and not resting.

Each card has the portrait on the left, then the name and the role, the last time the pilot met the person, and the
comment (read-only here, cut to COMMENT_LINES lines). A click selects a card: it is outlined with the accent colour, and
the selection goes when its person is no longer listed. The list is drawn in the rectangle `place` gives, with its
scroll bar beside it, and scrolls with the wheel, Page Up and Page Down, and the scroll bar.

A search box at the top of that rectangle shows only the cards whose person matches the text in what the card shows: the
name, the role, the last time met and the comment (Person.matches_search with SEARCH_LABELS, unlike the People dialog,
which searches all the fields). A person filtered out keeps the selection: only leaving the listing clears it. While the box
is focused, the typed text goes into it and the keys do not reach the options (see search_event)."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple
import pygame

from common import audio
from .dialog import is_cancel
from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, TEXT_COLOR, MessageDialog
from .mission_board_dialog import DIM_COLOR, LABEL_COLOR, PAGE_KEYS, ROW_FILL, SCROLL_BAR_GAP, SCROLL_STEP
from .scroll_bar import ScrollBar
from . import search_box

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.person import Person

BODY_SIZE = 16
HEADING_SIZE = 18
CARD_PAD = 12
CARD_GAP = 12
PORTRAIT_MAX_WIDTH = 120
PORTRAIT_RATIO = 1.5  # height over width, as the portraits (512 x 768)
PORTRAIT_FILL = (16, 52, 56)  # the box of a person whose portrait cannot be loaded
COMMENT_LINES = 3  # the most lines of a comment a card shows; a longer one ends with an ellipsis
EMPTY_TEXT = 'Nobody is available.'
SEARCH_GAP = 8  # between the search box and the first card
# The description fields a card shows, by label (see Person.description_fields): the search looks only at these.
SEARCH_LABELS = ('Role', 'Last time met')


class StaffList:
    """The available people of `outpost`, one card each (see the module docstring)."""

    def __init__(self, outpost: Outpost) -> None:
        self.outpost: Outpost = outpost
        self.selected: Optional[Person] = None  # the card that is outlined; None for none
        self.persons: List[Person] = []  # the people shown at the last `available` call, in card order
        self.query: str = ''  # what the search box holds
        self.search_focused: bool = False  # whether the typed text goes into the search box
        self.search_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)  # set by place
        self.text_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)  # the cards, below the search box; set by place
        self.scroll_bar: ScrollBar = ScrollBar(pygame.Rect(0, 0, ScrollBar.MIN_WIDTH, 0), ACCENT)
        self.scroll: int = 0
        self.content_height: int = 0
        self._cards: List[Tuple[pygame.Rect, Person]] = []  # where each card was last drawn, and its person

    def place(self, rect: pygame.Rect) -> None:
        """Puts the search box at the top of `rect`, and the cards below it, with the scroll bar SCROLL_BAR_GAP to their
        right: the rect must leave room for it."""
        self.search_rect = pygame.Rect(rect.left, rect.top, rect.width, search_box.HEIGHT)
        self.text_rect = pygame.Rect(rect.left, self.search_rect.bottom + SEARCH_GAP, rect.width,
                                     rect.bottom - self.search_rect.bottom - SEARCH_GAP)
        self.scroll_bar.track = pygame.Rect(self.text_rect.right + SCROLL_BAR_GAP, self.text_rect.top,
                                            ScrollBar.MIN_WIDTH, self.text_rect.height)

    def available(self) -> List[Person]:
        """The people shown now, in card order: those listed (Outpost.available_staff) that match the search. The
        selection goes when its person is no longer listed, not when the search leaves them out."""
        import game_environment as gem  # local: the game's environment, not needed by the rest of this module
        listed = self.outpost.available_staff(gem.current_environment.date_time)
        if self.selected not in listed:
            self.selected = None
        self.persons = [person for person in listed if person.matches_search(self.query, SEARCH_LABELS)]
        return self.persons

    def set_search_focus(self, focused: bool) -> None:
        """Focuses the search box (the typed text goes into it) or lets go of it. The text input is on only while
        focused."""
        if focused == self.search_focused:
            return
        self.search_focused = focused
        if focused:
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()

    def search_event(self, event: pygame.event.Event) -> bool:
        """The search box's events: a click on it focuses it, and a click elsewhere, or Esc, lets go of it. While it is
        focused, the typed text edits the search and Enter and the space do not press anything: True when the event was
        used so. Other events, and a click on a card, go on to the list (False)."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            inside = self.search_rect.collidepoint(event.pos)
            self.set_search_focus(inside)
            return inside
        if not self.search_focused:
            return False
        if is_cancel(event):
            self.set_search_focus(False)
            return False
        query = search_box.edit(self.query, event)
        if query is not None:
            self.query = query
            self.scroll = 0
            return True
        return search_box.swallows(event)

    def select_at(self, index: int) -> None:
        """Selects the card `index` of the last `available` call (the keyboard's way to a card)."""
        if 0 <= index < len(self.persons):
            audio.play('ui_click')
            self.selected = self.persons[index]

    # region Cards
    @staticmethod
    def _wrapped(text: str, font: pygame.font.Font, width: int) -> List[str]:
        """`text` in lines that fit `width`, each of its own lines (an empty line stays one)."""
        return [line for paragraph in text.split('\n') for line in (MessageDialog.wrap(paragraph, font, width) or [''])]

    @staticmethod
    def _comment_lines(text: str, width: int) -> List[str]:
        """The comment's lines, at most COMMENT_LINES: a longer one ends with an ellipsis that fits `width`."""
        font = body_font(BODY_SIZE)
        lines = StaffList._wrapped(text, font, width)
        if len(lines) <= COMMENT_LINES:
            return lines
        lines = lines[:COMMENT_LINES]
        last = lines[-1]
        while last and font.size(last + '…')[0] > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + '…'
        return lines

    def _card(self, person: Person, width: int, selected: bool, focused: bool) -> pygame.Surface:
        """The card of `person`, `width` wide: the portrait, then the name, the role, the last time met and the comment.
        A selected card is outlined in the accent colour; a focused one (the keyboard's) has an inner ring."""
        body = body_font(BODY_SIZE)
        heading = title_font(HEADING_SIZE)
        portrait_width = max(60, min(PORTRAIT_MAX_WIDTH, width // 4))
        portrait_size = (portrait_width, int(portrait_width * PORTRAIT_RATIO))
        text_x = CARD_PAD + portrait_width + CARD_PAD
        text_width = width - text_x - CARD_PAD

        name_lines = self._wrapped(person.get_full_name(), heading, text_width)
        role_lines = self._wrapped(person.role.name, body, text_width)
        met_lines = self._wrapped(f"Last time met: {person.last_time_met_text()}", body, text_width)
        comment_lines = self._comment_lines(person.comment, text_width) if person.comment else []
        text_height = (len(name_lines) * heading.get_linesize() + 4
                       + (len(role_lines) + len(met_lines) + len(comment_lines)) * body.get_linesize()
                       + (CARD_PAD // 2 if comment_lines else 0))
        height = max(portrait_size[1], text_height) + 2 * CARD_PAD

        card = pygame.Surface((width, height), pygame.SRCALPHA)
        card.fill(ROW_FILL)
        pygame.draw.rect(card, ACCENT if selected else ACCENT_DIM, card.get_rect(), 2 if selected else 1)
        if focused:
            pygame.draw.rect(card, ACCENT, card.get_rect().inflate(-8, -8), 1)

        portrait = pygame.Rect(CARD_PAD, CARD_PAD, *portrait_size)
        if person.icon is not None:
            card.blit(pygame.transform.smoothscale(person.icon, portrait_size), portrait)
        else:
            pygame.draw.rect(card, PORTRAIT_FILL, portrait)
        pygame.draw.rect(card, ACCENT, portrait, 2)

        y = CARD_PAD
        for line in name_lines:
            card.blit(heading.render(line, True, ACCENT), (text_x, y))
            y += heading.get_linesize()
        y += 4
        for line in role_lines:
            card.blit(body.render(line, True, TEXT_COLOR), (text_x, y))
            y += body.get_linesize()
        for line in met_lines:
            card.blit(body.render(line, True, LABEL_COLOR), (text_x, y))
            y += body.get_linesize()
        if comment_lines:
            y += CARD_PAD // 2
            for line in comment_lines:
                card.blit(body.render(line, True, DIM_COLOR), (text_x, y))
                y += body.get_linesize()
        return card
    # endregion

    # region Drawing and events
    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.text_rect.height)

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll + pixels))

    def draw(self, surface: pygame.Surface, focus: Optional[int] = None) -> None:
        """The search box and the cards in the rectangle of `place`. `focus` is the index of the card the keyboard is on,
        if any."""
        search_box.draw(surface, self.search_rect, self.query, self.search_focused)
        cards = [(self._card(person, self.text_rect.width, person is self.selected, index == focus), person)
                 for index, person in enumerate(self.available())]
        self.content_height = sum(card.get_height() + CARD_GAP for card, _ in cards) - CARD_GAP if cards else 0
        self.scroll = min(self.scroll, self._max_scroll())
        self._cards = []
        previous_clip = surface.get_clip()
        surface.set_clip(self.text_rect)
        if not cards:
            text = f'Nobody matches "{self.query.strip()}".' if self.query.strip() else EMPTY_TEXT
            surface.blit(body_font(BODY_SIZE).render(text, True, DIM_COLOR), self.text_rect.topleft)
        y = 0
        for card, person in cards:
            top = self.text_rect.top + y - self.scroll
            if top + card.get_height() >= self.text_rect.top and top <= self.text_rect.bottom:
                surface.blit(card, (self.text_rect.left, top))
            self._cards.append((pygame.Rect(self.text_rect.left, top, card.get_width(), card.get_height()), person))
            y += card.get_height() + CARD_GAP
        surface.set_clip(previous_clip)
        self.scroll_bar.draw(surface, self.scroll, self._max_scroll(), self.text_rect.height)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """The scroll bar, the wheel, Page Up and Page Down, and a click on a card (which selects it). True if the event
        was the list's, and was used."""
        moved = self.scroll_bar.handle_event(event, self.scroll, self._max_scroll(), self.text_rect.height)
        if moved is not None:
            self.scroll = moved
            return True
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * SCROLL_STEP)
            return True
        if event.type == pygame.KEYDOWN and event.key in PAGE_KEYS:
            self._scroll_by(PAGE_KEYS[event.key] * self.text_rect.height)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.text_rect.collidepoint(event.pos):
            for rect, person in self._cards:
                if rect.collidepoint(event.pos):
                    audio.play('ui_click')
                    self.selected = person
                    return True
        return False
    # endregion
