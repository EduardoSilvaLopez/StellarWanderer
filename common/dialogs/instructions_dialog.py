"""The instructions screen: the controls and how the game works, read-only and scrollable.

The text is INSTRUCTIONS below: a list of sections, each a heading and its paragraphs. Each paragraph is wrapped to the
box. A section can also have a drawing, listed in FIGURES by its heading (the Flying section is drawn, not written).
Edit the text there; the layout does not depend on it.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Tuple
import math
import pygame

from .dialog import Dialog, DialogResult
from .dialog_fonts import body_font, title_font
from .message_dialog import MessageDialog

INSTRUCTIONS: List[Tuple[str, List[str]]] = [
    ("Worlds", [
        "Fly close to a planet or moon to 'bind' to its surface. Fly away from it to 'unbind'.",
        "When the proximity meter's title is green (FIXED) - the coordinates change. Use brake to align with the body's movement.",
        "Outside every fixed zone, the meter reads TARGET: Tab and Shift+Tab move the target through the bodies in order of distance.",
        "While bound, the map in the middle shows the world: the mouse wheel and left button can be used to look around.",
        "The scanner shows what is in the crosshair. Hold Space to activate it (whichever that means in context).",
    ]),
    ("Flying", [  # drawn above the text: see _flying_figure
        "Numpad + / -: faster / slower passing of game time (be careful!).",
    ]),
    ("Mining", [
        "Heat a rock to melt it, crearing an ore field.",
        "M: place an ore mine in front of the ship.",
    ]),
    ("Keeping alive", [
        "Maintenance, energy, air, water and food are spent... don't let them go too down.",
        "Outposts restore them. Watch the bars and the cargo: a critical warning means go to an outpost now.",
    ]),
    ("Game", [
        "Esc: open the menu, where you can resume, start a new game, load or save. F5: save now, under the default name. F6: load the last save.",
    ]),
]

BODY_SIZE = 18
HEADING_SIZE = 22
TITLE_SIZE = 44
TITLE_COLOUR = (100, 200, 255)
HEADING_COLOUR = (150, 200, 255)
TEXT_COLOUR = (200, 200, 200)
BOX_COLOUR = (30, 30, 50)
BOX_EDGE_COLOUR = (80, 80, 120)
SCROLL_STEP = 30  # pixels per wheel notch or arrow key
PAGE_KEYS = {pygame.K_PAGEUP: -1, pygame.K_PAGEDOWN: 1}

# The Flying drawing: a grid of 3 columns and 2 rows of cells, each one control, with its keys around the ship it moves.
FLYING_CELL_H = 172
FLYING_SHIP_Y = 84  # the ship's height in its cell; the captions sit at the top of the cell
ARROW_COLOUR = (120, 220, 255)
SHIP_COLOUR = (200, 230, 255)
KEY_FILL = (45, 55, 85)
KEY_EDGE = (150, 200, 255)
KEY_SIZE = 28


def _key(surface: pygame.Surface, font: pygame.font.Font, label: str, centre: Tuple[int, int]) -> None:
    """A keycap with its label, centred on `centre`."""
    rect = pygame.Rect(0, 0, KEY_SIZE, KEY_SIZE)
    rect.center = centre
    pygame.draw.rect(surface, KEY_FILL, rect, border_radius=5)
    pygame.draw.rect(surface, KEY_EDGE, rect, 2, border_radius=5)
    text = font.render(label, True, TEXT_COLOUR)
    surface.blit(text, text.get_rect(center=rect.center))


def _arrow_head(surface: pygame.Surface, start: Tuple[float, float], end: Tuple[float, float]) -> None:
    """The head of an arrow at `end`, pointing from start to end."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    base_x, base_y = end[0] - ux * 8, end[1] - uy * 8
    side_x, side_y = -uy * 5, ux * 5
    pygame.draw.polygon(surface, ARROW_COLOUR, [
        end, (base_x + side_x, base_y + side_y), (base_x - side_x, base_y - side_y)])


def _arrow(surface: pygame.Surface, start: Tuple[float, float], end: Tuple[float, float]) -> None:
    """A straight arrow from start to end."""
    pygame.draw.line(surface, ARROW_COLOUR, start, end, 2)
    _arrow_head(surface, start, end)


def _arc_arrow(surface: pygame.Surface, centre: Tuple[int, int], radius: float,
               start_deg: float, end_deg: float) -> None:
    """An arc around `centre` from start_deg to end_deg, with its arrow at the end. Angles as on screen: 0 is right,
    90 is down, so from 200 to 160 runs down the left side."""
    steps = 12
    points = []
    for k in range(steps + 1):
        angle = math.radians(start_deg + (end_deg - start_deg) * k / steps)
        points.append((centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle)))
    pygame.draw.lines(surface, ARROW_COLOUR, False, points, 2)
    _arrow_head(surface, points[-2], points[-1])


def _ship_up(surface: pygame.Surface, centre: Tuple[int, int]) -> None:
    """The ship from above, nose up."""
    cx, cy = centre
    pygame.draw.polygon(surface, SHIP_COLOUR, [(cx, cy - 13), (cx - 9, cy + 9), (cx, cy + 4), (cx + 9, cy + 9)])


def _ship_side(surface: pygame.Surface, centre: Tuple[int, int]) -> None:
    """The ship from the side, nose to the right."""
    cx, cy = centre
    pygame.draw.polygon(surface, SHIP_COLOUR, [(cx + 14, cy), (cx - 10, cy - 8), (cx - 6, cy), (cx - 10, cy + 8)])


def _flying_figure(width: int) -> pygame.Surface:
    """The Flying section as diagrams. Each cell is one control: the keys are the keycaps, the arrows what they do."""
    cell = width / 3
    surface = pygame.Surface((width, FLYING_CELL_H * 2), pygame.SRCALPHA)
    key_font = body_font(16)
    caption_font = body_font(15)

    def place(col: int, row: int) -> Tuple[int, int]:
        return (int(col * cell + cell / 2), row * FLYING_CELL_H + FLYING_SHIP_Y)

    def caption(col: int, row: int, text: str) -> None:
        label = caption_font.render(text, True, HEADING_COLOUR)
        surface.blit(label, label.get_rect(midtop=(int(col * cell + cell / 2), row * FLYING_CELL_H)))

    # Thrust: forward, back, left, right (W X A D), from above.
    cx, cy = place(0, 0)
    _ship_up(surface, (cx, cy))
    _arrow(surface, (cx, cy - 18), (cx, cy - 40))
    _key(surface, key_font, 'W', (cx, cy - 50))
    _arrow(surface, (cx, cy + 18), (cx, cy + 40))
    _key(surface, key_font, 'X', (cx, cy + 50))
    _arrow(surface, (cx - 18, cy), (cx - 40, cy))
    _key(surface, key_font, 'A', (cx - 50, cy))
    _arrow(surface, (cx + 18, cy), (cx + 40, cy))
    _key(surface, key_font, 'D', (cx + 50, cy))
    caption(0, 0, 'Thrust')

    # Turn: yaw left (4) and right (6), from above.
    cx, cy = place(1, 0)
    _ship_up(surface, (cx, cy))
    _arc_arrow(surface, (cx, cy), 46, 200, 160)
    _arc_arrow(surface, (cx, cy), 46, -20, 20)
    _key(surface, key_font, '4', (cx - 74, cy))
    _key(surface, key_font, '6', (cx + 74, cy))
    caption(1, 0, 'Turn')

    # Brake: arrows push against the motion from every side; S stops all of it.
    cx, cy = place(2, 0)
    _ship_up(surface, (cx, cy))
    _arrow(surface, (cx - 40, cy), (cx - 18, cy))
    _arrow(surface, (cx + 40, cy), (cx + 18, cy))
    _arrow(surface, (cx, cy - 40), (cx, cy - 18))
    _key(surface, key_font, 'S', (cx, cy + 50))
    caption(2, 0, 'Brake')

    # Climb (bound to a world): up (8) and down (2), from the side.
    cx, cy = place(0, 1)
    _ship_side(surface, (cx, cy))
    _arrow(surface, (cx, cy - 16), (cx, cy - 36))
    _key(surface, key_font, '8', (cx, cy - 50))
    _arrow(surface, (cx, cy + 16), (cx, cy + 36))
    _key(surface, key_font, '2', (cx, cy + 50))
    caption(0, 1, 'Climb, bound')

    # Pitch (unbound): nose up (8) and nose down (2), from the side.
    cx, cy = place(1, 1)
    _ship_side(surface, (cx, cy))
    _arc_arrow(surface, (cx, cy), 30, 6, -50)
    _arc_arrow(surface, (cx, cy), 30, -6, 50)
    _key(surface, key_font, '8', (cx + 58, cy - 40))
    _key(surface, key_font, '2', (cx + 58, cy + 40))
    caption(1, 1, 'Pitch, unbound')

    # Roll (unbound): seen from behind, E rolls right, Q rolls left.
    cx, cy = place(2, 1)
    pygame.draw.line(surface, SHIP_COLOUR, (cx - 40, cy + 6), (cx + 40, cy + 6), 3)
    pygame.draw.circle(surface, SHIP_COLOUR, (cx, cy + 6), 6)
    _arc_arrow(surface, (cx, cy + 6), 40, 200, 340)
    _key(surface, key_font, 'Q', (cx - 50, cy + 50))
    _key(surface, key_font, 'E', (cx + 50, cy + 50))
    caption(2, 1, 'Roll, unbound')

    return surface


# The drawing of a section, by its heading. A section listed here is drawn after its heading.
FIGURES: Dict[str, Callable[[int], pygame.Surface]] = {'Flying': _flying_figure}


class InstructionsDialog(Dialog):
    """The instructions screen, opened from the starting dialog. Result: ('back', None)."""

    WIDTH = 800
    HEIGHT = 600
    MARGIN = 24
    TITLE_TOP = 12
    BOX_GAP = 24  # between the bottom of the title's letters and the text box
    BACK_HEIGHT = 52  # the bottom row for the Back button

    def __init__(self) -> None:
        super().__init__(self.WIDTH, self.HEIGHT)
        title_ink = title_font(TITLE_SIZE).render("Instructions", True, TITLE_COLOUR).get_bounding_rect()
        box_top = self.TITLE_TOP + title_ink.bottom + self.BOX_GAP
        self.box_rect = pygame.Rect(self.MARGIN, box_top, self.WIDTH - 2 * self.MARGIN,
                                    self.HEIGHT - box_top - self.BACK_HEIGHT)
        self.back_rect = pygame.Rect(self.WIDTH // 2 - 100, self.HEIGHT - self.BACK_HEIGHT + 12, 200, 32)
        self.scroll: int = 0  # pixels the text is moved up
        self._lines: List[Tuple[str, pygame.Surface]] = []  # (kind, rendered line)
        self._text_height: int = 0
        self._build_lines()

    def _build_lines(self) -> None:
        """Wrap and render the whole text once, as the box is fixed in size."""
        body = body_font(BODY_SIZE)
        heading = body_font(HEADING_SIZE)
        width = self.box_rect.width - 60  # the text's left padding, and room for the scrollbar on the right
        lines: List[Tuple[str, pygame.Surface]] = []
        for title, paragraphs in INSTRUCTIONS:
            lines.append(('gap', pygame.Surface((1, body.get_linesize() // 2))))
            lines.append(('heading', heading.render(title, True, HEADING_COLOUR)))
            if title in FIGURES:
                lines.append(('figure', FIGURES[title](width)))
            for paragraph in paragraphs:
                for line in MessageDialog.wrap('- ' + paragraph, body, width):
                    lines.append(('text', body.render(line, True, TEXT_COLOUR)))
        self._lines = lines
        self._text_height = sum(surface.get_height() + 4 for _, surface in lines)

    def _max_scroll(self) -> int:
        return max(0, self._text_height - (self.box_rect.height - 16))

    def _scroll_by(self, pixels: int) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll + pixels))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((20, 20, 30))

        title = title_font(TITLE_SIZE).render("Instructions", True, TITLE_COLOUR)
        surface.blit(title, title.get_rect(topleft=(self.MARGIN, self.TITLE_TOP)))

        pygame.draw.rect(surface, BOX_COLOUR, self.box_rect)
        pygame.draw.rect(surface, BOX_EDGE_COLOUR, self.box_rect, 2)
        previous_clip = surface.get_clip()
        surface.set_clip(self.box_rect.inflate(-4, -4))
        y = self.box_rect.top + 8 - self.scroll
        x = self.box_rect.left + 14
        for kind, line in self._lines:
            if kind != 'gap':
                surface.blit(line, (x, y))
            y += line.get_height() + 4
        surface.set_clip(previous_clip)

        if self._max_scroll() > 0:
            track = pygame.Rect(self.box_rect.right - 16, self.box_rect.top + 6, 8, self.box_rect.height - 12)
            pygame.draw.rect(surface, (60, 60, 80), track)
            thumb_height = max(20, track.height * self.box_rect.height // max(1, self._text_height))
            thumb_top = track.top + (track.height - thumb_height) * self.scroll // self._max_scroll()
            pygame.draw.rect(surface, (100, 150, 200), (track.left, thumb_top, track.width, thumb_height))

        pygame.draw.rect(surface, (110, 50, 50), self.back_rect)
        pygame.draw.rect(surface, (190, 110, 110), self.back_rect, 2)
        back = body_font(20).render("Back", True, (255, 255, 255))
        surface.blit(back, back.get_rect(center=self.back_rect.center))

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if event.type == pygame.QUIT:
            return ('exit', None)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.back_rect.collidepoint(event.pos):
            return ('back', None)
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * SCROLL_STEP)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                return ('back', None)
            if event.key == pygame.K_UP:
                self._scroll_by(-SCROLL_STEP)
            elif event.key == pygame.K_DOWN:
                self._scroll_by(SCROLL_STEP)
            elif event.key in PAGE_KEYS:
                self._scroll_by(PAGE_KEYS[event.key] * self.box_rect.height)
            elif event.key == pygame.K_HOME:
                self.scroll = 0
            elif event.key == pygame.K_END:
                self.scroll = self._max_scroll()
        return None
