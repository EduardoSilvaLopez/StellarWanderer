"""The inside of an outpost, as a screen that fills the whole window (SPACE with the outpost targeted; the Leave button
leaves it).

It is not a modal dialog: the host (main) draws it alone, without the cockpit behind it, and keeps the game running
while it is open (the pilot is `inside` the outpost, the other state of the game: see Player), so the time instrument,
drawn over it by the host, shows time passing. Esc is not for the screen: it opens the starting dialog, which is drawn
over it, as it is over the cockpit. The window is split in two.
On the left, the name of the outpost, and under it, smaller, the world, star and political entity it is in, then a radio
group of five buttons (Report, Cargo, Missions, Chat, Leave): one is always selected, and Report is the one selected
when the screen opens. The selected one is filled with the accent colour. What it does is what the right side shows:
Report starts the OutpostReport conversation, Cargo shows the cargo, Missions the outpost's missions (OutpostMissions,
drawn over the picture), and Chat the people of the outpost who can be chatted with now (StaffList, one card each,
on the right of three areas; the other two are reserved, nothing is drawn in them yet). On the right, the
picture of the outpost
(common/resources/backgrounds, the files named outpost*), chosen from the outpost's seed, so the same outpost always
shows the same picture; faded dark. At the top left of the right side, the dockmaster on duty: the portrait, the full
name with its title beside it, and under the name the age and the role.

The conversation of the selected option shows its messages here, not in a dialog over the cockpit: the screen is the
`show` of the conversation (see Conversation). The title and the text of the message are drawn in a dark panel under
the dockmaster. Its answers are translucent rectangles, the last at the bottom of the right side, tinted while the mouse
is over one; they are answered with the mouse, the number keys or Enter. A message asked while another is shown waits
its turn. Selecting another option, or leaving the screen, closes the conversation.
"""

from __future__ import annotations
import os
import random
from typing import TYPE_CHECKING, List, Optional, Tuple
import pygame

from common import audio
from common.paths import resource_path
from graphics.fallback_font import FallbackFont
from .dialog import Dialog, DialogResult
from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, BUTTON_FILL, TEXT_COLOR
from .messages import Message, ResultCallback
from .mission_board_dialog import OutpostMissions, PAGE_KEYS, SCROLL_BAR_GAP
from .scroll_bar import ScrollBar
from .staff_list import StaffList

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.conversation import Conversation
    from galaxies.people.person import Person

NOMINAL_SIZE = 800  # the base class wants a logical size; this dialog lays out at the window's size instead
BUTTON_LABELS = ('Report', 'Cargo', 'Missions', 'Chat', 'Leave')
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
MESSAGE_PANEL_SHADE = (0, 0, 0, 175)  # the message's panel, over the picture
MESSAGE_PANEL_FRACTION = 0.6  # the panel's share of the right block's width
MESSAGE_PANEL_MIN_WIDTH = 420
ANSWER_HEIGHT_FRACTION = 0.034  # of the window's height
CARGO_PICTURE_FRACTION = 0.36  # the ship's picture in the cargo view, as a share of the window's height
ANSWER_SHADE = (0, 0, 0, 110)  # an answer is a translucent rectangle over the picture...
ANSWER_HOVER_SHADE = (94, 234, 212, 90)  # ...tinted with the accent colour while the mouse is over it
CHAT_PEOPLE_FRACTION = 0.42  # the width of Chat's people panel, as a share of the window's height
TIME_DISPLAY_BOTTOM = 0.115  # the ship time display's bottom (graphics/instruments/clock.py), of the window's height


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
    The Leave button leaves it: the result is ('close', None). If the outpost is still repairing the ship, it asks
    first, in the panel, and Yes leaves with the repairs done so far (Outpost.stop_repair). While the pilot is inside,
    the ship is docked (Ship.dock), so nothing of it is consumed.

    Keyboard: Tab (Shift+Tab back) moves the focus over the radio group, Leave, the answers of the shown message and,
    while Cargo is selected, the −, + and ++ of its rows; Enter or Space press the focused button: select an option,
    leave, answer, give or take one unit, or fill a supply. The focus is drawn only while the keyboard is in use. Up and
    Down select the options directly, and the number keys answer.

    Cargo (selected, without a conversation): the ship's picture, the room left in the hold, and a row for each supply
    (spaceships/cargo_hold.py SUPPLIES), with − and + to give and take one unit, and ++ to fill it to its maximum in one
    press, all within the hold's maxima. The outpost has what it takes: its stock is not limited.

    Missions (selected): the outpost's OutpostMissions, the "Available" offers and the "Taken" missions, each the latest
    deadline first. A click opens a detail, where an offer is accepted or a taken mission delivered. Backspace or a
    right-click goes back from a detail; Page Up and Page Down and the wheel scroll the list. The arrow keys still
    select options.

    Chat (selected): the people listed now (Outpost.available_staff, see StaffList), in a dark panel on the right of
    the block. A click selects a card; Tab goes over the cards and Enter or Space selects the focused one. The middle
    and the right areas are reserved, nothing is drawn in them yet."""

    OPEN_SOUND = 'ui_open'
    CLOSE_SOUND = 'ui_close'

    def __init__(self, outpost: Outpost) -> None:
        super().__init__(NOMINAL_SIZE, NOMINAL_SIZE)
        self.outpost: Outpost = outpost
        self.outpost_name: str = outpost.name
        system = outpost.planet.parent_orbit.parent_stellar_system
        self.details: List[str] = [outpost.planet.name, system.star.name, system.political_entity.name]
        # The dockmaster on duty when the screen opens, who is the one that talks: their name and age are read at each
        # draw, but the shift changing while the screen is open does not change who is shown.
        self.officer: Optional[Person] = outpost.dockmaster
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

        self.conversation: Optional[Conversation] = None  # the one of the selected option, while there is one
        self._queue: List[Tuple[Message, Optional[ResultCallback]]] = []  # messages asked while another is shown
        self._shown: Optional[Tuple[Message, Optional[ResultCallback]]] = None  # the message in the panel
        self._answer_rects: List[pygame.Rect] = []  # where the answers of the shown message were last drawn
        self._answer_hover: Optional[int] = None  # the answer under the mouse at the last draw, if any
        # The button the keyboard is on (Tab), as a token: ('option', index), ('cargo', row, -1 or 1) for a row's − or
        # +, ('fill', row) for its ++, or ('answer', index). See _focus_targets. It is drawn only while the keyboard is
        # the one in use.
        self._focus: tuple = ('option', 0)
        # the −, + and ++ of each cargo row, and the row
        self._cargo_rects: List[Tuple[pygame.Rect, pygame.Rect, pygame.Rect, int]] = []
        self._ship_source: Optional[pygame.Surface] = None  # the ship's picture, loaded once
        self._ship_image: Optional[pygame.Surface] = None  # it, scaled for the cargo view, made for _ship_image_size
        self._ship_image_size: Optional[Tuple[int, int]] = None
        self._missions: Optional[OutpostMissions] = None  # the list of the Missions option, made when it is selected
        self._chat: Optional[StaffList] = None  # the people of the Chat option, made when it is selected
        self._chat_areas: List[pygame.Rect] = []  # the three areas of Chat, where they were last drawn
        self._focus_visible: bool = False
        self._asking_to_leave: bool = False  # the question of leaving with the repair going is in the panel
        self._leaving: bool = False  # it was answered Yes: the next event ends the screen
        # local: the player needs the missions, which need the outposts, which need the dialogs
        from galaxies.people.player import current_player
        self.ship = current_player.ship  # docked by the player's enter_outpost, which comes before this screen
        self._open_option()
        # The ship's levels as they are when the screen opens (maintenance, and energy as a share): the cargo view shows
        # them, and they are not updated while the screen is open.
        self._levels: Tuple[float, float] = (self.ship.maintenance, self.ship.energy / self.ship.energy_max)

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
        if self._shows_cargo():
            self._draw_cargo(surface, right, height)
        elif self._shows_missions():
            self._draw_missions(surface, right, height)
        elif self._shows_chat():
            self._draw_chat(surface, right, height)
        else:
            self._cargo_rects = []
            officer_bottom = self._draw_officer(surface, right, height)
            self._draw_message(surface, right, height, officer_bottom + _margin(height))

    def _cargo_picture(self, height: int, width: int) -> pygame.Surface:
        """The ship's picture, fitted in the cargo view: at most a share of the window's
        height, and at most the width. Made again when the size changes."""
        if self._ship_source is None:
            self._ship_source = pygame.image.load(
                resource_path('presentation', 'outpost.background.cargo.1.jpg')).convert()
        fit_height = int(height * CARGO_PICTURE_FRACTION)
        fit_width = min(width, int(fit_height * 16 / 9))
        size = (fit_width, int(fit_width * 9 / 16))
        if self._ship_image is None or self._ship_image_size != size:
            self._ship_image = pygame.transform.smoothscale(self._ship_source, size)
            self._ship_image_size = size
        return self._ship_image

    def _draw_cargo(self, surface: pygame.Surface, right: pygame.Rect, height: int) -> None:
        """The cargo: the ship's picture, the room left in the hold, and a row for each supply (SUPPLIES, in the hold's
        module), with − and + to give and take one unit, and ++ to fill it to its maximum. There is no conversation
        here."""
        from spaceships.cargo_hold import SUPPLIES  # local: the ship's hold is the game's, not the dialogs'
        margin = _margin(height)
        font = body_font(max(14, height // 48))
        row_height, gap = _button_size(height)
        button_width = row_height * 2
        hold = self.ship.cargo_hold

        picture = self._cargo_picture(height, right.width - 2 * margin)
        left, top = right.left + margin, right.top + margin
        surface.blit(picture, (left, top))
        pygame.draw.rect(surface, ACCENT_DIM, (left, top, picture.get_width(), picture.get_height()), 1)
        width = picture.get_width()
        y = top + picture.get_height() + margin
        bar_height = max(8, height // 90)
        for label, fraction in (('Maintenance', self._levels[0]), ('Energy', self._levels[1])):
            caption = font.render(f"{label}   {fraction:.0%}", True, TEXT_COLOR)
            surface.blit(caption, (left, y))
            y += font.get_linesize()
            bar = pygame.Rect(left, y, width, bar_height)
            pygame.draw.rect(surface, BUTTON_FILL, bar)
            pygame.draw.rect(surface, ACCENT, (left, y, int(width * max(0.0, min(1.0, fraction))), bar_height))
            pygame.draw.rect(surface, ACCENT_DIM, bar, 1)
            y += bar_height + gap
        y += margin // 2
        room = f"Room in the hold: {hold.free_capacity():.0f} of {hold.capacity} kg"
        surface.blit(font.render(room, True, TEXT_COLOR), (left, y))
        y += font.get_linesize() + gap

        self._cargo_rects = []
        for k, supply in enumerate(SUPPLIES):
            row = pygame.Rect(left, y, width, row_height)
            shade = pygame.Surface(row.size, pygame.SRCALPHA)
            shade.fill(ANSWER_SHADE)
            surface.blit(shade, row)
            fill = pygame.Rect(row.right - button_width, row.top, button_width, row_height)
            plus = pygame.Rect(fill.left - gap - button_width, row.top, button_width, row_height)
            minus = pygame.Rect(plus.left - gap - button_width, row.top, button_width, row_height)
            buttons = ((minus, ('cargo', k, -1), '-'), (plus, ('cargo', k, 1), '+'), (fill, ('fill', k), '++'))
            for rect, token, sign in buttons:
                focused = self._focus_visible and self._focus == token
                pygame.draw.rect(surface, BUTTON_FILL, rect)
                pygame.draw.rect(surface, ACCENT if focused else ACCENT_DIM, rect, 2 if focused else 1)
                caption = font.render(sign, True, ACCENT if focused else TEXT_COLOR)
                surface.blit(caption, caption.get_rect(center=rect.center))
            stock = getattr(hold, supply.key)
            maximum = supply.maximum(hold)
            amount = f"{int(stock)}" if supply.whole else f"{stock:.1f}"
            value = f"{supply.label}   {amount} / {maximum:g} {supply.unit}"
            caption = font.render(value, True, TEXT_COLOR)
            surface.blit(caption, (row.left + margin, row.centery - caption.get_height() // 2))
            self._cargo_rects.append((minus, plus, fill, k))
            y += row_height + gap

    def _draw_chat(self, surface: pygame.Surface, right: pygame.Rect, height: int) -> None:
        """Chat: three areas in the block, inside its margin and under the ship time display. The people are drawn in a
        dark panel on the right, CHAT_PEOPLE_FRACTION of the height wide (StaffList); tags and conversation share the
        left and are only reserved for now."""
        margin = _margin(height)
        top = max(right.top + margin, int(height * TIME_DISPLAY_BOTTOM) + margin)
        area = pygame.Rect(right.left + margin, top, right.width - 2 * margin, right.bottom - margin - top)
        people_width = min(int(height * CHAT_PEOPLE_FRACTION), area.width - 2 * margin)
        people = pygame.Rect(area.right - people_width, area.top, people_width, area.height)
        left_width = people.left - margin - area.left
        tags_width = (left_width - margin) // 2
        tags = pygame.Rect(area.left, area.top, tags_width, area.height)
        conversation = pygame.Rect(tags.right + margin, area.top, left_width - tags_width - margin, area.height)
        self._chat_areas = [tags, conversation, people]

        shade = pygame.Surface(people.size, pygame.SRCALPHA)
        shade.fill(MESSAGE_PANEL_SHADE)
        surface.blit(shade, people)
        pygame.draw.rect(surface, ACCENT_DIM, people, 1)
        inner = people.inflate(-2 * margin, -2 * margin)
        self._chat.place(pygame.Rect(inner.left, inner.top, inner.width - SCROLL_BAR_GAP - ScrollBar.MIN_WIDTH,
                                     inner.height))
        self._chat.draw(surface, self._focus[1] if self._focus_visible and self._focus[0] == 'person' else None)

    def _draw_missions(self, surface: pygame.Surface, right: pygame.Rect, height: int) -> None:
        """The missions of the outpost (OutpostMissions) in a dark panel over the block, its scroll bar at the right,
        inside the margin. The panel starts under the ship time display (TIME_DISPLAY_BOTTOM), drawn over the block."""
        margin = _margin(height)
        top = max(right.top + margin, int(height * TIME_DISPLAY_BOTTOM) + margin)
        panel = pygame.Rect(right.left + margin, top, right.width - 2 * margin, right.bottom - margin - top)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill(MESSAGE_PANEL_SHADE)
        surface.blit(shade, panel)
        pygame.draw.rect(surface, ACCENT_DIM, panel, 1)
        self._missions.place(panel.inflate(-2 * margin, -2 * margin))  # the columns, each with its scroll bar inside
        self._missions.draw_content(surface)

    def _press_cargo(self, k: int, delta: int) -> None:
        """One unit of supply `k` given (delta < 0) or taken (delta > 0), within the hold's limits (CargoHold.load)."""
        self._move_cargo(k, delta, 1)

    def _fill_cargo(self, k: int) -> None:
        """Supply `k` taken up to its maximum in one press: what the hold lacks of it, within its room
        (CargoHold.load)."""
        from spaceships.cargo_hold import SUPPLIES  # local: as in _draw_cargo
        hold = self.ship.cargo_hold
        supply = SUPPLIES[k]
        self._move_cargo(k, 1, supply.maximum(hold) - getattr(hold, supply.key))

    def _move_cargo(self, k: int, delta: int, units: float) -> None:
        """`units` of supply `k` given (delta < 0) or taken (delta > 0), within the hold's limits; the reputation
        follows what actually moved."""
        from spaceships.cargo_hold import SUPPLIES  # local: as in _draw_cargo
        supply = SUPPLIES[k]
        hold = self.ship.cargo_hold
        quantity = hold.load(supply, units) if delta > 0 else hold.unload(supply, units)
        self.ship.owner.those_who_share.adjust_reputation_by_supply(supply.key, -delta*quantity)
        audio.play('ui_click')

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

    def _draw_officer(self, surface: pygame.Surface, right: pygame.Rect, height: int) -> int:
        """The dockmaster, at the top left of the right block: the portrait, and beside it the full name (with its
        title), and under the name the age and the role. Nothing is drawn while there is no dockmaster. Returns the y
        under what was drawn."""
        margin = _margin(height)
        top = right.top + margin
        if self.officer is None:
            return top
        box = int(height * OFFICER_PORTRAIT_FRACTION)
        x = right.left + margin
        bottom = top
        portrait = self._scaled_portrait(box)
        if portrait is not None:
            # the frame goes round the picture, outside it, so the picture is inset by its thickness
            thickness = max(4, int(height * BEZEL_FRACTION))
            frame = portrait.get_rect(topleft=(x + thickness, top + thickness))
            outer = frame.inflate(thickness * 2, thickness * 2)
            surface.blit(self._frame(outer.size, thickness), (x, top))
            surface.blit(portrait, frame)
            x = frame.right + thickness + _button_size(height)[1]  # the same gap as between two buttons
            bottom = outer.bottom
        width = right.right - margin - x
        name_font = title_font(max(12, height // 40))
        y = _draw_wrapped(surface, x, width, top, self.officer.get_full_name(), name_font, ACCENT)
        role = self.officer.role.name
        y = _draw_wrapped(surface, x, width, y, f'{self.officer.age} years old, {role}',
                          body_font(max(16, height // 40)), TEXT_COLOR)
        return max(bottom, y)

    def _draw_message(self, surface: pygame.Surface, right: pygame.Rect, height: int, top: int) -> None:
        """The message being shown, at the left of the right block. Its title and its text, in paragraphs, are in a dark
        panel from `top`, with the height they need. Its answers, one for each button and numbered, are translucent
        rectangles under each other, the last one at the bottom of the block (see _draw_answers)."""
        self._answer_rects = []
        self._answer_hover = None
        if self._shown is None:
            return
        message = self._shown[0]
        margin = _margin(height)
        pad = margin
        wanted_width = max(MESSAGE_PANEL_MIN_WIDTH, int(right.width * MESSAGE_PANEL_FRACTION))
        panel_width = min(right.width - 2 * margin, wanted_width)
        inner_width = panel_width - 2 * pad
        heading = title_font(max(14, height // 36))
        body = body_font(max(14, height // 45))
        gap = _button_size(height)[1]

        title_lines = _wrap(message.title, heading, inner_width)
        paragraphs = [_wrap(paragraph, body, inner_width) for paragraph in message.paragraphs]
        text_height = sum(len(lines) * body.get_linesize() for lines in paragraphs)
        text_height += max(0, len(paragraphs) - 1) * (body.get_linesize() // 2)
        panel = pygame.Rect(right.left + margin, top, panel_width,
                            pad + len(title_lines) * heading.get_linesize() + gap + text_height + pad)

        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill(MESSAGE_PANEL_SHADE)
        surface.blit(shade, panel)
        pygame.draw.rect(surface, ACCENT_DIM, panel, 1)

        y = panel.top + pad
        for line in title_lines:
            surface.blit(heading.render(line, True, ACCENT), (panel.left + pad, y))
            y += heading.get_linesize()
        y += gap
        for number, lines in enumerate(paragraphs):
            if number:
                y += body.get_linesize() // 2
            for line in lines:
                surface.blit(body.render(line, True, TEXT_COLOR), (panel.left + pad, y))
                y += body.get_linesize()
        self._draw_answers(surface, right, height, panel.left, panel_width)

    def _draw_answers(self, surface: pygame.Surface, right: pygame.Rect, height: int, left: int, width: int) -> None:
        """The answers of the shown message, numbered, `width` wide from `left`: translucent rectangles close to each
        other, the last at the bottom of the block. The one under the mouse, or that has the keyboard focus, is tinted
        with the accent colour, and its text turns dark."""
        labels = self._shown[0].buttons
        margin = _margin(height)
        font = body_font(max(14, height // 48))
        answer_height = max(22, int(height * ANSWER_HEIGHT_FRACTION))
        gap = max(2, height // 400)
        top = right.bottom - margin - (len(labels) * answer_height + (len(labels) - 1) * gap)
        mouse = pygame.mouse.get_pos() if pygame.mouse.get_focused() else None
        for index, label in enumerate(labels):
            rect = pygame.Rect(left, top + index * (answer_height + gap), width, answer_height)
            self._answer_rects.append(rect)
            hovered = mouse is not None and rect.collidepoint(mouse)
            if hovered:
                self._answer_hover = index
            lit = hovered or (self._focus_visible and self._focus == ('answer', index))
            shade = pygame.Surface(rect.size, pygame.SRCALPHA)
            shade.fill(ANSWER_HOVER_SHADE if lit else ANSWER_SHADE)
            surface.blit(shade, rect)
            caption = font.render(f'{index + 1}. {label}', True, SELECTED_TEXT_COLOR if lit else TEXT_COLOR)
            surface.blit(caption, caption.get_rect(midleft=(rect.left + margin, rect.centery)))

    def _draw_buttons(self, surface: pygame.Surface, left: pygame.Rect, height: int, top: int) -> None:
        margin = _margin(height)
        button_height, gap = _button_size(height)
        font = body_font(max(13, height // 50))

        self._button_rects = []
        for index, label in enumerate(BUTTON_LABELS):
            rect = pygame.Rect(left.left + margin, top, left.width - 2 * margin, button_height)
            self._button_rects.append(rect)
            focused = self._focus_visible and self._focus == ('option', index)
            if index == self.selected:
                pygame.draw.rect(surface, ACCENT, rect)
                caption = font.render(label, True, SELECTED_TEXT_COLOR)
                if focused:  # a dark ring inside the accent fill
                    pygame.draw.rect(surface, SELECTED_TEXT_COLOR, rect.inflate(-6, -6), 2)
            else:
                pygame.draw.rect(surface, BUTTON_FILL, rect)
                pygame.draw.rect(surface, ACCENT if focused else ACCENT_DIM, rect, 2 if focused else 1)
                caption = font.render(label, True, ACCENT if focused else TEXT_COLOR)
            surface.blit(caption, caption.get_rect(center=rect.center))
            top += button_height + gap

    # region Conversations
    def _open_option(self) -> None:
        """Starts what the selected option shows: Report starts the report conversation, the others show nothing yet."""
        if BUTTON_LABELS[self.selected] == 'Report' and self.officer is not None:
            # local: the conversation needs the outpost and the people, which need the dialogs
            from galaxies.people.conversations.outpost_report import OutpostReport
            from galaxies.people.player import current_player
            self.conversation = OutpostReport(current_player, self.officer, self.outpost, self._show)
            self.conversation.start()
        elif BUTTON_LABELS[self.selected] == 'Missions':
            self._open_missions()
        elif BUTTON_LABELS[self.selected] == 'Chat':
            self._chat = StaffList(self.outpost)

    def _open_missions(self) -> None:
        """Missions: the board's offers are brought up to date, and their list is made (see OutpostMissions). The list
        is made again each time the option is selected, so it starts at the top."""
        import game_environment as gem  # local: the game's environment, not needed by the rest of this module
        self.outpost.mission_board.update_missions(gem.current_environment.date_time)
        self._missions = OutpostMissions(self.outpost.mission_board)

    def _after_conversation(self) -> None:
        """When the report is over (its conversation has closed, see OutpostReport._finish), Cargo is selected: the
        pilot goes on to the cargo. Nothing is shown for it yet."""
        if self.conversation is not None and self.conversation.is_closed:
            self.conversation = None
            self._select(BUTTON_LABELS.index('Cargo'))

    def _close_option(self) -> None:
        """Ends the conversation of the option, if one is going, and clears the messages of the panel."""
        if self.conversation is not None:
            self.conversation.close()
            self.conversation = None
        self._queue.clear()
        self._shown = None
        self._asking_to_leave = False

    def _show(self, message: Message, on_result: Optional[ResultCallback] = None) -> None:
        """What the conversation of the option calls instead of show_message (Conversation.show): the message goes to
        the panel at once, or waits for its turn if another is shown."""
        self._queue.append((message, on_result))
        if self._shown is None:
            self._next_message()

    def _next_message(self) -> None:
        self._shown = self._queue.pop(0) if self._queue else None
        self._answer_hover = None

    def _answer(self, index: int) -> None:
        """The answer `index` of the shown message: its callback is told, and the panel shows what the callback asked
        next, else the next message waiting, else nothing."""
        shown, self._shown = self._shown, None
        audio.play('ui_click')
        if shown is not None and shown[1] is not None:
            shown[1](index)
        self._focus = ('option', self.selected)
        if self._shown is None:
            self._next_message()

    def _answer_event(self, event: pygame.event.Event) -> bool:
        """Answers the shown message with the number keys or a click. True if it did."""
        count = len(self._shown[0].buttons)
        if event.type == pygame.KEYDOWN:
            number_keys = ((pygame.K_1, pygame.K_9), (pygame.K_KP1, pygame.K_KP9))
            for first, last in number_keys:
                if first <= event.key <= last and event.key - first < count:
                    self._answer(event.key - first)
                    return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self._answer_rects):
                if rect.collidepoint(event.pos):
                    self._answer(index)
                    return True
        return False
    # endregion

    def _try_leave(self) -> None:
        """The Leave button: the screen ends at once, or, if the outpost is still repairing the ship, the pilot is
        asked first."""
        if self._asking_to_leave:
            return
        if self.outpost.repair_due_at is not None:
            self._ask_to_leave()
        else:
            self._leaving = True

    def _ask_to_leave(self) -> None:
        """The outpost is still repairing the ship: the conversation is set aside, and the pilot is asked if they leave
        anyway, with only the repairs done so far."""
        self._close_option()
        self._asking_to_leave = True
        self._show(Message(
            title='Leaving',
            text="Your ship is not ready yet. If you leave now, it keeps only the repairs done so far."
                 "\n\nDo you want to leave anyway?",
            buttons=['Yes', 'No'],
        ), self._on_leave_answer)

    def _on_leave_answer(self, index: Optional[int]) -> None:
        """Yes: the repairs done so far are kept, and the screen ends. No: the option starts again."""
        import game_environment as gem  # local: the game's environment, not needed by the rest of this module
        self._asking_to_leave = False
        if index == 0:
            self.outpost.stop_repair(self.ship, gem.current_environment.date_time)
            self._leaving = True
        else:
            self._open_option()

    def _shows_cargo(self) -> bool:
        """Cargo is the view while it is selected and no message is shown: a message (the question of leaving, which
        any option can ask) takes the right side in its place."""
        return BUTTON_LABELS[self.selected] == 'Cargo' and self._shown is None

    def _shows_missions(self) -> bool:
        """The missions' list is the view while Missions is selected and no message is shown (see _shows_cargo)."""
        return BUTTON_LABELS[self.selected] == 'Missions' and self._shown is None

    def _missions_event(self, event: pygame.event.Event) -> bool:
        """The events the missions' list takes: its clicks, its scroll (the wheel, the scroll bar, Page Up and Page
        Down) and a way back from a detail, by Backspace or a right-click. The arrow keys stay with the options. True
        if it took the event."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                return self._missions.back()
            if event.key not in PAGE_KEYS:
                return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            return self._missions.back(event.pos)
        return self._missions.handle_content_event(event)

    def _shows_chat(self) -> bool:
        """Chat is the view while it is selected and no message is shown (see _shows_cargo)."""
        return BUTTON_LABELS[self.selected] == 'Chat' and self._shown is None

    def _chat_event(self, event: pygame.event.Event) -> bool:
        """The events the people's list takes: its clicks (a card is selected), its scroll (the wheel, the scroll bar,
        Page Up and Page Down). The arrow keys stay with the options. True if it took the event."""
        if event.type == pygame.KEYDOWN and event.key not in PAGE_KEYS:
            return False
        return self._chat.handle_event(event)

    def _focus_targets(self) -> List[tuple]:
        """What Tab goes over, in order: the options (Leave among them), the −, + and ++ of each cargo row while Cargo
        is selected, the people listed while Chat is selected, and the answers of the shown message. Then round
        again."""
        from spaceships.cargo_hold import SUPPLIES  # local: as in _draw_cargo
        targets: List[tuple] = [('option', index) for index in range(len(BUTTON_LABELS))]
        if self._shows_cargo():
            for k in range(len(SUPPLIES)):
                targets += [('cargo', k, -1), ('cargo', k, 1), ('fill', k)]
        if self._shows_chat():
            targets += [('person', index) for index in range(len(self._chat.available()))]
        if self._shown is not None:
            targets += [('answer', j) for j in range(len(self._shown[0].buttons))]
        return targets

    def _move_focus(self, step: int) -> None:
        """Tab: the focus goes to the next target (see _focus_targets). It only moves: Enter or Space press it."""
        targets = self._focus_targets()
        index = targets.index(self._focus) if self._focus in targets else 0
        self._focus = targets[(index + step) % len(targets)]
        self._focus_visible = True

    def _press_focus(self) -> None:
        """Enter or Space: presses the target that has the focus. An answer answers, a cargo row's − or + gives or
        takes one unit, its ++ fills it, Leave leaves (see _try_leave), an option is selected. On the option that is
        selected already, it answers the shown message as Enter always did: the answer under the mouse, else the
        first."""
        targets = self._focus_targets()
        token = self._focus if self._focus in targets else ('option', self.selected)
        if token[0] == 'answer':
            self._answer(token[1])
        elif token[0] == 'cargo':
            self._press_cargo(token[1], token[2])
        elif token[0] == 'fill':
            self._fill_cargo(token[1])
        elif token[0] == 'person':
            self._chat.select_at(token[1])
        elif BUTTON_LABELS[token[1]] == 'Leave' or token[1] != self.selected:
            self._select(token[1])
        elif self._shown is not None:
            self._answer(self._answer_hover or 0)

    def _select(self, index: int) -> None:
        """Selects another option: the conversation of the old one is closed, and the new one starts. Leave is not an
        option that stays selected: it leaves (see _try_leave), and the selection is the same as before."""
        self._focus = ('option', index)
        if BUTTON_LABELS[index] == 'Leave':
            self._try_leave()
        elif index != self.selected:
            self._close_option()
            self.selected = index
            self._open_option()

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if event.type == pygame.QUIT:
            return ('exit', None)
        if self._shown is not None and self._answer_event(event):  # noqa: SIM114
            pass
        elif self._shows_missions() and self._missions_event(event):
            pass
        elif self._shows_chat() and self._chat_event(event):
            pass
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self._move_focus(-1 if event.mod & pygame.KMOD_SHIFT else 1)
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._press_focus()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN):
            self._focus_visible = True
            index = self.selected
            while True:  # Up and Down select the options: passing over Leave must not leave
                index = (index + (-1 if event.key == pygame.K_UP else 1)) % len(BUTTON_LABELS)
                if BUTTON_LABELS[index] != 'Leave':
                    break
            self._select(index)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._focus_visible = False
            for minus, plus, fill, k in self._cargo_rects:
                if minus.collidepoint(event.pos) or plus.collidepoint(event.pos):
                    self._press_cargo(k, 1 if plus.collidepoint(event.pos) else -1)
                elif fill.collidepoint(event.pos):
                    self._fill_cargo(k)
            for index, rect in enumerate(self._button_rects):
                if rect.collidepoint(event.pos):
                    self._select(index)
        elif event.type == pygame.MOUSEMOTION:
            self._focus_visible = False  # the mouse is the one in use
        self._after_conversation()
        if self._leaving:
            self._close_option()
            return ('close', None)
        return None
