"""Message dialog: a short textured, futuristic-looking message with one button."""

from __future__ import annotations
from typing import List, Optional, Tuple
import os
import pygame

from .dialog import Dialog, DialogResult
from .dialog_fonts import body_font, title_font
from .messages import Message, load_message

TEXTURE_PATH = os.path.join(os.path.dirname(__file__), '..', 'Resources', 'textures', 'dialog_background.png')

ACCENT = (94, 234, 212)        # same as the cockpit accent
ACCENT_DIM = (34, 92, 92)
TEXT_COLOR = (205, 232, 232)
BUTTON_FILL = (16, 52, 56)
BUTTON_FILL_HOVER = (26, 84, 88)


class MessageDialog(Dialog):
    """Title, wrapped and scrollable text, and one button, loaded from messages.toml by key.

    Results: ('close', None) on Esc, Enter, Space or a click on the button; ('exit', None) when the
    window is closed."""

    WIDTH = 800
    HEIGHT = 600
    MARGIN = 38
    TITLE_SIZE = 26
    BODY_SIZE = 19
    LINE_SPACING = 1.35
    PARAGRAPH_GAP = 12
    BUTTON_SIZE = (220, 40)

    def __init__(self, key: str, values: Optional[dict] = None, message: Optional[Message] = None) -> None:
        super().__init__(self.WIDTH, self.HEIGHT)
        self.message: Message = message if message is not None else load_message(key, values)

        self.button_rect = pygame.Rect(0, 0, *self.BUTTON_SIZE)
        self.button_rect.midbottom = (self.WIDTH // 2, self.HEIGHT - self.MARGIN + 6)
        self.button_hover: bool = False

        self._title_surface: pygame.Surface = self._render_title()
        self.divider_y: int = self.MARGIN - 4 + self._title_surface.get_height() + 12
        self.text_rect = pygame.Rect(
            self.MARGIN, self.divider_y + 16,
            self.WIDTH - 2 * self.MARGIN, self.button_rect.top - 18 - (self.divider_y + 16)
        )
        self.lines: List[Tuple[str, int]] = []   # (text, y offset inside the text area)
        self.content_height: int = 0
        self._layout_text()
        self.scroll: int = 0                     # pixels scrolled down

        self._texture: Optional[pygame.Surface] = None
        self._texture_loaded: bool = False

    # ---- layout ----

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
    def max_scroll(self) -> int:
        return max(0, self.content_height - self.text_rect.height)

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self.max_scroll, self.scroll + pixels))

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

        font = body_font(self.BODY_SIZE)
        previous_clip = surface.get_clip()
        surface.set_clip(self.text_rect)
        for text, y in self.lines:
            line_y = self.text_rect.top + y - self.scroll
            if line_y + font.get_linesize() < self.text_rect.top or line_y > self.text_rect.bottom:
                continue
            surface.blit(font.render(text, True, TEXT_COLOR), (self.text_rect.left, line_y))
        surface.set_clip(previous_clip)

        self._draw_scroll_indicators(surface)
        self._draw_button(surface)

    def _draw_frame(self, surface: pygame.Surface) -> None:
        outer = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        pygame.draw.rect(surface, ACCENT_DIM, outer, 1)
        pygame.draw.rect(surface, ACCENT, outer.inflate(-10, -10), 1)
        bracket = 22  # heavier corner marks
        for (cx, cy, sx, sy) in ((5, 5, 1, 1), (self.WIDTH - 6, 5, -1, 1),
                                 (5, self.HEIGHT - 6, 1, -1), (self.WIDTH - 6, self.HEIGHT - 6, -1, -1)):
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx + sx * bracket, cy), 3)
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx, cy + sy * bracket), 3)

    def _draw_scroll_indicators(self, surface: pygame.Surface) -> None:
        if self.max_scroll <= 0:
            return
        x = self.text_rect.right + 12
        if self.scroll > 0:
            top = self.text_rect.top + 4
            pygame.draw.polygon(surface, ACCENT, [(x, top), (x - 7, top + 10), (x + 7, top + 10)])
        if self.scroll < self.max_scroll:
            bottom = self.text_rect.bottom - 4
            pygame.draw.polygon(surface, ACCENT, [(x, bottom), (x - 7, bottom - 10), (x + 7, bottom - 10)])

    def _draw_button(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, BUTTON_FILL_HOVER if self.button_hover else BUTTON_FILL, self.button_rect)
        pygame.draw.rect(surface, ACCENT, self.button_rect, 2)
        label = title_font(16).render(self.message.button.upper(), True, ACCENT)
        surface.blit(label, label.get_rect(center=self.button_rect.center))

    # ---- events ----

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Handle one event (mouse positions in dialog coordinates)."""
        if event.type == pygame.QUIT:
            return ('exit', None)

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return ('close', None)
            line = int(body_font(self.BODY_SIZE).get_linesize() * self.LINE_SPACING)
            if event.key == pygame.K_UP:
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
                self.scroll = self.max_scroll

        elif event.type == pygame.MOUSEWHEEL:
            line = int(body_font(self.BODY_SIZE).get_linesize() * self.LINE_SPACING)
            self._scroll_by(-event.y * line * 3)

        elif event.type == pygame.MOUSEMOTION:
            self.button_hover = self.button_rect.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button_rect.collidepoint(event.pos):
                return ('close', None)

        return None
