"""The search box of the people lists: the People dialog (beside its title, see knowledge_dialogs.py) and the people panel
of the outpost's Chat (see staff_list.py). A box with the text typed in (or a grey 'Search' while empty), a cursor while
focused, and a magnifier at its right. The text is `query`: what the list filters on (Person.matches_search).

A focused box takes the typed text (`edit`) and the keys in KEYS, which do not press the buttons under it: the space is
typed as TEXTINPUT, and Enter and the space only must not press. Esc and a right-click are left to the dialog."""

from __future__ import annotations
from typing import Optional
import pygame

from .dialog_fonts import body_font
from .message_dialog import ACCENT, ACCENT_DIM, TEXT_COLOR

HEIGHT = 30
FONT_SIZE = 18
PADDING = 6  # between the text and the box's edge, on the left
ICON_RADIUS = 7  # of the magnifier's glass
ICON_INSET = 8  # between the magnifier and the box's right edge
FILL = (14, 24, 30)
PLACEHOLDER = 'Search'
PLACEHOLDER_COLOUR = (110, 120, 120)
KEYS = (pygame.K_BACKSPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


def edit(query: str, event: pygame.event.Event) -> Optional[str]:
    """The query after `event` when the event types into the box (text, or Backspace), else None."""
    if event.type == pygame.TEXTINPUT:
        return query + event.text
    if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
        return query[:-1]
    return None


def swallows(event: pygame.event.Event) -> bool:
    """Whether a focused box takes the event (a key of KEYS) so that no button under it is pressed."""
    return event.type == pygame.KEYDOWN and event.key in KEYS


def draw(surface: pygame.Surface, rect: pygame.Rect, query: str, focused: bool) -> None:
    """The box in `rect` (HEIGHT high), its text cut from the left when it is too long."""
    font = body_font(FONT_SIZE)
    pygame.draw.rect(surface, FILL, rect)
    pygame.draw.rect(surface, ACCENT if focused else ACCENT_DIM, rect, 2 if focused else 1)

    icon_centre = (rect.right - ICON_INSET - ICON_RADIUS, rect.centery - 2)
    pygame.draw.circle(surface, ACCENT, icon_centre, ICON_RADIUS, 2)
    pygame.draw.line(surface, ACCENT, (icon_centre[0] + 5, icon_centre[1] + 5),
                     (icon_centre[0] + 10, icon_centre[1] + 10), 3)

    room = rect.width - PADDING - 2 * ICON_INSET - 2 * ICON_RADIUS
    rendered = font.render(query or PLACEHOLDER, True, TEXT_COLOR if query else PLACEHOLDER_COLOUR)
    typed = min(font.size(query)[0], room)
    if rendered.get_width() > room:
        rendered = rendered.subsurface((rendered.get_width() - room, 0, room, rendered.get_height()))
    x, y = rect.left + PADDING, rect.centery - font.get_linesize() // 2
    surface.blit(rendered, (x, y))
    if focused:
        cursor_x = x + typed + 1
        pygame.draw.line(surface, ACCENT, (cursor_x, y), (cursor_x, y + font.get_linesize() - 2), 2)
