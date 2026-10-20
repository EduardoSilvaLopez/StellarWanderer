"""Message dialog: a short textured, futuristic-looking message with one or more buttons."""

from __future__ import annotations
from typing import List, Optional, Tuple
import pygame

from .dialog import Dialog, DialogResult, is_cancel
from .dialog_fonts import BODY_FONT_SIZE, body_font, title_font
from .messages import Message
from .scroll_bar import ScrollBar
from common.paths import resource_path

TEXTURE_PATH = resource_path('textures', 'dialog_background.png')

ACCENT = (94, 234, 212)  # same as the cockpit accent
ACCENT_DIM = (34, 92, 92)
TEXT_COLOR = (205, 232, 232)
BUTTON_FILL = (16, 52, 56)
BUTTON_FILL_HOVER = (26, 84, 88)


class MessageDialog(Dialog):
    """Title, wrapped and scrollable text, and one or more buttons, from the Message it is given.

    Results: ('close', index) when a button is pressed, index being its position in the message's
    buttons (0 is the first); ('close', None) on Esc or a right-click; ('exit', None) when the window is closed.
    Enter or Space press the focused button (the first at the start); Tab, Left and Right move the focus,
    and the mouse moves it too.

    Look: a textured panel (common/resources/textures/dialog_background.png), Orbitron title and Oxanium body at size 20
    (common/resources/fonts/, SIL OFL, licence files next to them). Every label must go through FontCache or dialog_fonts,
    not pygame.font directly. Button labels use the body font, like the text, and wrap onto several lines when they
    are long. The buttons are stacked, one above the other, each as wide as the text area: the first at the top. A scroll
    bar (a thumb only, no box) sits in the right margin beside the text when the text does not fit; the mouse drags it,
    and a click above or below it pages (see ScrollBar)."""

    WIDTH = 800
    HEIGHT = 600
    MARGIN = 38
    TITLE_SIZE = 26
    BODY_SIZE = BODY_FONT_SIZE
    LINE_SPACING = 1.35
    PARAGRAPH_GAP = 12
    BUTTON_HEIGHT = 40
    BUTTON_PADDING = 20  # each side of the label
    BUTTON_PADDING_Y = 4  # above and below the label's lines
    BUTTON_GAP = 14
    SCROLLBAR_GAP = 10  # between the text area and the scroll bar
    SCROLLBAR_WIDTH = ScrollBar.MIN_WIDTH
    SCROLLBAR_MIN_THUMB = 24

    def __init__(self, message: Message) -> None:
        super().__init__(self.WIDTH, self.HEIGHT)
        self.message: Message = message
        self.OPEN_SOUND = message.open_sound

        self.button_rects: List[pygame.Rect] = self._layout_buttons()
        self.hover: Optional[int] = None  # the button under the mouse
        self.focus: int = 0  # the button Enter or Space press

        self._title_surface: pygame.Surface = self._render_title()
        self.divider_y: int = self.MARGIN - 4 + self._title_surface.get_height() + 12
        buttons_top = min(rect.top for rect in self.button_rects)
        self.text_rect = pygame.Rect(
            self.MARGIN, self.divider_y + 16,
            self.WIDTH - 2 * self.MARGIN, buttons_top - 18 - (self.divider_y + 16)
        )
        self.lines: List[Tuple[str, int]] = []  # (text, y offset inside the text area)
        self.content_height: int = 0
        self._layout_text()
        self.scroll: int = 0  # pixels scrolled down
        self.scroll_bar = ScrollBar(
            pygame.Rect(self.text_rect.right + self.SCROLLBAR_GAP, self.text_rect.top, self.SCROLLBAR_WIDTH, self.text_rect.height),
            ACCENT, min_thumb=self.SCROLLBAR_MIN_THUMB,
        )

        self._texture: Optional[pygame.Surface] = None
        self._texture_loaded: bool = False

    # ---- layout ----

    def _button_lines(self, label: str) -> List[str]:
        """The label, uppercase and wrapped to the button's width less its padding, as lines to draw."""
        return self.wrap(label.upper(), body_font(self.BODY_SIZE), self._button_width - 2 * self.BUTTON_PADDING)

    @property
    def _button_width(self) -> int:
        return self.WIDTH - 2 * self.MARGIN

    def _layout_buttons(self) -> List[pygame.Rect]:
        """One rectangle per button, stacked and each as wide as the text area; the first at the top, the last at the
        bottom. A button grows taller only when its label wraps."""
        font = body_font(self.BODY_SIZE)
        self._button_texts: List[List[str]] = [self._button_lines(label) for label in self.message.buttons]
        heights = [
            max(self.BUTTON_HEIGHT, font.get_linesize() * len(lines) + 2 * self.BUTTON_PADDING_Y)
            for lines in self._button_texts
        ]
        rects: List[pygame.Rect] = []
        y = self.HEIGHT - self.MARGIN + 6  # the bottom edge of the last button
        for height in reversed(heights):
            rects.insert(0, pygame.Rect(self.MARGIN, y - height, self._button_width, height))
            y -= height + self.BUTTON_GAP
        return rects

    def _render_title(self) -> pygame.Surface:
        """The title, with the font stepped down until it fits the width."""
        max_width = self.WIDTH - 2 * self.MARGIN
        size = self.TITLE_SIZE
        surface = title_font(size).render(self.message.title, True, ACCENT)
        while surface.get_width() > max_width and size > 12:
            size -= 1
            surface = title_font(size).render(self.message.title, True, ACCENT)
        return surface

    @staticmethod
    def wrap(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        """Break `text` into lines no wider than `max_width` (a word wider than that is split)."""
        lines: List[str] = []
        current = ''
        for word in text.split(' '):
            candidate = word if not current else current + ' ' + word
            if font.size(candidate)[0] <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = ''
            while font.size(word)[0] > max_width:  # an over-long word: split it by characters
                cut = len(word)
                while cut > 1 and font.size(word[:cut])[0] > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        if current:
            lines.append(current)
        return lines

    def _layout_text(self) -> None:
        font = body_font(self.BODY_SIZE)
        line_height = int(font.get_linesize() * self.LINE_SPACING / 1.0)
        y = 0
        self.lines = []
        for index, paragraph in enumerate(self.message.paragraphs):
            if index > 0:
                y += self.PARAGRAPH_GAP
            for line in self.wrap(paragraph, font, self.text_rect.width):
                self.lines.append((line, y))
                y += line_height
        self.content_height = y

    @property
    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.text_rect.height)

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self._max_scroll, self.scroll + pixels))

    # ---- drawing ----

    def _background(self) -> Optional[pygame.Surface]:
        if not self._texture_loaded:
            self._texture_loaded = True
            try:
                self._texture = pygame.image.load(TEXTURE_PATH).convert()
                if self._texture.get_size() != (self.WIDTH, self.HEIGHT):
                    self._texture = pygame.transform.smoothscale(self._texture, (self.WIDTH, self.HEIGHT))
            except (FileNotFoundError, pygame.error):
                self._texture = None
        return self._texture

    def draw(self, surface: pygame.Surface) -> None:
        texture = self._background()
        if texture is not None:
            surface.blit(texture, (0, 0))
        else:
            surface.fill((12, 20, 32))
        tint = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        tint.fill((0, 0, 0, 90))  # keeps the text readable whatever the texture is
        surface.blit(tint, (0, 0))

        self._draw_frame(surface)

        surface.blit(self._title_surface, (self.MARGIN, self.MARGIN - 4))
        pygame.draw.line(surface, ACCENT, (self.MARGIN, self.divider_y), (self.WIDTH - self.MARGIN, self.divider_y), 2)
        pygame.draw.line(surface, ACCENT_DIM, (self.MARGIN, self.divider_y + 3), (self.WIDTH - self.MARGIN, self.divider_y + 3), 1)

        previous_clip = surface.get_clip()
        surface.set_clip(self.text_rect)
        self._draw_content(surface)
        surface.set_clip(previous_clip)

        self.scroll_bar.draw(surface, self.scroll, self._max_scroll, self.text_rect.height)
        self._draw_buttons(surface)

    def _draw_content(self, surface: pygame.Surface) -> None:
        """The scrolled content, in the text area (the clip is already set to it). A subclass with other content (see
        knowledge_dialogs.py) replaces this and _layout_text, and keeps the rest."""
        font = body_font(self.BODY_SIZE)
        for text, y in self.lines:
            line_y = self.text_rect.top + y - self.scroll
            if line_y + font.get_linesize() < self.text_rect.top or line_y > self.text_rect.bottom:
                continue
            surface.blit(font.render(text, True, TEXT_COLOR), (self.text_rect.left, line_y))

    def _draw_frame(self, surface: pygame.Surface) -> None:
        outer = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        pygame.draw.rect(surface, ACCENT_DIM, outer, 1)
        pygame.draw.rect(surface, ACCENT, outer.inflate(-10, -10), 1)
        bracket = 22  # heavier corner marks
        for (cx, cy, sx, sy) in ((5, 5, 1, 1), (self.WIDTH - 6, 5, -1, 1),
                                 (5, self.HEIGHT - 6, 1, -1), (self.WIDTH - 6, self.HEIGHT - 6, -1, -1)):
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx + sx * bracket, cy), 3)
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx, cy + sy * bracket), 3)

    def _draw_buttons(self, surface: pygame.Surface) -> None:
        font = body_font(self.BODY_SIZE)
        several = len(self.button_rects) > 1
        for index, rect in enumerate(self.button_rects):
            # With several buttons the focused one is lit, so the player sees which Enter will press.
            lit = index == self.hover or (several and index == self.focus)
            pygame.draw.rect(surface, BUTTON_FILL_HOVER if lit else BUTTON_FILL, rect)
            pygame.draw.rect(surface, ACCENT, rect, 2)
            lines = self._button_texts[index]
            top = rect.centery - font.get_linesize() * len(lines) // 2
            for line_index, line in enumerate(lines):
                label = font.render(line, True, ACCENT)
                surface.blit(label, label.get_rect(midtop=(rect.centerx, top + line_index * font.get_linesize())))

    def _button_at(self, position: Tuple[int, int]) -> Optional[int]:
        return next((index for index, rect in enumerate(self.button_rects) if rect.collidepoint(position)), None)

    # ---- events ----

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Handle one event (mouse positions in dialog coordinates)."""
        if event.type == pygame.QUIT:
            return ('exit', None)

        moved = self.scroll_bar.handle_event(event, self.scroll, self._max_scroll, self.text_rect.height)
        if moved is not None:
            self.scroll = moved
            return None

        if is_cancel(event):
            return ('close', None)

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return ('close', self.focus)
            line = int(body_font(self.BODY_SIZE).get_linesize() * self.LINE_SPACING)
            count = len(self.button_rects)
            if event.key == pygame.K_TAB:
                step = -1 if event.mod & pygame.KMOD_SHIFT else 1
                self.focus = (self.focus + step) % count
            elif event.key == pygame.K_LEFT:
                self.focus = (self.focus - 1) % count
            elif event.key == pygame.K_RIGHT:
                self.focus = (self.focus + 1) % count
            elif event.key == pygame.K_UP:
                self._scroll_by(-line)
            elif event.key == pygame.K_DOWN:
                self._scroll_by(line)
            elif event.key == pygame.K_PAGEUP:
                self._scroll_by(-self.text_rect.height)
            elif event.key == pygame.K_PAGEDOWN:
                self._scroll_by(self.text_rect.height)
            elif event.key == pygame.K_HOME:
                self.scroll = 0
            elif event.key == pygame.K_END:
                self.scroll = self._max_scroll

        elif event.type == pygame.MOUSEWHEEL:
            line = int(body_font(self.BODY_SIZE).get_linesize() * self.LINE_SPACING)
            self._scroll_by(-event.y * line * 3)

        elif event.type == pygame.MOUSEMOTION:
            self.hover = self._button_at(event.pos)
            if self.hover is not None:
                self.focus = self.hover

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pressed = self._button_at(event.pos)
            if pressed is not None:
                return ('close', pressed)

        return None
