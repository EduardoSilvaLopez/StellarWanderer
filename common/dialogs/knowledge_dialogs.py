"""What the pilot knows, from the cockpit buttons: the stellar systems (KnownSystemsDialog) and the people they have talked
to (PeopleDialog). Both have the look of the message dialogs, a scrollable list and one Close button.

The systems are those of the player's knowledge (knowledge.py), each shown with the text of `StellarSystem.almanack()`: its
markdown headings and bullets are drawn as headings and 'label: value' lines. The people are those in
`GameEnvironment.persons` (the ones the player has talked to): each is a card, with the portrait beside the fields of
`Person.description_fields()`. A system or a person that is not in memory is generated again from its key or seed."""

from __future__ import annotations
from typing import List, Optional, Tuple
import pygame

from .dialog_fonts import body_font, title_font
from .message_dialog import ACCENT, ACCENT_DIM, TEXT_COLOR, MessageDialog
from .messages import Message

LABEL_COLOR = (120, 175, 175)
HEADING_COLOR = (225, 245, 245)
FIELD_SIZE = 18
PORTRAIT_SIZE = (128, 192)  # the portraits are 512 x 768
PORTRAIT_GAP = 22
BLOCK_GAP = 10  # between the lines of a list
SECTION_GAP = 22  # before a system's or a person's heading


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
        """A 'label: value' line (or several, when it wraps): the label dim, the value bright. An empty label is a plain line."""
        font = body_font(FIELD_SIZE)
        lines = MessageDialog.wrap(f"{label}: {value}" if label else value, font, width - indent)
        result: List[pygame.Surface] = []
        for number, line in enumerate(lines):
            surface = pygame.Surface((width, font.get_linesize()), pygame.SRCALPHA)
            x = indent
            if number == 0 and label and line.startswith(label + ':'):
                label_surface = font.render(label + ':', True, LABEL_COLOR)
                surface.blit(label_surface, (x, 0))
                x += label_surface.get_width()
                line = line[len(label) + 1:]
            surface.blit(font.render(line, True, TEXT_COLOR), (x, 0))
            result.append(surface)
        return result

    @staticmethod
    def _message(text: str, width: int) -> List[Tuple[pygame.Surface, int]]:
        return [(surface, 0) for surface in _ListDialog._field('', text, width)]


class KnownSystemsDialog(_ListDialog):
    """The stellar systems the pilot knows. Result: ('close', 0), ('close', None) on Esc, ('exit', None) if the window closes."""

    def __init__(self) -> None:
        super().__init__('Known stellar systems')

    def _build(self, width: int) -> List[Tuple[pygame.Surface, int]]:
        import game_environment as gem
        import knowledge

        galaxy = gem.current_environment.galaxy
        systems = [galaxy.system_of_key(key) for key in knowledge.current_knowledge.bodies]
        blocks: List[Tuple[pygame.Surface, int]] = []
        for system in (s for s in systems if s is not None):
            blocks += self._markdown(system.almanack(), width)
        return blocks or self._message('Nothing is known yet.', width)

    @staticmethod
    def _markdown(text: str, width: int) -> List[Tuple[pygame.Surface, int]]:
        """The headings ('##' system, '###' star or world, '####' moon) and bullets of an almanack text."""
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


class PeopleDialog(_ListDialog):
    """The people the pilot has talked to. Same results as KnownSystemsDialog."""

    def __init__(self) -> None:
        super().__init__('People')

    def _build(self, width: int) -> List[Tuple[pygame.Surface, int]]:
        import game_environment as gem
        import knowledge
        from galaxies.people.person import Person

        galaxy = gem.current_environment.galaxy
        outposts = [
            outpost
            for key in knowledge.current_knowledge.bodies
            if (system := galaxy.system_of_key(key)) is not None
            for world in system.get_all_worlds()
            for outpost in world.outposts.values()
        ]
        blocks: List[Tuple[pygame.Surface, int]] = []
        for seed, alterations in gem.current_environment.persons.items():
            person: Optional[Person] = next(
                (found for outpost in outposts if (found := outpost.person_with_seed(seed)) is not None), None)
            blocks.append((self._card(person, seed, alterations['first_met_at'], width), SECTION_GAP))
        return blocks or self._message('You have not talked to anybody yet.', width)

    @staticmethod
    def _card(person, seed: float, first_met_at: str, width: int) -> pygame.Surface:
        """One person: the portrait on the left, the name and the fields beside it. A person who cannot be found again
        shows only the ID and where the player met them."""
        text_width = width - PORTRAIT_SIZE[0] - PORTRAIT_GAP
        name = person.get_full_name() if person is not None else 'Unknown person'
        fields = person.description_fields() if person is not None else [('ID', f"{seed}."), ('First met at', first_met_at)]

        name_surface = title_font(20).render(name, True, ACCENT)
        lines: List[pygame.Surface] = []
        for label, value in fields:
            lines += _ListDialog._field(label, value, text_width)
        text_height = name_surface.get_height() + 8 + sum(line.get_height() + 2 for line in lines)

        card = pygame.Surface((width, max(PORTRAIT_SIZE[1], text_height)), pygame.SRCALPHA)
        portrait_rect = pygame.Rect(0, 0, *PORTRAIT_SIZE)
        if person is not None and person.icon is not None:
            card.blit(pygame.transform.smoothscale(person.icon, PORTRAIT_SIZE), portrait_rect)
        else:
            pygame.draw.rect(card, (16, 52, 56), portrait_rect)
        pygame.draw.rect(card, ACCENT, portrait_rect, 2)
        for corner, sx, sy in (((0, 0), 1, 1), ((portrait_rect.right - 1, 0), -1, 1),
                               ((0, portrait_rect.bottom - 1), 1, -1), ((portrait_rect.right - 1, portrait_rect.bottom - 1), -1, -1)):
            pygame.draw.line(card, ACCENT, corner, (corner[0] + 12 * sx, corner[1]), 4)
            pygame.draw.line(card, ACCENT, corner, (corner[0], corner[1] + 12 * sy), 4)

        x, y = PORTRAIT_SIZE[0] + PORTRAIT_GAP, 0
        card.blit(name_surface, (x, y))
        y += name_surface.get_height() + 8
        for line in lines:
            card.blit(line, (x, y))
            y += line.get_height() + 2
        return card
