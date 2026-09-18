"""Startup dialog for choosing between loading and starting a new game."""

import glob
import os
import pygame
from datetime import datetime


class StartDialog:
    """Dialog to choose between loading a save file or starting a new game."""

    def __init__(self, surface=None, screen_width=800, screen_height=600):
        """Initialize the dialog.

        Args:
            surface: Existing pygame surface to use. If None, a new display is created.
            screen_width: Window width in pixels (used if surface is None)
            screen_height: Window height in pixels (used if surface is None)
        """
        self.width = screen_width
        self.height = screen_height
        self.surface = surface
        self.clock = None
        self.font_title = None
        self.font_normal = None
        self.font_small = None
        self.created_display = surface is None

        self.savefiles = []
        self.selected_index = -1  # -1 means no savefile selected
        self.seed_input = "1"
        self.seed_input_active = False
        self.scroll_offset = 0  # For scrolling through the savefile list

    def _safe_quit(self):
        """Quit pygame only if we created the display ourselves."""
        if self.created_display:
            pygame.quit()

    def setup_pygame(self):
        """Initialize pygame and create the display (if not provided)."""
        pygame.init()
        if self.surface is None:
            self.surface = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("Stellar Wanderer - Start Game")
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.Font(None, 48)
        self.font_normal = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.font_savefile = pygame.font.Font(None, 22)  # Slightly larger for save files

    def load_savefiles(self):
        """Load list of available savefiles."""
        self.savefiles = []
        if os.path.exists('Savefiles'):
            files = glob.glob('Savefiles/Savefile *.json')
            for filepath in sorted(files, key=os.path.getmtime, reverse=True):
                filename = os.path.basename(filepath)
                # Extract seed and datetime from filename
                # Format: "Savefile {seed} {datetime}.json"
                # DateTime format in filename: "YYYY-MM-DDTHH_MM_SS" (19 characters)
                parts = filename.replace('Savefile ', '').replace('.json', '').split(' ', 1)
                if len(parts) == 2:
                    seed, game_time_str = parts

                    # Parse game time from filename (convert T and _ to proper format)
                    # From "YYYY-MM-DDTHH_MM_SS" to "YYYY-MM-DD HH:mm:SS"
                    game_time_formatted = game_time_str.replace('T', ' ').replace('_', ':')

                    # Get real file modification time
                    import time as time_module
                    mtime = os.path.getmtime(filepath)
                    real_time = datetime.fromtimestamp(mtime)
                    real_time_formatted = real_time.strftime('%Y-%m-%d %H:%M:%S')

                    self.savefiles.append({
                        'path': filepath,
                        'filename': filename,
                        'seed': seed,
                        'game_time': game_time_formatted,
                        'real_time': real_time_formatted,
                        'display_name': f"Seed {seed}   -   Time: {game_time_formatted}   -   Saved at {real_time_formatted}"
                    })

    def draw(self):
        """Draw the main dialog screen with seed input and scrollable save file list."""
        self.surface.fill((20, 20, 30))

        # Title
        title = self.font_title.render("Stellar Wanderer", True, (100, 200, 255))
        self.surface.blit(title, (self.width // 2 - title.get_width() // 2, 15))

        # Seed input section
        seed_y = 75
        seed_label = self.font_normal.render("World Seed:", True, (150, 200, 255))
        self.surface.blit(seed_label, (60, seed_y))

        input_x = 250
        input_rect = pygame.Rect(input_x, seed_y - 2, 80, 28)
        pygame.draw.rect(self.surface, (50, 50, 80) if self.seed_input_active else (40, 40, 60), input_rect)
        pygame.draw.rect(self.surface, (100, 150, 255) if self.seed_input_active else (80, 80, 120), input_rect, 2)

        seed_text = self.font_small.render(self.seed_input, True, (200, 200, 200))
        self.surface.blit(seed_text, (input_rect.x + 8, input_rect.centery - seed_text.get_height() // 2))

        # New Game button
        new_game_rect = pygame.Rect(380, seed_y - 2, 120, 28)
        pygame.draw.rect(self.surface, (100, 150, 100), new_game_rect)
        pygame.draw.rect(self.surface, (150, 255, 150), new_game_rect, 2)

        new_text = self.font_small.render("New Game", True, (255, 255, 255))
        self.surface.blit(new_text, (new_game_rect.centerx - new_text.get_width() // 2,
                                     new_game_rect.centery - new_text.get_height() // 2))

        # Save files list section
        list_y = 130
        list_height = self.height - list_y - 10
        list_width = self.width - 120

        # Draw list background
        pygame.draw.rect(self.surface, (30, 30, 50), (60, list_y, list_width, list_height))
        pygame.draw.rect(self.surface, (80, 80, 120), (60, list_y, list_width, list_height), 2)

        # Draw save files list with scrolling
        item_height = 42
        max_visible = list_height // item_height

        if self.savefiles:
            save_file_rects = []
            for i in range(self.scroll_offset, min(self.scroll_offset + max_visible, len(self.savefiles))):
                display_index = i - self.scroll_offset
                y = list_y + 5 + display_index * item_height

                savefile = self.savefiles[i]
                rect = pygame.Rect(65, y, list_width - 40, item_height - 5)

                # Draw selection highlight background
                if i == self.selected_index:
                    pygame.draw.rect(self.surface, (80, 80, 140), rect)
                else:
                    pygame.draw.rect(self.surface, (40, 40, 60), rect)

                # Draw border around each save file entry
                pygame.draw.rect(self.surface, (100, 100, 150), rect, 2)

                # Draw savefile info with larger font
                info = savefile['display_name']
                text = self.font_savefile.render(info, True, (200, 200, 200))
                self.surface.blit(text, (75, y + 8))

                save_file_rects.append((i, rect))

            # Draw scrollbar if needed
            if len(self.savefiles) > max_visible:
                scrollbar_x = self.width - 65
                scrollbar_height = list_height - 10
                scroll_fraction = self.scroll_offset / len(self.savefiles)
                thumb_height = max(20, scrollbar_height * (max_visible / len(self.savefiles)))
                thumb_y = list_y + 5 + scroll_fraction * (scrollbar_height - thumb_height)

                pygame.draw.rect(self.surface, (60, 60, 80), (scrollbar_x, list_y + 5, 10, scrollbar_height))
                pygame.draw.rect(self.surface, (100, 150, 200), (scrollbar_x, thumb_y, 10, thumb_height))
        else:
            no_saves = self.font_normal.render("No save files found", True, (150, 150, 150))
            self.surface.blit(no_saves, (self.width // 2 - no_saves.get_width() // 2, list_y + 60))
            save_file_rects = []

        pygame.display.flip()
        return input_rect, new_game_rect, save_file_rects

    def run(self):
        """Run the dialog and return the user's choice.

        Returns:
            tuple: ('load', filepath) or ('new', seed)
        """
        self.setup_pygame()
        self.load_savefiles()

        running = True
        while running:
            input_rect, new_game_rect, save_file_rects = self.draw()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._safe_quit()
                    return None

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if input_rect.collidepoint(event.pos):
                        self.seed_input_active = True
                    elif new_game_rect.collidepoint(event.pos):
                        # Start new game with current seed
                        try:
                            seed = int(self.seed_input) if self.seed_input else 1
                            self._safe_quit()
                            return ('new', seed)
                        except ValueError:
                            self.seed_input = "1"
                    else:
                        self.seed_input_active = False
                        # Check if clicked on a savefile
                        for i, rect in save_file_rects:
                            if rect.collidepoint(event.pos):
                                self._safe_quit()
                                return ('load', self.savefiles[i]['path'])

                if event.type == pygame.MOUSEWHEEL:
                    # Scroll the savefile list
                    if event.y > 0:  # Scroll up
                        self.scroll_offset = max(0, self.scroll_offset - 1)
                    else:  # Scroll down
                        max_visible = (self.height - 140) // 35
                        self.scroll_offset = min(len(self.savefiles) - max_visible, self.scroll_offset + 1)

                if event.type == pygame.KEYDOWN:
                    if self.seed_input_active:
                        if event.key == pygame.K_BACKSPACE:
                            self.seed_input = self.seed_input[:-1]
                        elif event.key == pygame.K_RETURN:
                            try:
                                seed = int(self.seed_input) if self.seed_input else 1
                                self._safe_quit()
                                return ('new', seed)
                            except ValueError:
                                self.seed_input = "1"
                        elif event.unicode.isdigit():
                            if len(self.seed_input) < 10:
                                self.seed_input += event.unicode
                    elif event.key == pygame.K_ESCAPE:
                        self._safe_quit()
                        return None
                    elif event.key == pygame.K_UP and self.savefiles:
                        self.selected_index = max(-1, self.selected_index - 1)
                    elif event.key == pygame.K_DOWN and self.savefiles:
                        self.selected_index = min(len(self.savefiles) - 1, self.selected_index + 1)
                    elif event.key == pygame.K_RETURN and self.selected_index >= 0:
                        self._safe_quit()
                        return ('load', self.savefiles[self.selected_index]['path'])

            self.clock.tick(60)  # 60 FPS
