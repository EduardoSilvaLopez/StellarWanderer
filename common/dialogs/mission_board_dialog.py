"""The missions as windows, both over one list (see galaxies/missions/mission_board.py for the rules).

The list shows each mission by its title and a line about time, under headings. A click on a mission opens its detail: the
description, and the button that acts on it, if there is one. Esc (or a right-click) goes back from the detail to the list,
and from the list closes the window. The lines scroll with the wheel and the arrow keys, and the scroll bar can be dragged (see ScrollBar).

MissionBoardDialog is the board of an outpost: "Your missions" (delivered there) and "Available" (offers, taken there, the
latest deadline first), with their deadlines. Under the list (not under a detail) it has two buttons, Leave and Communicate (see
MissionBoardDialog). PendingMissionsDialog is the view away from any outpost: the missions taken and not yet done, with the time
left, and nothing to act on."""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
import pygame

from common import audio
from common.paths import resource_path
from .dialog import Dialog, DialogResult, is_cancel
from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, BUTTON_FILL, BUTTON_FILL_HOVER, TEXT_COLOR, MessageDialog
from .scroll_bar import ScrollBar

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
DETAIL_TITLE_SIZE = 22
ROW_PAD = 12
ROW_GAP = 12
BUTTON_WIDTH = 150
BUTTON_HEIGHT = 36
SCROLL_STEP = 40
PAGE_KEYS = {pygame.K_PAGEUP: -1, pygame.K_PAGEDOWN: 1}
FOOTER_HEIGHT = 70  # the band under the text that MissionBoardDialog keeps for its two buttons
FOOTER_BUTTON_HEIGHT = 64
FOOTER_BUTTON_GAP = 30
FOOTER_LABELS = ('Leave', 'Communicate')
PORTRAIT_SIZE = (38, 57)  # 2:3, as the portraits

# One line of the content: (surface, gap above it, its clickable rect inside the surface or None, what a click does).
Item = Tuple[pygame.Surface, int, Optional[pygame.Rect], Optional[Callable[[], None]]]
# A heading of the list, its missions, and what to say when there are none: (heading, missions, empty text).
Section = Tuple[str, List['Mission'], str]


class MissionListDialog(Dialog):
    """The list and the detail of missions. A subclass gives the sections, the line about time, and the action, if any.
    `footer_height` is the band under the text that a subclass keeps for its own buttons."""

    def __init__(self, title: str, footer_height: int = 0) -> None:
        super().__init__(WIDTH, HEIGHT)
        self.open_mission: Optional[Mission] = None  # the mission whose detail is shown; None for the list
        self.notice: Optional[Tuple[str, str]] = None  # (mission title, text) shown in place of the list, after a delivery
        self.scroll: int = 0
        self._list_scroll: int = 0  # the list's scroll while a detail is open, restored when the list is shown again
        self.content_height: int = 0
        self._clickable: List[Tuple[pygame.Rect, Callable[[], None]]] = []  # where the clickable lines were last drawn
        self._texture: Optional[pygame.Surface] = None
        self._texture_loaded: bool = False

        size = TITLE_SIZE
        self._title = title_font(size).render(title, True, ACCENT)
        while self._title.get_width() > WIDTH - 2 * MARGIN and size > 12:
            size -= 1
            self._title = title_font(size).render(title, True, ACCENT)
        self._divider_y = MARGIN - 4 + self._title.get_height() + 12
        text_bottom = HEIGHT - MARGIN - footer_height
        self.text_rect = pygame.Rect(MARGIN, self._divider_y + 16, WIDTH - 2 * MARGIN, text_bottom - 12 - (self._divider_y + 16))
        self.scroll_bar = ScrollBar(
            pygame.Rect(self.text_rect.right + 10, self.text_rect.top, ScrollBar.MIN_WIDTH, self.text_rect.height), ACCENT
        )

    # region What a subclass gives
    def _sections(self) -> List[Section]:
        raise NotImplementedError

    def _deadline_line(self, mission: Mission) -> str:
        from galaxies.missions.mission_board import DATE_FORMAT  # local: the board's module imports the player, which imports this package
        return f"Deadline: {mission.deadline.strftime(DATE_FORMAT)}"

    def _action(self, mission: Mission) -> Optional[Tuple[str, Callable[[], None]]]:
        """The button of the detail, its label and what it does, or None for no button."""
        return None

    # endregion

    # region Content
    def _items(self, width: int) -> List[Item]:
        """Every line of the content, top to bottom, for a text area `width` wide."""
        if self.notice is not None:
            return self._notice_items(self.notice, width)
        if self.open_mission is not None:
            return self._detail_items(self.open_mission, width)
        return self._list_items(width)

    def _notice_items(self, notice: Tuple[str, str], width: int) -> List[Item]:
        """What the outpost says when a mission is done: the mission, and the reward text."""
        body = body_font(BODY_SIZE)
        title, text = notice
        items: List[Item] = [
            (title_font(DETAIL_TITLE_SIZE).render('Mission completed', True, ACCENT), 0, None, None),
            (body.render(title, True, LABEL_COLOR), 6, None, None),
        ]
        return items + [(body.render(line, True, TEXT_COLOR), 14 if index == 0 else 4, None, None)
                        for index, line in enumerate(MessageDialog.wrap(text, body, width))]

    def _list_items(self, width: int) -> List[Item]:
        heading = title_font(HEADING_SIZE)
        items: List[Item] = []
        for index, (title, missions, empty) in enumerate(self._sections()):
            items.append((heading.render(title, True, ACCENT), 0 if index == 0 else 22, None, None))
            if missions:
                items += [self._row(mission, width) for mission in missions]
            else:
                items.append((body_font(BODY_SIZE).render(empty, True, DIM_COLOR), 4, None, None))
        return items

    def _detail_items(self, mission: Mission, width: int) -> List[Item]:
        """The description of a mission, and the button that acts on it, if any. Acting goes back to the list."""
        body = body_font(BODY_SIZE)
        items: List[Item] = [
            (title_font(DETAIL_TITLE_SIZE).render(mission.title(), True, ACCENT), 0, None, None),
            (body.render(self._deadline_line(mission), True, LABEL_COLOR), 6, None, None),
        ]
        if mission.progress():
            items.append((body.render(mission.progress(), True, ACCENT), 4, None, None))
        # Paragraphs (the blank lines of the description) are wrapped one by one, as the messages do: the wrap only
        # breaks at spaces, so a blank line inside a word would be measured as part of it and break the lines too early.
        paragraph_gap = 14
        for index, paragraph in enumerate(mission.description().split('\n\n')):
            for line_index, line in enumerate(MessageDialog.wrap(paragraph, body, width)):
                gap = paragraph_gap if index > 0 and line_index == 0 else 4
                items.append((body.render(line, True, TEXT_COLOR), gap, None, None))
        action = self._action(mission)
        if action is not None:
            label, do = action
            items.append((self._button(label), 28, pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT), do))
        return items

    def _row(self, mission: Mission, width: int) -> Item:
        """One mission in the list: its title, a line about time and, if it has one, its progress, in a box. A click opens its detail."""
        lines: List[pygame.Surface] = [
            title_font(HEADING_SIZE).render(mission.title(), True, ACCENT),
            body_font(BODY_SIZE).render(self._deadline_line(mission), True, LABEL_COLOR),
        ]
        if mission.progress():
            lines.append(body_font(BODY_SIZE).render(mission.progress(), True, TEXT_COLOR))
        height = sum(line.get_height() + 4 for line in lines) + 2 * ROW_PAD
        row = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(row, ROW_FILL, row.get_rect())
        pygame.draw.rect(row, ACCENT_DIM, row.get_rect(), 1)
        y = ROW_PAD
        for line in lines:
            row.blit(line, (ROW_PAD, y))
            y += line.get_height() + 4
        return row, ROW_GAP, row.get_rect(), lambda: self._show(mission)

    @staticmethod
    def _button(label: str) -> pygame.Surface:
        button = pygame.Surface((BUTTON_WIDTH, BUTTON_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(button, BUTTON_FILL, button.get_rect())
        pygame.draw.rect(button, ACCENT, button.get_rect(), 2)
        caption = body_font(18).render(label, True, ACCENT)
        button.blit(caption, caption.get_rect(center=button.get_rect().center))
        return button

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.text_rect.height)

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll + pixels))
    # endregion

    # region Changing the view
    def _show(self, mission: Mission) -> None:
        self._list_scroll = self.scroll
        self.open_mission = mission
        self.scroll = 0
        self._clickable = []

    def _show_list(self) -> None:
        """Back to the list, at the scroll it had. draw keeps that within the list's length, which may have changed."""
        self.open_mission = None
        self.notice = None
        self.scroll = self._list_scroll
        self._clickable = []

    def _act(self, action: Callable[[Mission], Optional[str]], mission: Mission) -> None:
        """The board changes, so the list is shown again at its scroll. An action that answers with a text (a delivery's
        reward) shows it first, from the top: Esc (or a right-click) then goes back to the list."""
        reply = action(mission)
        self._show_list()
        if reply is not None:
            self.notice = (mission.title(), reply)
            self.scroll = 0

    # endregion

    # region Drawing
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

        self._clickable = []
        previous_clip = surface.get_clip()
        surface.set_clip(self.text_rect)
        items = self._items(self.text_rect.width)
        self.content_height = sum(gap + block.get_height() for block, gap, _, _ in items)
        self.scroll = min(self.scroll, self._max_scroll())  # the list may have become shorter since it was scrolled
        y = 0
        for block, gap, rect, action in items:
            y += gap
            top = self.text_rect.top + y - self.scroll
            if top + block.get_height() >= self.text_rect.top and top <= self.text_rect.bottom:
                surface.blit(block, (self.text_rect.left, top))
            if rect is not None and action is not None:
                self._clickable.append((rect.move(self.text_rect.left, top), action))
            y += block.get_height()
        surface.set_clip(previous_clip)

        self.scroll_bar.draw(surface, self.scroll, self._max_scroll(), self.text_rect.height)

    def _draw_frame(self, surface: pygame.Surface) -> None:
        outer = pygame.Rect(0, 0, WIDTH, HEIGHT)
        pygame.draw.rect(surface, ACCENT_DIM, outer, 1)
        pygame.draw.rect(surface, ACCENT, outer.inflate(-10, -10), 1)
        bracket = 22
        for (cx, cy, sx, sy) in ((5, 5, 1, 1), (WIDTH - 6, 5, -1, 1), (5, HEIGHT - 6, 1, -1), (WIDTH - 6, HEIGHT - 6, -1, -1)):
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx + sx * bracket, cy), 3)
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx, cy + sy * bracket), 3)

    # endregion

    # region Events
    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if event.type == pygame.QUIT:
            return ('exit', None)
        moved = self.scroll_bar.handle_event(event, self.scroll, self._max_scroll(), self.text_rect.height)
        if moved is not None:
            self.scroll = moved
            return None
        if is_cancel(event):
            if self.open_mission is None and self.notice is None:
                return ('close', None)
            audio.play('ui_close')
            self._show_list()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._scroll_by(-SCROLL_STEP)
            elif event.key == pygame.K_DOWN:
                self._scroll_by(SCROLL_STEP)
            elif event.key in PAGE_KEYS:
                self._scroll_by(PAGE_KEYS[event.key] * self.text_rect.height)
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * SCROLL_STEP)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.text_rect.collidepoint(event.pos):
            for rect, action in self._clickable:
                if rect.collidepoint(event.pos):
                    audio.play('ui_click')
                    action()
                    break
        return None
    # endregion


class MissionBoardDialog(MissionListDialog):
    """The board of an outpost: the player's missions to deliver here, and the offers to take.

    Under the list (not under a detail or a notice) are two buttons: Leave, which does what Esc does there, and Communicate,
    with the portrait of the outpost's com officer. Results: ('close', None) and ('communicate', None); the host talks to the
    officer and opens the board again (see main.visit_mission_board). Tab, Left and Right move the focus between the buttons,
    Enter presses the focused one, and the mouse moves the focus too."""

    OPEN_SOUND = 'board_open'

    def __init__(self, board: MissionBoard) -> None:
        super().__init__(board.title, FOOTER_HEIGHT)
        self.board: MissionBoard = board
        self.focus: int = 0  # the footer button that Enter presses
        width = (WIDTH - 2 * MARGIN - FOOTER_BUTTON_GAP) // 2
        top = HEIGHT - MARGIN + 6 - FOOTER_BUTTON_HEIGHT
        self._footer_rects: List[pygame.Rect] = [
            pygame.Rect(MARGIN + index * (width + FOOTER_BUTTON_GAP), top, width, FOOTER_BUTTON_HEIGHT)
            for index in range(len(FOOTER_LABELS))]
        icon = board.outpost.com_officer.icon  # no officer is an error: the outpost is prepared when its Km2 is made
        self._portrait: Optional[pygame.Surface] = None if icon is None else pygame.transform.smoothscale(icon, PORTRAIT_SIZE)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        font = body_font(20)
        for index, (label, rect) in enumerate(zip(FOOTER_LABELS, self._footer_rects)):
            pygame.draw.rect(surface, BUTTON_FILL_HOVER if index == self.focus else BUTTON_FILL, rect)
            pygame.draw.rect(surface, ACCENT, rect, 2)
            label_area = rect
            if label == 'Communicate':
                portrait_rect = pygame.Rect((0, 0), PORTRAIT_SIZE)
                portrait_rect.midleft = (rect.left + 12, rect.centery)
                if self._portrait is not None:
                    surface.blit(self._portrait, portrait_rect)
                pygame.draw.rect(surface, ACCENT, portrait_rect, 1)
                label_area = pygame.Rect(portrait_rect.right, rect.top, rect.right - portrait_rect.right, rect.height)
            caption = font.render(label, True, ACCENT)
            surface.blit(caption, caption.get_rect(center=label_area.center))

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        if self.open_mission is None and self.notice is None:
            self._draw_footer(surface)

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if self.open_mission is not None or self.notice is not None:
            return super().handle_event(event)
        pressed: Optional[int] = None
        if event.type == pygame.MOUSEMOTION:
            for index, rect in enumerate(self._footer_rects):
                if rect.collidepoint(event.pos):
                    self.focus = index
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self._footer_rects):
                if rect.collidepoint(event.pos):
                    pressed = index
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                pressed = self.focus
            elif event.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
                backwards = event.key == pygame.K_LEFT or (event.key == pygame.K_TAB and event.mod & pygame.KMOD_SHIFT)
                self.focus = (self.focus + (-1 if backwards else 1)) % len(FOOTER_LABELS)
        if pressed is None:
            return super().handle_event(event)
        audio.play('ui_click')
        return ('close', None) if FOOTER_LABELS[pressed] == 'Leave' else ('communicate', None)

    def _sections(self) -> List[Section]:
        offers = sorted(self.board.offers, key=lambda offer: offer.deadline, reverse=True)  # the latest deadline first
        return [('Your missions', self.board.mine(), 'None.'),
                ('Available', offers, 'Nothing new.')]

    def _action(self, mission: Mission) -> Optional[Tuple[str, Callable[[], None]]]:
        if mission in self.board.mine():
            return 'Deliver', lambda: self._act(self.board.deliver, mission)
        return 'Accept', lambda: self._act(self.board.accept, mission)


class PendingMissionsDialog(MissionListDialog):
    """The missions the player has taken and not yet done, with the time left. Nothing to act on here: delivery is at the
    outpost's board."""

    def __init__(self, missions: List[Mission]) -> None:
        super().__init__('Pending missions')
        self.missions: List[Mission] = missions

    def _sections(self) -> List[Section]:
        return [('Pending missions', self.missions, 'None.')]

    def _deadline_line(self, mission: Mission) -> str:
        import game_environment as gem  # local: the game's environment, not needed by the rest of this module
        left = mission.deadline - gem.current_environment.date_time
        if left.total_seconds() <= 0:
            return 'Time left: expired'
        hours, remainder = divmod(int(left.total_seconds()), 3600)
        return f"Time left: {left.days} days {hours - 24 * left.days:02d} h {remainder // 60:02d} min"
