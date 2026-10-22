"""The inside of an outpost, as a screen that fills the whole window (SPACE with the outpost targeted, Esc leaves it).

It is not a modal dialog: the host (main) draws it alone, without the cockpit behind it, and keeps the game running
while it is open, so the time instrument, drawn over it by the host, shows time passing. The window is split in two.
On the left, the name of the outpost, and under it, smaller, the world, star and political entity it is in, then a radio
group of four buttons (Report, Cargo, Missions, Leave): one is always selected, and Report is the one selected when the
screen opens; they do nothing yet. The selected one is filled with the accent colour. On the right, the picture of the
outpost (common/resources/backgrounds, the files named outpost*), chosen from the outpost's seed, so the same outpost
always shows the same picture; faded dark. At the top left of the right side, the dockmaster on duty: the portrait, the
full name with its title beside it, and under the name the age and the role.
"""

from __future__ import annotations
import os
import random
from typing import TYPE_CHECKING, List, Optional, Tuple
import pygame

from common.paths import resource_path
from graphics.fallback_font import FallbackFont
from .dialog import Dialog, DialogResult, is_cancel
from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, BUTTON_FILL, TEXT_COLOR

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.person import Person

NOMINAL_SIZE = 800  # the base class wants a logical size; this dialog lays out at the window's size instead
BUTTON_LABELS = ('Report', 'Cargo', 'Missions', 'Leave')
SELECTED_TEXT_COLOR = (9, 17, 21)  # dark text on the accent fill of the selected button
PICTURE_PREFIX = 'outpost'
PICTURE_FADE = 0.7  # how much of the picture is covered by black: 0 is the picture as it is, 1 is black
LEFT_FADE = 0.6  # the same for the cockpit texture behind the buttons, which the instruments show darkened too
LEFT_FRACTION = 0.16  # the left block's share of the window's width
LEFT_MIN_WIDTH = 150
BUTTON_HEIGHT_FRACTION = 0.05  # of the window's height
OFFICER_PORTRAIT_FRACTION = 0.2  # the portrait's box, of the window's height
BEZEL_FRACTION = 0.012  # the thickness of the portrait's frame, of the window's height
BEZEL_BORDER = 16  # the corner size of textures/bezel.png (made by tools/generate_bezel_texture.py)


def _pictures() -> List[str]:
    """The files of common/resources/backgrounds whose names start with PICTURE_PREFIX, in a fixed order."""
    folder = resource_path('backgrounds')
    return sorted(
        os.path.join(folder, name) for name in os.listdir(folder)
        if name.startswith(PICTURE_PREFIX) and name.lower().endswith(('.jpg', '.jpeg', '.png'))
    )


def _cover(image: pygame.Surface, size: Tuple[int, int]) -> pygame.Surface:
    """`image` scaled to fill `size` (keeping its proportions), cropped to its middle."""
    width, height = size
    scale = max(width / image.get_width(), height / image.get_height())
    scaled = pygame.transform.smoothscale(image, (round(image.get_width() * scale), round(image.get_height() * scale)))
    crop = pygame.Rect(0, 0, width, height)
    crop.center = scaled.get_rect().center
    return scaled.subsurface(crop).copy()


def _darken(image: pygame.Surface, fraction: float) -> pygame.Surface:
    """`image` with `fraction` of it covered by black (0 leaves it as it is, 1 makes it black)."""
    shade = pygame.Surface(image.get_size())
    shade.fill((0, 0, 0))
    shade.set_alpha(round(255 * fraction))
    image.blit(shade, (0, 0))
    return image


def _wrap(text: str, font: pygame.font.Font, width: int) -> List[str]:
    """`text` split at its spaces into lines of at most `width` pixels (a word longer than that stays whole)."""
    lines: List[str] = []
    line = ''
    for word in text.split():
        candidate = f'{line} {word}' if line else word
        if line and font.size(candidate)[0] > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def _margin(height: int) -> int:
    return max(10, height // 50)


def _button_size(height: int) -> Tuple[int, int]:
    """The height of a radio button, and the gap between two buttons (also the gap the officer's portrait keeps)."""
    button_height = max(24, int(height * BUTTON_HEIGHT_FRACTION))
    return button_height, max(4, button_height // 5)


def _nine_slice(texture: pygame.Surface, border: int, size: Tuple[int, int], thickness: int) -> pygame.Surface:
    """A frame of `size` made from `texture`: its corners (`border` px in the texture) are drawn `thickness` px, its
    edges stretched to fit, and its centre is left clear."""
    width, height = size
    texture_w, texture_h = texture.get_size()
    source_x = (0, border, texture_w - border, texture_w)
    source_y = (0, border, texture_h - border, texture_h)
    target_x = (0, thickness, width - thickness, width)
    target_y = (0, thickness, height - thickness, height)
    result = pygame.Surface(size, pygame.SRCALPHA)
    for column in range(3):
        for row in range(3):
            target_w = target_x[column + 1] - target_x[column]
            target_h = target_y[row + 1] - target_y[row]
            if (column, row) == (1, 1) or target_w <= 0 or target_h <= 0:
                continue
            piece = texture.subsurface(pygame.Rect(source_x[column], source_y[row],
                                                   source_x[column + 1] - source_x[column],
                                                   source_y[row + 1] - source_y[row]))
            result.blit(pygame.transform.smoothscale(piece, (target_w, target_h)), (target_x[column], target_y[row]))
    return result


def _draw_wrapped(surface: pygame.Surface, x: int, width: int, top: int, text: str,
                  font: FallbackFont, colour: Tuple[int, int, int]) -> int:
    """`text` drawn at x, from `top`, wrapped to `width`. Returns the y under it."""
    for line in _wrap(text, font, width):
        surface.blit(font.render(line, True, colour), (x, top))
        top += font.get_linesize()
    return top


class OutpostScreenDialog(Dialog):
    """The screen of `outpost` (galaxies/outpost.py): its name, then the world, star and political entity it is in,
    then the radio group. Its picture is chosen from its seed, so the same outpost always shows the same picture.
    Esc (or a right-click) leaves it: the result is ('close', None). Up and Down, or a click, select a button of the
    radio group."""

    OPEN_SOUND = 'ui_open'
    CLOSE_SOUND = 'ui_close'

    def __init__(self, outpost: Outpost) -> None:
        super().__init__(NOMINAL_SIZE, NOMINAL_SIZE)
        self.outpost_name: str = outpost.name
        system = outpost.planet.parent_orbit.parent_stellar_system
        self.details: List[str] = [outpost.planet.name, system.star.name, system.political_entity.name]
        self.officer: Optional[Person] = outpost.dockmaster  # read at each draw: the shift may change while it is open
        self._portrait: Optional[pygame.Surface] = None  # the officer's portrait, made for _portrait_source and _box
        self._portrait_source: Optional[pygame.Surface] = None
        self._portrait_box: int = 0
        self._frame_texture: Optional[pygame.Surface] = None  # textures/bezel.png, loaded at the first draw
        self._frame_image: Optional[pygame.Surface] = None  # the frame made for _frame_key
        self._frame_key: Optional[Tuple[Tuple[int, int], int]] = None
        self.selected: int = 0  # the radio group: exactly one button is selected, Report at first
        self._button_rects: List[pygame.Rect] = []  # where the buttons were last drawn
        pictures = _pictures()
        self._picture_file: Optional[str] = random.Random(outpost.seed).choice(pictures) if pictures else None
        self._picture: Optional[pygame.Surface] = None  # the faded picture, made for _picture_size
        self._picture_size: Optional[Tuple[int, int]] = None
        self._left: Optional[pygame.Surface] = None  # the cockpit texture covering the left block, made for _left_size
        self._left_size: Optional[Tuple[int, int]] = None

    def _panel_layout(self, window_size: Tuple[int, int]) -> Tuple[pygame.Rect, float]:
        """The whole window, at its own scale: nothing is centred or scaled down."""
        return pygame.Rect(0, 0, *window_size), 1.0

    def render_panel(self, window_size: Tuple[int, int]) -> Tuple[pygame.Surface, pygame.Rect]:
        panel = pygame.Surface(window_size, pygame.SRCALPHA)
        self.draw(panel)
        return panel, panel.get_rect()

    def compose_overlay(self, window_size: Tuple[int, int]) -> pygame.Surface:
        """The screen itself: the host draws it in place of the cockpit, so there is no backdrop to dim."""
        return self.render_panel(window_size)[0]

    def _faded_picture(self, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        """The chosen picture covering `size`, darkened, made once per size."""
        if self._picture_file is None or size[0] <= 0 or size[1] <= 0:
            return None
        if self._picture is None or self._picture_size != size:
            self._picture = _darken(_cover(pygame.image.load(self._picture_file).convert(), size), PICTURE_FADE)
            self._picture_size = size
        return self._picture

    def _left_background(self, size: Tuple[int, int]) -> pygame.Surface:
        """The cockpit texture, as the instruments' background, covering the left block; made once per size."""
        if self._left is None or self._left_size != size:
            texture = pygame.image.load(resource_path('textures', 'cockpit_background.png')).convert()
            self._left = _darken(_cover(texture, size), LEFT_FADE)
            self._left_size = size
        return self._left

    def draw(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        left_width = max(LEFT_MIN_WIDTH, int(width * LEFT_FRACTION))
        left = pygame.Rect(0, 0, left_width, height)
        right = pygame.Rect(left_width, 0, width - left_width, height)

        surface.blit(self._left_background(left.size), left)
        buttons_top = self._draw_name(surface, left, height)
        self._draw_buttons(surface, left, height, buttons_top)

        picture = self._faded_picture(right.size)
        if picture is not None:
            surface.blit(picture, right)
        else:
            surface.fill((0, 0, 0), right)
        self._draw_officer(surface, right, height)

    def _draw_name(self, surface: pygame.Surface, left: pygame.Rect, height: int) -> int:
        """The outpost's name, and under it, smaller, its world, star and political entity, all in the left block.
        Returns the y where the buttons start: a margin under them."""
        margin = _margin(height)
        x, width = left.left + margin, left.width - 2 * margin
        y = _draw_wrapped(surface, x, width, margin, self.outpost_name, title_font(max(12, height // 40)), ACCENT)
        y += max(4, margin // 3)  # a little more room between the name and the details
        for detail in self.details:
            y = _draw_wrapped(surface, x, width, y, detail, body_font(max(16, height // 40)), TEXT_COLOR)
        return y + margin

    def _scaled_portrait(self, box: int) -> Optional[pygame.Surface]:
        """The com officer's portrait, fitted in a box x box square, made again when the officer or the box changes."""
        icon = self.officer.icon if self.officer is not None else None
        if icon is None:
            return None
        if self._portrait is None or self._portrait_source is not icon or self._portrait_box != box:
            scale = min(box / icon.get_width(), box / icon.get_height())
            self._portrait = pygame.transform.smoothscale(
                icon, (round(icon.get_width() * scale), round(icon.get_height() * scale)))
            self._portrait_source = icon
            self._portrait_box = box
        return self._portrait

    def _frame(self, size: Tuple[int, int], thickness: int) -> pygame.Surface:
        """The bezel texture as a frame of `size` (see _nine_slice), made again when either changes."""
        if self._frame_texture is None:
            self._frame_texture = pygame.image.load(resource_path('textures', 'bezel.png')).convert_alpha()
        if self._frame_key != (size, thickness):
            self._frame_image = _nine_slice(self._frame_texture, BEZEL_BORDER, size, thickness)
            self._frame_key = (size, thickness)
        return self._frame_image

    def _draw_officer(self, surface: pygame.Surface, right: pygame.Rect, height: int) -> None:
        """The com officer, at the top left of the right block: the portrait, and beside it the full name (with its
        title), and under the name the age and the role. Nothing is drawn while there is no com officer."""
        if self.officer is None:
            return
        margin = _margin(height)
        box = int(height * OFFICER_PORTRAIT_FRACTION)
        top = right.top + margin
        x = right.left + margin
        portrait = self._scaled_portrait(box)
        if portrait is not None:
            # the frame goes round the picture, outside it, so the picture is inset by its thickness
            thickness = max(4, int(height * BEZEL_FRACTION))
            frame = portrait.get_rect(topleft=(x + thickness, top + thickness))
            surface.blit(self._frame(frame.inflate(thickness * 2, thickness * 2).size, thickness), (x, top))
            surface.blit(portrait, frame)
            x = frame.right + thickness + _button_size(height)[1]  # the same gap as between two buttons
        width = right.right - margin - x
        name_font = title_font(max(12, height // 40))
        y = _draw_wrapped(surface, x, width, top, self.officer.get_full_name(), name_font, ACCENT)
        role = self.officer.role.name
        _draw_wrapped(surface, x, width, y, f'{self.officer.age} years old, {role}',
                      body_font(max(16, height // 40)), TEXT_COLOR)

    def _draw_buttons(self, surface: pygame.Surface, left: pygame.Rect, height: int, top: int) -> None:
        margin = _margin(height)
        button_height, gap = _button_size(height)
        font = body_font(max(13, height // 50))

        self._button_rects = []
        for index, label in enumerate(BUTTON_LABELS):
            rect = pygame.Rect(left.left + margin, top, left.width - 2 * margin, button_height)
            self._button_rects.append(rect)
            if index == self.selected:
                pygame.draw.rect(surface, ACCENT, rect)
                caption = font.render(label, True, SELECTED_TEXT_COLOR)
            else:
                pygame.draw.rect(surface, BUTTON_FILL, rect)
                pygame.draw.rect(surface, ACCENT_DIM, rect, 1)
                caption = font.render(label, True, TEXT_COLOR)
            surface.blit(caption, caption.get_rect(center=rect.center))
            top += button_height + gap

    def _select(self, index: int) -> None:
        self.selected = index

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if event.type == pygame.QUIT:
            return ('exit', None)
        if is_cancel(event):
            return ('close', None)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB):
            backwards = event.key == pygame.K_UP or (event.key == pygame.K_TAB and event.mod & pygame.KMOD_SHIFT)
            self._select((self.selected + (-1 if backwards else 1)) % len(BUTTON_LABELS))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self._button_rects):
                if rect.collidepoint(event.pos):
                    self._select(index)
        return None
