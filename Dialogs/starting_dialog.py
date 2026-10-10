"""The starting dialog: start a new game, load a savefile, or exit the game."""

from __future__ import annotations
from typing import List, Optional, Dict, Any
import glob
import os
import pygame
from datetime import datetime

from .dialog import Dialog, DialogResult


class StartingDialog(Dialog):
    """Choose between a new game, a savefile, and leaving the game.

    Shown when the program starts and again on Esc while playing (game_running=True, where Esc
    resumes the game). Results: ('new', seed), ('load', path), ('exit', None), ('resume', None).
    """

    WIDTH = 800
    HEIGHT = 600
    ITEM_HEIGHT = 42
    LIST_TOP = 130
    EXIT_ROW_HEIGHT = 52  # bottom row reserved for the exit button

    def __init__(self, game_running: bool = False) -> None:
        super().__init__(self.WIDTH, self.HEIGHT)
        self.game_running: bool = game_running

        self.savefiles: List[Dict[str, Any]] = []
        self.selected_index: int = -1  # -1 means no savefile selected
        self.seed_input: str = "1"
        self.seed_input_active: bool = False
        self.scroll_offset: int = 0  # first visible savefile of the list

        self.font_title: Optional[pygame.font.Font] = None
        self.font_normal: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None
        self.font_savefile: Optional[pygame.font.Font] = None

        self.input_rect = pygame.Rect(250, 73, 80, 28)
        self.new_game_rect = pygame.Rect(380, 73, 120, 28)
        self.list_rect = pygame.Rect(60, self.LIST_TOP, self.WIDTH - 120,
                                     self.HEIGHT - self.LIST_TOP - self.EXIT_ROW_HEIGHT)
        self.exit_rect = pygame.Rect(self.WIDTH // 2 - 100, self.HEIGHT - self.EXIT_ROW_HEIGHT + 12, 200, 32)

        self.load_savefiles()

    @property
    def max_visible(self) -> int:
        """How many savefile rows fit in the list."""
        return self.list_rect.height // self.ITEM_HEIGHT

    def load_savefiles(self) -> None:
        """Load list of available savefiles."""
        self.savefiles = []
        if os.path.exists('Savefiles'):
            files = glob.glob('Savefiles/Savefile *.json')
            for filepath in sorted(files, key=os.path.getmtime, reverse=True):
                filename = os.path.basename(filepath)
                # Format: "Savefile {seed} {datetime}.json"
                # DateTime format in filename: "YYYY-MM-DDTHH_MM_SS" (19 characters)
                parts = filename.replace('Savefile ', '').replace('.json', '').split(' ', 1)
                if len(parts) == 2:
                    seed, game_time_str = parts

                    # From "YYYY-MM-DDTHH_MM_SS" to "YYYY-MM-DD HH:mm:SS"
                    game_time_formatted = game_time_str.replace('T', ' ').replace('_', ':')

                    # Get real file modification time
                    real_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    real_time_formatted = real_time.strftime('%Y-%m-%d %H:%M:%S')

                    self.savefiles.append({
                        'path': filepath,
                        'filename': filename,
                        'seed': seed,
                        'game_time': game_time_formatted,
                        'real_time': real_time_formatted,
                        'display_name': f"Seed {seed}   -   Time: {game_time_formatted}   -   Saved at {real_time_formatted}"
                    })

    def _ensure_fonts(self) -> None:
        if self.font_title is None:
            self.font_title = pygame.font.Font(None, 48)
            self.font_normal = pygame.font.Font(None, 24)
            self.font_small = pygame.font.Font(None, 18)
            self.font_savefile = pygame.font.Font(None, 22)  # Slightly larger for save files

    def _savefile_rect(self, index: int) -> pygame.Rect:
        """Screen rectangle of the savefile at `index` (only meaningful while it is visible)."""
        y = self.list_rect.top + 5 + (index - self.scroll_offset) * self.ITEM_HEIGHT
        return pygame.Rect(65, y, self.list_rect.width - 40, self.ITEM_HEIGHT - 5)

    def _visible_indices(self) -> range:
        return range(self.scroll_offset, min(self.scroll_offset + self.max_visible, len(self.savefiles)))

    def _scroll_to(self, offset: int) -> None:
        self.scroll_offset = max(0, min(max(0, len(self.savefiles) - self.max_visible), offset))

    def _select(self, index: int) -> None:
        """Select a savefile and scroll so that it is visible."""
        self.selected_index = index
        if index >= 0:
            if index < self.scroll_offset:
                self._scroll_to(index)
            elif index >= self.scroll_offset + self.max_visible:
                self._scroll_to(index - self.max_visible + 1)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the dialog: seed input, New Game button, scrollable savefile list, Exit game button."""
        self._ensure_fonts()
        surface.fill((20, 20, 30))

        # Title
        title = self.font_title.render("Stellar Wanderer", True, (100, 200, 255))
        surface.blit(title, (self.width // 2 - title.get_width() // 2, 15))

        # Seed input section
        seed_label = self.font_normal.render("World Seed:", True, (150, 200, 255))
        surface.blit(seed_label, (60, self.input_rect.y + 2))

        pygame.draw.rect(surface, (50, 50, 80) if self.seed_input_active else (40, 40, 60), self.input_rect)
        pygame.draw.rect(surface, (100, 150, 255) if self.seed_input_active else (80, 80, 120), self.input_rect, 2)
        seed_text = self.font_small.render(self.seed_input, True, (200, 200, 200))
        surface.blit(seed_text, (self.input_rect.x + 8, self.input_rect.centery - seed_text.get_height() // 2))

        # New Game button
        pygame.draw.rect(surface, (100, 150, 100), self.new_game_rect)
        pygame.draw.rect(surface, (150, 255, 150), self.new_game_rect, 2)
        new_text = self.font_small.render("New Game", True, (255, 255, 255))
        surface.blit(new_text, new_text.get_rect(center=self.new_game_rect.center))

        # Save files list section
        pygame.draw.rect(surface, (30, 30, 50), self.list_rect)
        pygame.draw.rect(surface, (80, 80, 120), self.list_rect, 2)

        if self.savefiles:
            for i in self._visible_indices():
                rect = self._savefile_rect(i)
                pygame.draw.rect(surface, (80, 80, 140) if i == self.selected_index else (40, 40, 60), rect)
                pygame.draw.rect(surface, (100, 100, 150), rect, 2)
                text = self.font_savefile.render(self.savefiles[i]['display_name'], True, (200, 200, 200))
                surface.blit(text, (75, rect.y + 8))

            # Scrollbar if needed
            if len(self.savefiles) > self.max_visible:
                scrollbar_height = self.list_rect.height - 10
                scroll_fraction = self.scroll_offset / len(self.savefiles)
                thumb_height = max(20, scrollbar_height * (self.max_visible / len(self.savefiles)))
                thumb_y = self.list_rect.top + 5 + scroll_fraction * (scrollbar_height - thumb_height)
                scrollbar_x = self.width - 65
                pygame.draw.rect(surface, (60, 60, 80), (scrollbar_x, self.list_rect.top + 5, 10, scrollbar_height))
                pygame.draw.rect(surface, (100, 150, 200), (scrollbar_x, thumb_y, 10, thumb_height))
        else:
            no_saves = self.font_normal.render("No save files found", True, (150, 150, 150))
            surface.blit(no_saves, (self.width // 2 - no_saves.get_width() // 2, self.list_rect.top + 60))

        # Exit game button, at the very bottom
        pygame.draw.rect(surface, (150, 70, 70), self.exit_rect)
        pygame.draw.rect(surface, (255, 150, 150), self.exit_rect, 2)
        exit_text = self.font_normal.render("Exit game", True, (255, 255, 255))
        surface.blit(exit_text, exit_text.get_rect(center=self.exit_rect.center))

    def _new_game_result(self) -> Optional[DialogResult]:
        try:
            return ('new', int(self.seed_input) if self.seed_input else 1)
        except ValueError:
            self.seed_input = "1"
            return None

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        """Handle one event (mouse positions in dialog coordinates)."""
        if event.type == pygame.QUIT:
            return ('exit', None)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.input_rect.collidepoint(event.pos):
                self.seed_input_active = True
            elif self.new_game_rect.collidepoint(event.pos):
                return self._new_game_result()
            elif self.exit_rect.collidepoint(event.pos):
                return ('exit', None)
            else:
                self.seed_input_active = False
                for i in self._visible_indices():
                    if self._savefile_rect(i).collidepoint(event.pos):
                        return ('load', self.savefiles[i]['path'])

        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_to(self.scroll_offset - 1 if event.y > 0 else self.scroll_offset + 1)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_running:
                    return ('resume', None)
                self.seed_input_active = False
            elif self.seed_input_active:
                if event.key == pygame.K_BACKSPACE:
                    self.seed_input = self.seed_input[:-1]
                elif event.key == pygame.K_RETURN:
                    return self._new_game_result()
                elif event.unicode.isdigit() and len(self.seed_input) < 10:
                    self.seed_input += event.unicode
            elif event.key == pygame.K_UP and self.savefiles:
                self._select(max(-1, self.selected_index - 1))
            elif event.key == pygame.K_DOWN and self.savefiles:
                self._select(min(len(self.savefiles) - 1, self.selected_index + 1))
            elif event.key == pygame.K_RETURN and self.selected_index >= 0:
                return ('load', self.savefiles[self.selected_index]['path'])

        return None
