"""The starting dialog: start a new game, load a savefile, or exit the game."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import glob
import logging
import math
import os
import pygame
from datetime import datetime

from .dialog import Dialog, DialogResult
from .dialog_fonts import body_font, title_font
from .instructions_dialog import InstructionsDialog
from .message_dialog import MessageDialog
from .messages import Message

logger = logging.getLogger(__name__)
from common.paths import data_path, SAVEFILES_DIR
from common.savefile import Savefile, SAVE_NAME_FORBIDDEN, SAVE_NAME_MAX_LENGTH
from common.paths import resource_path

ICON_PATH = resource_path('presentation', 'game_icon.png')
DOUBLE_CLICK_MS = 400


def _blit_centred_on_ink(surface: pygame.Surface, text: pygame.Surface, x: int, rect: pygame.Rect) -> None:
    """Blit `text` at x with its visible glyphs centred on the rect's height (the font's box has space above and below)."""
    ink = text.get_bounding_rect()
    surface.blit(text, (x, rect.centery - ink.centery))


def _draw_gear(surface: pygame.Surface, rect: pygame.Rect, background: tuple) -> None:
    """A metal gear with eight teeth, filling the square rect."""
    cx, cy = rect.center
    steps = 32
    points = []
    for k in range(steps):
        radius = rect.width * (0.46 if k % 4 in (0, 1) else 0.36)
        angle = k * math.tau / steps
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    pygame.draw.polygon(surface, (170, 178, 190), points)
    pygame.draw.polygon(surface, (100, 105, 115), points, 1)
    pygame.draw.circle(surface, background, rect.center, int(rect.width * 0.14))


class StartingDialog(Dialog):
    """Choose between a new game, a savefile, saving the game, and leaving the game.

    Shown when the program starts and again on Esc while playing (game_running=True, where Esc
    resumes the game). Results: ('new', seed), ('load', path), ('save', name), ('exit', None), ('resume', None).
    The Instructions button shows the instructions screen (see InstructionsDialog) in its place until Back.
    ('save', '') means the default name: the text box is empty, and its grey text shows that name.

    Esc opens it from the game and does not quit; the Exit game button (or closing the window) does.
    The save row is only offered while a game is running.
    """

    WIDTH = 800
    HEIGHT = 600
    ITEM_HEIGHT = 42
    NAME_ROW_Y = 109
    TITLE = "Stellar Wanderer"
    TITLE_SIZE = 44
    TITLE_TOP = 12  # top of the title's box, before its letters
    MARGIN = 24  # left and right, for the labels, the title and the list
    LIST_TOP = 150
    EXIT_ROW_HEIGHT = 52  # bottom row reserved for the exit button

    def __init__(self, game_running: bool = False) -> None:
        super().__init__(self.WIDTH, self.HEIGHT)
        self.game_running: bool = game_running

        self.savefiles: List[Dict[str, Any]] = []
        self.selected_index: int = -1  # -1 means no savefile selected
        self.seed_input: str = "1"
        self.seed_input_active: bool = False
        self.name_input: str = ""  # empty shows the default name, in grey
        self.name_input_active: bool = False
        self.instructions: Optional[InstructionsDialog] = None  # open while the instructions screen is shown
        self.scroll_offset: int = 0  # first visible savefile of the list
        self.hover_index: Optional[int] = None  # the savefile under the mouse, highlighted
        self.prompt: Optional[MessageDialog] = None  # the delete question, while open
        self.prompt_index: int = -1  # the savefile the question is about
        self._last_click: Optional[int] = None  # the savefile last clicked, and when (for a double click)
        self._last_click_at: int = 0

        self.font_title: Optional[pygame.font.Font] = None
        self.icon: Optional[pygame.Surface] = None
        self.font_normal: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None
        self.font_savefile: Optional[pygame.font.Font] = None

        # The fields and buttons are left-aligned in one group, the labels in a column at x=60. The icon sits at the
        # right of both rows, and the free space between New Game and the icon is for further buttons.
        # The icon is a square: its top is the top of the title's letters, its bottom the bottom of the Save row.
        # The Save row, the Instructions button and the file box stop a gap short of the icon's left edge.
        title_top = self.TITLE_TOP + title_font(self.TITLE_SIZE).render(self.TITLE, True, (0, 0, 0)).get_bounding_rect().top
        save_bottom = self.NAME_ROW_Y + 28
        icon_size = save_bottom - title_top
        self.icon_rect = pygame.Rect(self.WIDTH - self.MARGIN - icon_size, title_top, icon_size, icon_size)
        gap = 12
        self.input_rect = pygame.Rect(150, 73, 80, 28)
        self.new_game_rect = pygame.Rect(242, 73, 120, 28)
        self.instructions_rect = pygame.Rect(self.icon_rect.left - gap - 28, 73, 28, 28)
        self.save_rect = pygame.Rect(self.icon_rect.left - gap - 120, self.NAME_ROW_Y, 120, 28)
        self.name_rect = pygame.Rect(150, self.NAME_ROW_Y, self.save_rect.left - 10 - 150, 28)
        self.list_rect = pygame.Rect(self.MARGIN, self.LIST_TOP, self.WIDTH - 2 * self.MARGIN,
                                     self.HEIGHT - self.LIST_TOP - self.EXIT_ROW_HEIGHT)
        self.exit_rect = pygame.Rect(self.WIDTH // 2 - 100, self.HEIGHT - self.EXIT_ROW_HEIGHT + 12, 200, 32)

        self._load_savefiles()

    @property
    def _max_visible(self) -> int:
        """How many savefile rows fit in the list."""
        return self.list_rect.height // self.ITEM_HEIGHT

    def _load_savefiles(self) -> None:
        """Load list of available savefiles."""
        self.savefiles = []
        if os.path.exists(data_path(SAVEFILES_DIR)):
            files = glob.glob(data_path(SAVEFILES_DIR, '*.json'))
            for filepath in sorted(files, key=os.path.getmtime, reverse=True):
                filename = os.path.basename(filepath)
                name = os.path.splitext(filename)[0]
                real_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                real_time_formatted = real_time.strftime('%Y-%m-%d %H:%M:%S')

                # A default name is "Savefile {seed} {datetime}", with the datetime as "YYYY-MM-DDTHH_MM_SS"
                parts = name[len('Savefile '):].split(' ', 1) if name.startswith('Savefile ') else []
                if len(parts) == 2:
                    seed, game_time_str = parts
                    game_time_formatted = game_time_str.replace('T', ' ').replace('_', ':')
                    display_name = f"Seed {seed}   -   Time: {game_time_formatted}   -   Saved at {real_time_formatted}"
                else:
                    display_name = f"{name}   -   Saved at {real_time_formatted}"

                self.savefiles.append({
                    'path': filepath,
                    'filename': filename,
                    'display_name': display_name,
                })

    def _ensure_fonts(self) -> None:
        if self.font_title is None:
            self.font_title = title_font(self.TITLE_SIZE)
            self.icon = pygame.transform.smoothscale(pygame.image.load(ICON_PATH), self.icon_rect.size)
            self.font_normal = body_font(20)
            self.font_small = body_font(17)
            self.font_savefile = body_font(16)  # the save names are long: kept small to fit the rows

    def _savefile_rect(self, index: int) -> pygame.Rect:
        """Screen rectangle of the savefile at `index` (only meaningful while it is visible)."""
        y = self.list_rect.top + 5 + (index - self.scroll_offset) * self.ITEM_HEIGHT
        return pygame.Rect(self.list_rect.x + 5, y, self.list_rect.width - 40, self.ITEM_HEIGHT - 5)

    def _visible_indices(self) -> range:
        return range(self.scroll_offset, min(self.scroll_offset + self._max_visible, len(self.savefiles)))

    def _scroll_to(self, offset: int) -> None:
        self.scroll_offset = max(0, min(max(0, len(self.savefiles) - self._max_visible), offset))

    def _select(self, index: int) -> None:
        """Select a savefile and scroll so that it is visible."""
        self.selected_index = index
        if index >= 0:
            if index < self.scroll_offset:
                self._scroll_to(index)
            elif index >= self.scroll_offset + self._max_visible:
                self._scroll_to(index - self._max_visible + 1)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the dialog: seed input, New Game button, scrollable savefile list, Exit game button."""
        if self.instructions is not None:
            self.instructions.draw(surface)
            return
        if self.prompt is not None:
            self.prompt.draw(surface)
            return
        self._ensure_fonts()
        surface.fill((20, 20, 30))

        # Title
        # Title, right-aligned with the list; the icon at the right of the button rows
        title = self.font_title.render(self.TITLE, True, (100, 200, 255))
        surface.blit(title, title.get_rect(topleft=(self.MARGIN, self.TITLE_TOP)))
        surface.blit(self.icon, self.icon_rect)

        # Seed input section, its label vertically centred on the box
        seed_label = self.font_normal.render("World Seed:", True, (150, 200, 255))
        surface.blit(seed_label, seed_label.get_rect(midleft=(self.MARGIN, self.input_rect.centery)))

        pygame.draw.rect(surface, (50, 50, 80) if self.seed_input_active else (40, 40, 60), self.input_rect)
        pygame.draw.rect(surface, (100, 150, 255) if self.seed_input_active else (80, 80, 120), self.input_rect, 2)
        seed_text = self.font_small.render(self.seed_input, True, (200, 200, 200))
        _blit_centred_on_ink(surface, seed_text, self.input_rect.x + 8, self.input_rect)

        # New Game button
        pygame.draw.rect(surface, (70, 115, 70), self.new_game_rect)
        pygame.draw.rect(surface, (110, 190, 110), self.new_game_rect, 2)
        new_text = self.font_small.render("New Game", True, (255, 255, 255))
        _blit_centred_on_ink(surface, new_text, self.new_game_rect.centerx - new_text.get_width() // 2, self.new_game_rect)

        # Instructions button (a gear for now, no function yet)
        pygame.draw.rect(surface, (40, 40, 60), self.instructions_rect)
        pygame.draw.rect(surface, (80, 80, 120), self.instructions_rect, 2)
        _draw_gear(surface, self.instructions_rect.inflate(-6, -6), (40, 40, 60))

        # Save row: the file name (grey default, recalculated from the game's date and time), and Save
        if self.game_running:
            name_label = self.font_normal.render("File name:", True, (150, 200, 255))
            surface.blit(name_label, name_label.get_rect(midleft=(self.MARGIN, self.name_rect.centery)))

            pygame.draw.rect(surface, (50, 50, 80) if self.name_input_active else (40, 40, 60), self.name_rect)
            pygame.draw.rect(surface, (100, 150, 255) if self.name_input_active else (80, 80, 120), self.name_rect, 2)
            if self.name_input:
                name_text = self.font_small.render(self.name_input, True, (200, 200, 200))
            else:
                name_text = self.font_small.render(Savefile.default_name(), True, (110, 110, 130))
            _blit_centred_on_ink(surface, name_text, self.name_rect.x + 8, self.name_rect)

            pygame.draw.rect(surface, (70, 115, 70), self.save_rect)
            pygame.draw.rect(surface, (110, 190, 110), self.save_rect, 2)
            save_text = self.font_small.render("Save", True, (255, 255, 255))
            _blit_centred_on_ink(surface, save_text, self.save_rect.centerx - save_text.get_width() // 2, self.save_rect)

        # Save files list section
        pygame.draw.rect(surface, (30, 30, 50), self.list_rect)
        pygame.draw.rect(surface, (80, 80, 120), self.list_rect, 2)

        if self.savefiles:
            for i in self._visible_indices():
                rect = self._savefile_rect(i)
                if i == self.hover_index:
                    fill = (75, 75, 120)
                elif i == self.selected_index:
                    fill = (80, 80, 140)
                else:
                    fill = (40, 40, 60)
                pygame.draw.rect(surface, fill, rect)
                pygame.draw.rect(surface, (100, 100, 150), rect, 2)
                text = self.font_savefile.render(self.savefiles[i]['display_name'], True, (200, 200, 200))
                surface.blit(text, (rect.x + 10, rect.y + 8))

            # Scrollbar if needed
            if len(self.savefiles) > self._max_visible:
                scrollbar_height = self.list_rect.height - 10
                scroll_fraction = self.scroll_offset / len(self.savefiles)
                thumb_height = max(20, scrollbar_height * (self._max_visible / len(self.savefiles)))
                thumb_y = self.list_rect.top + 5 + scroll_fraction * (scrollbar_height - thumb_height)
                scrollbar_x = self.list_rect.right - 20  # inside the list, clear of the entries
                pygame.draw.rect(surface, (60, 60, 80), (scrollbar_x, self.list_rect.top + 5, 10, scrollbar_height))
                pygame.draw.rect(surface, (100, 150, 200), (scrollbar_x, thumb_y, 10, thumb_height))
        else:
            no_saves = self.font_normal.render("No save files found", True, (150, 150, 150))
            surface.blit(no_saves, (self.width // 2 - no_saves.get_width() // 2, self.list_rect.top + 60))

        # Exit game button, at the very bottom
        pygame.draw.rect(surface, (110, 50, 50), self.exit_rect)
        pygame.draw.rect(surface, (190, 110, 110), self.exit_rect, 2)
        exit_text = self.font_normal.render("Exit game", True, (255, 255, 255))
        _blit_centred_on_ink(surface, exit_text, self.exit_rect.centerx - exit_text.get_width() // 2, self.exit_rect)

    def _savefile_at(self, position: Tuple[int, int]) -> Optional[int]:
        """The visible savefile under `position`, or None."""
        return next((i for i in self._visible_indices() if self._savefile_rect(i).collidepoint(position)), None)

    def _ask_delete(self, index: int) -> None:
        """Right-click on a save: the question, Delete or Cancel."""
        name = os.path.splitext(self.savefiles[index]['filename'])[0]
        self.prompt = MessageDialog(Message(
            title='DELETE SAVE?',
            text=f"Delete the save '{name}'? It cannot be recovered.",
            buttons=['Delete', 'Cancel'],
        ))
        self.prompt_index = index

    def _delete_savefile(self, index: int) -> None:
        """Delete the save file at `index` of the list, then refresh the list."""
        try:
            os.remove(self.savefiles[index]['path'])
        except OSError as error:
            logger.warning(f"Could not delete the savefile: {error}")
        self.selected_index = -1
        self.hover_index = None
        self._load_savefiles()
        self._scroll_to(self.scroll_offset)

    def _click_savefile(self, index: int) -> Optional[DialogResult]:
        """A click selects the save and puts its name in the name box, ready to be saved again or edited. A second click
        on the same save, within DOUBLE_CLICK_MS, loads it."""
        now = pygame.time.get_ticks()
        if self._last_click == index and now - self._last_click_at <= DOUBLE_CLICK_MS:
            return ('load', self.savefiles[index]['path'])
        self._last_click = index
        self._last_click_at = now
        self.selected_index = index
        self.name_input = Savefile.clean_name(os.path.splitext(self.savefiles[index]['filename'])[0])
        self.name_input_active = True
        return None

    def _save_result(self) -> DialogResult:
        """The typed name, cleaned; '' (the default name) when nothing usable is typed."""
        return ('save', Savefile.clean_name(self.name_input))

    def _new_game_result(self) -> Optional[DialogResult]:
        try:
            return ('new', float(self.seed_input) if self.seed_input else 1.0)
        except ValueError:
            self.seed_input = "1"
            return None

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Handle one event (mouse positions in dialog coordinates)."""
        if self.instructions is not None:
            result = self.instructions.handle_event(event)
            if result is not None and result[0] == 'back':
                self.instructions = None
                return None
            return result
        if self.prompt is not None:
            result = self.prompt.handle_event(event)
            if result is not None and result[0] == 'close':
                if result[1] == 0:  # Delete
                    self._delete_savefile(self.prompt_index)
                self.prompt = None
                self.prompt_index = -1
            return None
        if event.type == pygame.QUIT:
            return ('exit', None)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.input_rect.collidepoint(event.pos):
                self.seed_input_active = True
                self.name_input_active = False
            elif self.new_game_rect.collidepoint(event.pos):
                return self._new_game_result()
            elif self.game_running and self.name_rect.collidepoint(event.pos):
                self.name_input_active = True
                self.seed_input_active = False
            elif self.game_running and self.save_rect.collidepoint(event.pos):
                return self._save_result()
            elif self.exit_rect.collidepoint(event.pos):
                return ('exit', None)
            elif self.instructions_rect.collidepoint(event.pos):
                self.instructions = InstructionsDialog()
            else:
                self.seed_input_active = False
                self.name_input_active = False
                for i in self._visible_indices():
                    if self._savefile_rect(i).collidepoint(event.pos):
                        return self._click_savefile(i)

        elif event.type == pygame.MOUSEMOTION:
            self.hover_index = self._savefile_at(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            index = self._savefile_at(event.pos)
            if index is not None:
                self._ask_delete(index)

        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_to(self.scroll_offset - 1 if event.y > 0 else self.scroll_offset + 1)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_running:
                    return ('resume', None)
                self.seed_input_active = False
                self.name_input_active = False
            elif self.seed_input_active:
                if event.key == pygame.K_BACKSPACE:
                    self.seed_input = self.seed_input[:-1]
                elif event.key == pygame.K_RETURN:
                    return self._new_game_result()
                elif event.unicode.isdigit() and len(self.seed_input) < 10:
                    self.seed_input += event.unicode
            elif self.name_input_active:
                if event.key == pygame.K_BACKSPACE:
                    self.name_input = self.name_input[:-1]
                elif event.key == pygame.K_RETURN:
                    return self._save_result()
                elif (event.unicode and event.unicode.isprintable() and event.unicode not in SAVE_NAME_FORBIDDEN
                      and len(self.name_input) < SAVE_NAME_MAX_LENGTH):
                    self.name_input += event.unicode
            elif event.key == pygame.K_UP and self.savefiles:
                self._select(max(-1, self.selected_index - 1))
            elif event.key == pygame.K_DOWN and self.savefiles:
                self._select(min(len(self.savefiles) - 1, self.selected_index + 1))
            elif event.key == pygame.K_RETURN and self.selected_index >= 0:
                return ('load', self.savefiles[self.selected_index]['path'])

        return None
