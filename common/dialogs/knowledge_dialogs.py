"""What the pilot knows, from the cockpit buttons: the stellar systems (KnownSystemsDialog), the people they have
talked to (KnownPeopleDialog) and the specifications of the ship they fly (ShipSpecificationsDialog). All have the look
of the message dialogs, a scrollable list and one Close button.

The systems are those of the player's knowledge (knowledge.py), each shown with the text of `StellarSystem.markdown()`,
which ends with the asteroids that matter (see `Asteroid.markdown`): its markdown headings and bullets are drawn as
headings and 'label: value' lines. The people are those in `GameEnvironment.persons` (the ones the player has talked to,
and those of a mission they took, "Not met yet"): each is a card, with the portrait beside the fields of
`Person.description_fields()`, and a comment box that the player can write in (saved with the person, see
Person.set_comment). A system or a person that is not in memory is generated again from its key or seed."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple
import pygame

from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, TEXT_COLOR, MessageDialog
from .dialog import DialogResult
from .messages import Message

if TYPE_CHECKING:
    from galaxies.people.person import Person
    from spaceships.ship import Ship

LABEL_COLOR = (120, 175, 175)
HEADING_COLOR = (225, 245, 245)
FIELD_SIZE = 18
PORTRAIT_SIZE = (128, 192)  # the portraits are 512 x 768
PORTRAIT_GAP = 22
BLOCK_GAP = 10  # between the lines of a list
SECTION_GAP = 22  # before a system's or a person's heading
COMMENT_GAP = 8  # between a person's fields and their comment box
COMMENT_PADDING = 6
COMMENT_MIN_LINES = 2  # the box is at least this tall, even when empty
COMMENT_FILL = (14, 24, 30)
COMMENT_PLACEHOLDER = 'Comments'
COMMENT_PLACEHOLDER_COLOUR = (110, 120, 120)
# The keys that edit the comment being typed in. Letters and the space come as TEXTINPUT; Esc is left to close the
# dialog.
TYPING_KEYS = (pygame.K_BACKSPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


class _ListDialog(MessageDialog):
    """A message dialog whose scrolled content is a list of pre-rendered surfaces (see _build), not wrapped text."""

    def __init__(self, title: str) -> None:
        self._blocks: List[Tuple[pygame.Surface, int]] = []  # (surface, y inside the text area)
        super().__init__(Message(title=title, text='', buttons=['Close']))

    def _build(self, width: int) -> List[Tuple[pygame.Surface, int]]:
        """The content's surfaces for a text area `width` wide, each with the gap to leave above it."""
        raise NotImplementedError

    def _layout_text(self) -> None:
        y = 0
        self._blocks = []
        for surface, gap in self._build(self.text_rect.width):
            y += gap
            self._blocks.append((surface, y))
            y += surface.get_height()
        self.content_height = y

    def _draw_content(self, surface: pygame.Surface) -> None:
        for block, y in self._blocks:
            top = self.text_rect.top + y - self.scroll
            if top + block.get_height() >= self.text_rect.top and top <= self.text_rect.bottom:
                surface.blit(block, (self.text_rect.left, top))

    @staticmethod
    def _field(label: str, value: str, width: int, indent: int = 0) -> List[pygame.Surface]:
        """A 'label: value' line (or several, when it wraps): the label dim, the value bright. An empty label is a plain
        line."""
        font = body_font(FIELD_SIZE)
        lines = MessageDialog.wrap(f"{label}: {value}" if label else value, font, width - indent)
        result: List[pygame.Surface] = []
        for number, line in enumerate(lines):
            surface = pygame.Surface((width, font.get_linesize()), pygame.SRCALPHA)
            x = indent
            text = line
            if number == 0 and label and line.startswith(label + ':'):
                label_surface = font.render(label + ':', True, LABEL_COLOR)
                surface.blit(label_surface, (x, 0))
                x += label_surface.get_width()
                text = line[len(label) + 1:]
            surface.blit(font.render(text, True, TEXT_COLOR), (x, 0))
            result.append(surface)
        return result

    @staticmethod
    def _message(text: str, width: int) -> List[Tuple[pygame.Surface, int]]:
        return [(surface, 0) for surface in _ListDialog._field('', text, width)]


class KnownSystemsDialog(_ListDialog):
    """The stellar systems the pilot knows. Result: ('close', 0), ('close', None) on Esc or a right-click, ('exit',
    None) if the window closes."""

    def __init__(self) -> None:
        super().__init__('Known stellar systems')

    def _build(self, width: int) -> List[Tuple[pygame.Surface, int]]:
        import game_environment as gem
        from galaxies.people import knowledge

        galaxy = gem.current_environment.galaxy
        systems = [galaxy.system_of_key(key) for key in knowledge.current_knowledge.bodies]
        blocks: List[Tuple[pygame.Surface, int]] = []
        for system in (s for s in systems if s is not None):
            blocks += self._markdown(system.markdown(), width)
        return blocks or self._message('Nothing is known yet.', width)

    @staticmethod
    def _markdown(text: str, width: int) -> List[Tuple[pygame.Surface, int]]:
        """The headings ('##' system, '###' star or world, '####' moon) and bullets of a markdown text."""
        blocks: List[Tuple[pygame.Surface, int]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            level = len(stripped) - len(stripped.lstrip('#'))
            if stripped.startswith('#') and stripped[level:level + 1] == ' ':
                heading = stripped[level + 1:]
                if level <= 2:
                    surface = title_font(22).render(heading, True, ACCENT)
                    blocks.append((surface, SECTION_GAP))
                    rule = pygame.Surface((width, 3), pygame.SRCALPHA)
                    pygame.draw.line(rule, ACCENT_DIM, (0, 1), (width, 1), 1)
                    blocks.append((rule, 2))
                else:
                    size, indent = (17, 0) if level == 3 else (15, 18)
                    surface = pygame.Surface((width, title_font(size).get_linesize()), pygame.SRCALPHA)
                    surface.blit(title_font(size).render(heading, True, HEADING_COLOR), (indent, 0))
                    blocks.append((surface, BLOCK_GAP + 4))
            elif stripped.startswith('* '):
                depth = len(line) - len(line.lstrip(' '))
                label, separator, value = stripped[2:].partition(': ')
                fields = _ListDialog._field(label, value, width, 14 + depth * 8) if separator \
                    else _ListDialog._field('', stripped[2:], width, 14 + depth * 8)
                blocks += [(surface, 2) for surface in fields]
            else:
                blocks += [(surface, 2) for surface in _ListDialog._field('', stripped, width)]
        return blocks


class KnownPeopleDialog(_ListDialog):
    """The people the pilot has talked to, each with a comment box. A click in a box focuses it: the keys then write
    into it (Enter starts a new line) until another box or the outside is clicked. Esc, a right-click, or the Close
    button, closes the dialog; the comments are already saved as they are typed. Same results as KnownSystemsDialog. The
    box that has the focus stays focused when the list is scrolled away (wheel, keys or scroll bar), and typing scrolls
    it back into view."""

    def __init__(self) -> None:
        self._people: dict = {}  # seed -> Person, for each card that could be found again
        # (seed, index of the card's block, box inside that block)
        self._boxes: List[Tuple[float, int, pygame.Rect]] = []
        self._focus: Optional[float] = None  # the seed of the person whose comment is being typed
        super().__init__('People')

    # region Cards
    def _build(self, width: int) -> List[Tuple[pygame.Surface, int]]:
        import game_environment as gem
        from galaxies.people import knowledge

        galaxy = gem.current_environment.galaxy
        outposts = [
            outpost
            for key in knowledge.current_knowledge.bodies
            if (system := galaxy.system_of_key(key)) is not None
            for world in system.get_all_worlds()
            for outpost in world.outposts.values()
        ]
        self._people = {}
        self._boxes = []
        blocks: List[Tuple[pygame.Surface, int]] = []
        for seed, alterations in gem.current_environment.persons.items():
            person: Optional[Person] = next(
                (found for outpost in outposts if (found := outpost.person_with_seed(seed)) is not None), None)
            if person is not None:
                self._people[seed] = person
            card, box = self._card(person, seed, alterations['first_met_at'], width)
            if box is not None:
                self._boxes.append((seed, len(blocks), box))
            blocks.append((card, SECTION_GAP))
        return blocks or self._message('You have not talked to anybody yet.', width)

    @staticmethod
    def _comment_lines(text: str, width: int) -> List[str]:
        """The comment as lines that fit `width`: each of its own lines, wrapped (an empty line stays one line)."""
        font = body_font(FIELD_SIZE)
        return [line for paragraph in text.split('\n') for line in (MessageDialog.wrap(paragraph, font, width) or [''])]

    def _card(self, person: Optional[Person], seed: int, first_met_at: Optional[str],
              width: int) -> Tuple[pygame.Surface, Optional[pygame.Rect]]:
        """One person: the portrait on the left, the name and the fields beside it, and under them the comment box (when
        the person could be found again). Returns the card and the box's rectangle inside it."""
        text_width = width - PORTRAIT_SIZE[0] - PORTRAIT_GAP
        name = person.get_full_name() if person is not None else 'Unknown person'
        fields = person.description_fields() if person is not None else [('ID', f"{seed}."),
                                                                         ('First met at',
                                                                          "Not met yet" if first_met_at is None
                                                                          else first_met_at)]

        name_surface = title_font(20).render(name, True, ACCENT)
        lines: List[pygame.Surface] = []
        for label, value in fields:
            lines += _ListDialog._field(label, value, text_width)
        fields_bottom = name_surface.get_height() + 8 + sum(line.get_height() + 2 for line in lines)

        box: Optional[pygame.Rect] = None
        text_height = fields_bottom
        if person is not None:
            font = body_font(FIELD_SIZE)
            comment_lines = self._comment_lines(person.comment, text_width - 2
                                                * COMMENT_PADDING) if person.comment else []
            rows = max(COMMENT_MIN_LINES, len(comment_lines))
            box = pygame.Rect(PORTRAIT_SIZE[0] + PORTRAIT_GAP, fields_bottom + COMMENT_GAP, text_width,
                              2 * COMMENT_PADDING + rows * font.get_linesize())
            text_height = box.bottom

        card = pygame.Surface((width, max(PORTRAIT_SIZE[1], text_height)), pygame.SRCALPHA)
        portrait_rect = pygame.Rect(0, 0, *PORTRAIT_SIZE)
        if person is not None and person.icon is not None:
            card.blit(pygame.transform.smoothscale(person.icon, PORTRAIT_SIZE), portrait_rect)
        else:
            pygame.draw.rect(card, (16, 52, 56), portrait_rect)
        pygame.draw.rect(card, ACCENT, portrait_rect, 2)
        for corner, sx, sy in (((0, 0), 1, 1), ((portrait_rect.right - 1, 0), -1, 1),
                               ((0, portrait_rect.bottom - 1), 1, -1), ((portrait_rect.right - 1, portrait_rect.bottom
                                                                         - 1), -1, -1)):
            pygame.draw.line(card, ACCENT, corner, (corner[0] + 12 * sx, corner[1]), 4)
            pygame.draw.line(card, ACCENT, corner, (corner[0], corner[1] + 12 * sy), 4)

        x, y = PORTRAIT_SIZE[0] + PORTRAIT_GAP, 0
        card.blit(name_surface, (x, y))
        y += name_surface.get_height() + 8
        for line in lines:
            card.blit(line, (x, y))
            y += line.get_height() + 2

        if box is not None:
            self._draw_box(card, box, person, seed == self._focus)
        return card, box

    @staticmethod
    def _draw_box(card: pygame.Surface, box: pygame.Rect, person: Person, focused: bool) -> None:
        """The comment box: the comment, or the grey placeholder while nothing has been written."""
        font = body_font(FIELD_SIZE)
        pygame.draw.rect(card, COMMENT_FILL, box)
        pygame.draw.rect(card, ACCENT if focused else ACCENT_DIM, box, 2 if focused else 1)
        text_x, text_y = box.left + COMMENT_PADDING, box.top + COMMENT_PADDING
        if not person.comment:
            card.blit(font.render(COMMENT_PLACEHOLDER, True, COMMENT_PLACEHOLDER_COLOUR), (text_x, text_y))
            return
        lines = KnownPeopleDialog._comment_lines(person.comment, box.width - 2 * COMMENT_PADDING)
        for index, line in enumerate(lines):
            card.blit(font.render(line, True, TEXT_COLOR), (text_x, text_y + index * font.get_linesize()))
    # endregion

    # region Focus and typing
    def _box_at(self, position: Tuple[int, int]) -> Optional[float]:
        """The seed of the person whose comment box is at a mouse position (dialog coordinates), or None. A box scrolled
        out of the text area cannot be clicked."""
        if not self.text_rect.collidepoint(position):
            return None
        for seed, index, box in self._boxes:
            on_screen = box.move(self.text_rect.left, self.text_rect.top + self._blocks[index][1] - self.scroll)
            if on_screen.collidepoint(position):
                return seed
        return None

    def _set_focus(self, seed: Optional[int]) -> None:
        """Focuses the comment box of `seed` (None for none): the keys type into it. The text input is on only while
        focused."""
        if seed == self._focus:
            return
        self._focus = seed
        if seed is None:
            pygame.key.stop_text_input()
        else:
            pygame.key.start_text_input()
        self._layout_text()

    def _change_comment(self, text: str) -> None:
        self._people[self._focus].set_comment(text)
        self._layout_text()
        self._reveal_focused_box()

    def _reveal_focused_box(self) -> None:
        """Scrolls just enough to show the focused comment box, where the typing goes: one scrolled away with the wheel
        or the scroll bar comes back when the player types. A box taller than the view shows its top."""
        for seed, index, box in self._boxes:
            if seed == self._focus:
                top = self._blocks[index][1] + box.top
                bottom = self._blocks[index][1] + box.bottom
                scroll = min(max(self.scroll, bottom - self.text_rect.height), top)
                self.scroll = max(0, min(self._max_scroll, scroll))
                break

    def handle_event(self, event: pygame.event.Event) -> Optional[DialogResult]:
        if self._focus is not None and event.type == pygame.TEXTINPUT:
            self._change_comment(self._people[self._focus].comment + event.text)
            return None
        if self._focus is not None and event.type == pygame.KEYDOWN and event.key in TYPING_KEYS:
            comment = self._people[self._focus].comment
            if event.key == pygame.K_BACKSPACE:
                self._change_comment(comment[:-1])
            elif event.key != pygame.K_SPACE:  # the space is typed as TEXTINPUT; here it only must not close the dialog
                self._change_comment(comment + '\n')
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            on_scroll_bar = self._max_scroll > 0 and self.scroll_bar.track.collidepoint(event.pos)
            if not on_scroll_bar:  # a press on the scroll bar keeps the focus: typing brings the box back into view
                self._set_focus(self._box_at(event.pos))
        result = super().handle_event(event)
        if result is not None:
            self._set_focus(None)  # the text input stops with the dialog
        return result
    # endregion


SI_PREFIXES = ((1e15, 'P'), (1e12, 'T'), (1e9, 'G'), (1e6, 'M'), (1e3, 'k'), (1.0, ''))


def _si(value: float, unit: str) -> str:
    """A value with the SI prefix that keeps its number between 1 and 1000: '400 GWh', '1.5 TWh'."""
    for scale, prefix in SI_PREFIXES:
        if abs(value) >= scale:
            return f"{value / scale:.3g} {prefix}{unit}"
    return f"{value:.3g} {unit}"


class ShipSpecificationsDialog(_ListDialog):
    """The specifications of the pilot's ship: its kind (the name of its configuration), then the values that vary from
    one kind to another (see spaceships/ship_configurations). Same results as KnownSystemsDialog."""

    def __init__(self, ship: Ship) -> None:
        self._ship: Ship = ship
        super().__init__('Ship specifications')

    def _build(self, width: int) -> List[Tuple[pygame.Surface, int]]:
        configuration = type(self._ship)
        hold = type(self._ship.cargo_hold)
        fields = [
            ('Energy capacity', _si(configuration.ENERGY_MAX, 'Wh')),
            ('Acceleration, forward and backward', f"{configuration.FORWARD_BACKWARD_ACC:g} m/s²"),
            ('Braking', f"{configuration.BRAKE_ACC:g} m/s²"),
            ('Cargo hold', f"{hold.CAPACITY} kg"),
            ('Air carried at most', f"{hold.AIR_MAX:g} kg"),
            ('Water carried at most', f"{hold.WATER_MAX:g} kg"),
            ('Food carried at most', f"{hold.FOOD_MAX:g} kg"),
        ]
        blocks: List[Tuple[pygame.Surface, int]] = [(title_font(22).render(configuration.NAME, True, ACCENT),
                                                     SECTION_GAP)]
        for label, value in fields:
            blocks += [(surface, 2) for surface in _ListDialog._field(label, value, width)]
        return blocks
