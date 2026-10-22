"""The chat of the outpost screen (the Chat option): the conversation tags on the left, the chat log in the middle (see
galaxies/people/chat_log.py for what it holds). Both are lists in the rectangle `place` gives, with a scroll bar beside
them, scrolled with the wheel, Page Up and Page Down, and the scroll bar.

ChatView draws the lines as bubbles, one colour per speaker: the pilot's on the right, the person's on the left, in the
person's colour (chat_log.py, speaker_colour). A marked word is in the accent colour. The replies are bubbles of the
pilot's colour under the lines, without numbers; choosing one calls `on_reply` with its index. The view follows the
newest line, until the player scrolls up.

ChatTags draws the tags in the order given, one row each; a click on a tag calls `on_tag` with it, but only while the
tags are `active` (a person is selected and no reply is open, see the outpost screen)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Sequence, Tuple
import pygame

from common import audio
from galaxies.people.chat_log import PLAYER, ChatLog, Word
from .dialog_fonts import body_font
from .message_dialog import ACCENT, ACCENT_DIM, TEXT_COLOR
from .mission_board_dialog import DIM_COLOR, PAGE_KEYS, ROW_FILL, SCROLL_BAR_GAP, SCROLL_STEP
from .scroll_bar import ScrollBar

if TYPE_CHECKING:
    from galaxies.people.person import Person

BODY_SIZE = 16
BUBBLE_PAD = 10
BUBBLE_GAP = 10
BUBBLE_MAX_FRACTION = 0.8  # the most a bubble takes, of the view's width
BUBBLE_FILL = (14, 24, 30, 230)
PLAYER_COLOUR = (236, 226, 190)
NPC_PALETTE = ((120, 200, 255), (255, 170, 110), (170, 235, 140), (230, 140, 220), (255, 226, 120), (140, 220, 220))

# A block of the list: (surface, y in the content, x in the text area, what a click on it does, or None).
Block = Tuple[pygame.Surface, int, int, Any]


def speaker_colour(person: Person) -> Tuple[int, int, int]:
    """The colour of a person in the chat: one of NPC_PALETTE, by the person's seed, so it stays the same."""
    return NPC_PALETTE[person.seed % len(NPC_PALETTE)]


def _line_width(words: Sequence[Word], font: pygame.font.Font) -> int:
    """The width of `words` on one line, with a space between them."""
    if not words:
        return 0
    return sum(font.size(word)[0] for word, _ in words) + font.size(' ')[0] * (len(words) - 1)


def _wrap_words(words: Sequence[Word], font: pygame.font.Font, width: int) -> List[List[Word]]:
    """The words in lines that fit `width`, greedily; a word longer than that stays whole."""
    space = font.size(' ')[0]
    lines: List[List[Word]] = []
    line: List[Word] = []
    used = 0
    for word in words:
        size = font.size(word[0])[0]
        if line and used + space + size > width:
            lines.append(line)
            line, used = [], 0
        used += space if line else 0
        line.append(word)
        used += size
    if line:
        lines.append(line)
    return lines


class _ScrolledList:
    """A list of blocks in `text_rect`, with the scroll bar beside it. A subclass says what a click on a block does
    (`_pressed`). `follow` keeps the view on the bottom: it is set again when the list is scrolled to the bottom."""

    def __init__(self) -> None:
        self.text_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)  # set by place
        self.scroll_bar: ScrollBar = ScrollBar(pygame.Rect(0, 0, ScrollBar.MIN_WIDTH, 0), ACCENT)
        self.scroll: int = 0
        self.content_height: int = 0
        self.follow: bool = True
        self._hits: List[Tuple[pygame.Rect, Any]] = []  # where the clickable blocks were last drawn, and their payload

    def place(self, rect: pygame.Rect) -> None:
        """Puts the blocks in `rect`, and the scroll bar SCROLL_BAR_GAP to its right: the rect leaves room for it."""
        self.text_rect = rect
        self.scroll_bar.track = pygame.Rect(rect.right + SCROLL_BAR_GAP, rect.top, ScrollBar.MIN_WIDTH, rect.height)

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.text_rect.height)

    def _scroll_to(self, value: int) -> None:
        self.scroll = max(0, min(self._max_scroll(), value))
        self.follow = self.scroll >= self._max_scroll()

    def _paint(self, surface: pygame.Surface, blocks: List[Block]) -> None:
        """Draws `blocks` in the text rectangle, clipped to it, from the bottom while following, and the scroll bar."""
        self.content_height = max((y + block.get_height() for block, y, _, _ in blocks), default=0)
        self.scroll = self._max_scroll() if self.follow else min(self.scroll, self._max_scroll())
        self._hits = []
        previous_clip = surface.get_clip()
        surface.set_clip(self.text_rect)
        for block, y, x, payload in blocks:
            top = self.text_rect.top + y - self.scroll
            left = self.text_rect.left + x
            if top + block.get_height() >= self.text_rect.top and top <= self.text_rect.bottom:
                surface.blit(block, (left, top))
            if payload is not None:
                self._hits.append((pygame.Rect(left, top, block.get_width(), block.get_height()), payload))
        surface.set_clip(previous_clip)
        self.scroll_bar.draw(surface, self.scroll, self._max_scroll(), self.text_rect.height)

    def _pressed(self, payload: Any) -> bool:
        """What a click on a block with `payload` does. True if it was used."""
        return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        moved = self.scroll_bar.handle_event(event, self.scroll, self._max_scroll(), self.text_rect.height)
        if moved is not None:
            self._scroll_to(moved)
            return True
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_to(self.scroll - event.y * SCROLL_STEP)
            return True
        if event.type == pygame.KEYDOWN and event.key in PAGE_KEYS:
            self._scroll_to(self.scroll + PAGE_KEYS[event.key] * self.text_rect.height)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.text_rect.collidepoint(event.pos):
            for rect, payload in self._hits:
                if rect.collidepoint(event.pos):
                    return self._pressed(payload)
        return False


class ChatView(_ScrolledList):
    """The lines of a ChatLog as bubbles, and its open replies under them."""

    def __init__(self, on_reply: Callable[[int], None]) -> None:
        super().__init__()
        self.on_reply: Callable[[int], None] = on_reply

    def _bubble(self, words: Sequence[Word], colour: Tuple[int, int, int], width: int,
                border: int = 1) -> pygame.Surface:
        """A bubble of `words` in `colour`, at most BUBBLE_MAX_FRACTION of `width` wide: the marked words in the accent
        colour, the others in `colour`."""
        font = body_font(BODY_SIZE)
        inner = int(width * BUBBLE_MAX_FRACTION) - 2 * BUBBLE_PAD
        lines = _wrap_words(words, font, inner)
        text_width = max((_line_width(line, font) for line in lines), default=0)
        bubble = pygame.Surface((text_width + 2 * BUBBLE_PAD, len(lines) * font.get_linesize() + 2 * BUBBLE_PAD),
                                pygame.SRCALPHA)
        bubble.fill(BUBBLE_FILL)
        pygame.draw.rect(bubble, colour, bubble.get_rect(), border)
        y = BUBBLE_PAD
        for line in lines:
            x = BUBBLE_PAD
            for index, (word, marked) in enumerate(line):
                if index:
                    x += font.size(' ')[0]
                rendered = font.render(word, True, ACCENT if marked else colour)
                bubble.blit(rendered, (x, y))
                x += rendered.get_width()
            y += font.get_linesize()
        return bubble

    def _reply(self, label: str, width: int, focused: bool) -> pygame.Surface:
        """An open reply, a bubble in the pilot's colour; a focused one has an inner ring."""
        words = [(word, False) for word in label.split()]
        bubble = self._bubble(words, PLAYER_COLOUR, width, border=2 if focused else 1)
        if focused:
            pygame.draw.rect(bubble, ACCENT, bubble.get_rect().inflate(-8, -8), 1)
        return bubble

    def draw(self, surface: pygame.Surface, log: Optional[ChatLog], focus: Optional[int] = None) -> None:
        """The log's lines and its open replies; `focus` is the index of the reply the keyboard is on, if any."""
        blocks: List[Block] = []
        width = self.text_rect.width
        y = 0
        if log is not None:
            colour = speaker_colour(log.person)
            for line in log.lines:
                if line.speaker == PLAYER:
                    bubble = self._bubble(line.words, PLAYER_COLOUR, width)
                    x = width - bubble.get_width()
                else:
                    bubble = self._bubble(line.words, colour, width)
                    x = 0
                blocks.append((bubble, y, x, None))
                y += bubble.get_height() + BUBBLE_GAP
            for index, label in enumerate(log.replies or []):
                bubble = self._reply(label, width, focus == index)
                blocks.append((bubble, y, width - bubble.get_width(), index))
                y += bubble.get_height() + BUBBLE_GAP
        self._paint(surface, blocks)

    def _pressed(self, payload: Any) -> bool:
        audio.play('ui_click')
        self.on_reply(payload)
        return True


class ChatTags(_ScrolledList):
    """The conversation tags, in the order given, one row each. Only while `active` does a click start a
    conversation."""

    def __init__(self, on_tag: Callable[[str], None]) -> None:
        super().__init__()
        self.on_tag: Callable[[str], None] = on_tag
        self.active: bool = False

    def draw(self, surface: pygame.Surface, tags: Sequence[str], active: bool, focus: Optional[int] = None) -> None:
        """The rows of `tags`; `focus` is the index of the row the keyboard is on, if any."""
        self.active = active
        font = body_font(BODY_SIZE)
        row_height = font.get_linesize() + 2 * BUBBLE_PAD
        width = self.text_rect.width
        blocks: List[Block] = []
        y = 0
        for index, tag in enumerate(tags):
            row = pygame.Surface((width, row_height), pygame.SRCALPHA)
            row.fill(ROW_FILL)
            focused = focus == index
            pygame.draw.rect(row, ACCENT if focused else ACCENT_DIM, row.get_rect(), 2 if focused else 1)
            caption = font.render(tag, True, TEXT_COLOR if active else DIM_COLOR)
            row.blit(caption, (BUBBLE_PAD, row_height // 2 - caption.get_height() // 2))
            blocks.append((row, y, 0, ('tag', tag)))
            y += row_height + BUBBLE_GAP
        self._paint(surface, blocks)

    def _pressed(self, payload: Any) -> bool:
        if not self.active:
            return False
        audio.play('ui_click')
        self.on_tag(payload[1])
        return True
