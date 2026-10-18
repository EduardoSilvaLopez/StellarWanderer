"""The mission board of an outpost, as a window (see galaxies/missions/mission_board.py for the rules).

Each mission is a row: its title, its deadline, what it asks and its reward, and on the right its own button: Accept for an
offer, Deliver for a mission the player has taken. The rows are listed under two headings, "Your missions" and "Available".
Esc leaves; there is no other button. The rows scroll with the wheel and the arrow keys."""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
import pygame

from common.paths import resource_path
from .dialog import Dialog, DialogResult
from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, BUTTON_FILL, TEXT_COLOR, MessageDialog

if TYPE_CHECKING:
    from galaxies.missions import Mission
    from galaxies.missions.mission_board import MissionBoard

TEXTURE_PATH = resource_path('textures', 'dialog_background.png')
LABEL_COLOR = (120, 175, 175)
DIM_COLOR = (110, 120, 120)
ROW_FILL = (14, 24, 30)
WIDTH = 800
HEIGHT = 600
MARGIN = 38
TITLE_SIZE = 26
BODY_SIZE = 16
HEADING_SIZE = 18
ROW_PAD = 12
ROW_GAP = 12
BUTTON_WIDTH = 130
BUTTON_HEIGHT = 36
SCROLL_STEP = 40
PAGE_KEYS = {pygame.K_PAGEUP: -1, pygame.K_PAGEDOWN: 1}

# One line of the list: (surface, gap above it, the button's rect inside the surface or None, what the button does).
Item = Tuple[pygame.Surface, int, Optional[pygame.Rect], Optional[Callable[[], None]]]


class MissionBoardDialog(Dialog):
    """Result: ('close', None) on Esc; ('exit', None) when the window closes."""

    def __init__(self, board: MissionBoard) -> None:
        super().__init__(WIDTH, HEIGHT)
        self.board: MissionBoard = board
        self.scroll: int = 0
        self.content_height: int = 0
        self._buttons: List[Tuple[pygame.Rect, Callable[[], None]]] = []  # where the buttons were last drawn
        self._texture: Optional[pygame.Surface] = None
        self._texture_loaded: bool = False

        size = TITLE_SIZE
        self._title = title_font(size).render(board.title, True, ACCENT)
        while self._title.get_width() > WIDTH - 2 * MARGIN and size > 12:
            size -= 1
            self._title = title_font(size).render(board.title, True, ACCENT)
        self._divider_y = MARGIN - 4 + self._title.get_height() + 12
        hint_top = HEIGHT - MARGIN
        self.text_rect = pygame.Rect(MARGIN, self._divider_y + 16, WIDTH - 2 * MARGIN, hint_top - 12 - (self._divider_y + 16))

    # ---- content ----

    def _items(self, width: int) -> List[Item]:
        """Every line of the list, top to bottom, for a text area `width` wide."""
        heading = title_font(HEADING_SIZE)
        items: List[Item] = []
        mine = self.board.mine()
        items.append((heading.render('Your missions', True, ACCENT), 0, None, None))
        if mine:
            for mission in mine:
                items.append(self._row(mission, 'Deliver', lambda m=mission: self._do(self.board.deliver, m), width))
        else:
            items.append((self._note('None.', width), 4, None, None))
        items.append((heading.render('Available', True, ACCENT), 22, None, None))
        if self.board.offers:
            for offer in list(self.board.offers):
                items.append(self._row(offer, 'Accept', lambda o=offer: self._do(self.board.accept, o), width))
        else:
            items.append((self._note('Nothing new.', width), 4, None, None))
        return items

    @staticmethod
    def _note(text: str, width: int) -> pygame.Surface:
        return body_font(BODY_SIZE).render(text, True, DIM_COLOR)

    @staticmethod
    def _row(mission: Mission, label: str, action: Callable[[], None], width: int) -> Item:
        """One mission: its text on the left, its button on the right, the row's background behind them."""
        from galaxies.missions.mission_board import DATE_FORMAT  # local: the board's module imports the player, which imports this package
        body = body_font(BODY_SIZE)
        text_width = width - 2 * ROW_PAD - BUTTON_WIDTH - ROW_GAP
        lines: List[pygame.Surface] = [title_font(HEADING_SIZE).render(mission.title(), True, ACCENT),
                                       body.render(f"Deadline: {mission.deadline.strftime(DATE_FORMAT)}", True, LABEL_COLOR)]
        lines += [body.render(line, True, TEXT_COLOR) for line in MessageDialog.wrap(mission.description(), body, text_width)]
        lines += [body.render(line, True, DIM_COLOR) for line in MessageDialog.wrap(mission.reward_text(), body, text_width)]

        text_height = sum(line.get_height() + 4 for line in lines)
        height = max(text_height + ROW_PAD, BUTTON_HEIGHT + 2 * ROW_PAD) + ROW_PAD
        row = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(row, ROW_FILL, row.get_rect())
        pygame.draw.rect(row, ACCENT_DIM, row.get_rect(), 1)
        y = ROW_PAD
        for line in lines:
            row.blit(line, (ROW_PAD, y))
            y += line.get_height() + 4

        button = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        button.midright = (width - ROW_PAD, height // 2)
        pygame.draw.rect(row, BUTTON_FILL, button)
        pygame.draw.rect(row, ACCENT, button, 2)
        caption = body_font(18).render(label, True, ACCENT)
        row.blit(caption, caption.get_rect(center=button.center))
        return row, ROW_GAP, button, action

    def _do(self, action: Callable[[Mission], None], mission: Mission) -> None:
        """The board changes; the buttons are the old ones until the next draw, so they are dropped now (no double press)."""
        action(mission)
        self._buttons = []

    # ---- drawing ----

    def _background(self) -> Optional[pygame.Surface]:
        if not self._texture_loaded:
            self._texture_loaded = True
            try:
                self._texture = pygame.image.load(TEXTURE_PATH).convert()
                if self._texture.get_size() != (WIDTH, HEIGHT):
                    self._texture = pygame.transform.smoothscale(self._texture, (WIDTH, HEIGHT))
            except (FileNotFoundError, pygame.error):
                self._texture = None
        return self._texture

    def draw(self, surface: pygame.Surface) -> None:
        texture = self._background()
        if texture is not None:
            surface.blit(texture, (0, 0))
        else:
            surface.fill((12, 20, 32))
        tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        tint.fill((0, 0, 0, 90))
        surface.blit(tint, (0, 0))
        self._draw_frame(surface)

        surface.blit(self._title, (MARGIN, MARGIN - 4))
        pygame.draw.line(surface, ACCENT, (MARGIN, self._divider_y), (WIDTH - MARGIN, self._divider_y), 2)

        self._buttons = []
        previous_clip = surface.get_clip()
        surface.set_clip(self.text_rect)
        y = 0
        for block, gap, button, action in self._items(self.text_rect.width):
            y += gap
            top = self.text_rect.top + y - self.scroll
            if top + block.get_height() >= self.text_rect.top and top <= self.text_rect.bottom:
                surface.blit(block, (self.text_rect.left, top))
            if button is not None and action is not None:
                self._buttons.append((button.move(self.text_rect.left, top), action))
            y += block.get_height()
        self.content_height = y
        surface.set_clip(previous_clip)

        self._draw_scroll_bar(surface)
        hint = body_font(BODY_SIZE).render('Esc: leave the board', True, DIM_COLOR)
        surface.blit(hint, hint.get_rect(midbottom=(WIDTH // 2, HEIGHT - MARGIN // 2)))

    def _draw_frame(self, surface: pygame.Surface) -> None:
        outer = pygame.Rect(0, 0, WIDTH, HEIGHT)
        pygame.draw.rect(surface, ACCENT_DIM, outer, 1)
        pygame.draw.rect(surface, ACCENT, outer.inflate(-10, -10), 1)
        bracket = 22
        for (cx, cy, sx, sy) in ((5, 5, 1, 1), (WIDTH - 6, 5, -1, 1), (5, HEIGHT - 6, 1, -1), (WIDTH - 6, HEIGHT - 6, -1, -1)):
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx + sx * bracket, cy), 3)
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx, cy + sy * bracket), 3)

    def _draw_scroll_bar(self, surface: pygame.Surface) -> None:
        if self._max_scroll() <= 0:
            return
        track = self.text_rect.height
        thumb = max(24, track * self.text_rect.height // max(1, self.content_height))
        top = self.text_rect.top + (track - thumb) * self.scroll // self._max_scroll()
        pygame.draw.rect(surface, ACCENT, (self.text_rect.right + 10, top, 4, thumb))

    # ---- events ----

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.text_rect.height)

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll + pixels))

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if event.type == pygame.QUIT:
            return ('exit', None)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return ('close', None)
            if event.key == pygame.K_UP:
                self._scroll_by(-SCROLL_STEP)
            elif event.key == pygame.K_DOWN:
                self._scroll_by(SCROLL_STEP)
            elif event.key in PAGE_KEYS:
                self._scroll_by(PAGE_KEYS[event.key] * self.text_rect.height)
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * SCROLL_STEP)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.text_rect.collidepoint(event.pos):
            for rect, action in self._buttons:
                if rect.collidepoint(event.pos):
                    action()
                    break
        return None
