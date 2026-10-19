"""A vertical scroll bar for the dialogs: it draws the thumb, and the mouse can drag it or click the track to page.

The dialog keeps its own scroll value, in its own unit (pixels, or rows of a list); the bar only works out the thumb from
it, and says what the scroll becomes when the mouse acts on it. `max_scroll` is the largest scroll, and `visible` how much
of the content is in view, in the same unit. Nothing is drawn, and the mouse is not answered, while max_scroll is 0 or less
(the content fits)."""

from __future__ import annotations
from typing import Optional, Tuple
import pygame

Colour = Tuple[int, int, int]


class ScrollBar:
    """The track is the column that holds the thumb and answers the mouse; it is drawn only if it has a colour.

    Mouse (positions in dialog coordinates, see Dialog.localize_event): a press on the thumb grabs it, and it follows the
    mouse until the button is released, wherever the mouse goes; a press on the track above or below the thumb moves the
    scroll a page (`visible`) that way."""

    MIN_WIDTH = 8  # pixels: a thinner bar is hard to hit with the mouse

    def __init__(self, track: pygame.Rect, thumb_colour: Colour, track_colour: Optional[Colour] = None,
                 min_thumb: int = 24) -> None:
        self.track: pygame.Rect = track.copy()
        self.track.width = max(self.MIN_WIDTH, track.width)
        self.thumb_colour: Colour = thumb_colour
        self.track_colour: Optional[Colour] = track_colour
        self.min_thumb: int = min_thumb  # the thumb is never shorter, however long the content
        self._grab: Optional[int] = None  # while dragging: how far below the thumb's top the mouse took hold of it

    def thumb_rect(self, scroll: int, max_scroll: int, visible: int) -> pygame.Rect:
        """The thumb: as long as the share of the content in view, and where the scroll has reached. max_scroll must be above 0."""
        height = max(self.min_thumb, self.track.height * visible // (visible + max_scroll))
        top = self.track.top + (self.track.height - height) * scroll // max_scroll
        return pygame.Rect(self.track.left, top, self.track.width, height)

    def draw(self, surface: pygame.Surface, scroll: int, max_scroll: int, visible: int) -> None:
        if max_scroll <= 0:
            return
        if self.track_colour is not None:
            pygame.draw.rect(surface, self.track_colour, self.track)
        pygame.draw.rect(surface, self.thumb_colour, self.thumb_rect(scroll, max_scroll, visible))

    def handle_event(self, event: pygame.event.Event, scroll: int, max_scroll: int, visible: int) -> Optional[int]:
        """The scroll that this event sets, when it is the bar's: a press on the thumb or the track, the motion of a drag, its
        release. None for any other event. A press on the thumb and a release leave the scroll as it is, and still return
        it: the event is the bar's all the same, and the dialog must not use it for anything else."""
        if max_scroll <= 0:
            self._grab = None
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.track.collidepoint(event.pos):
            thumb = self.thumb_rect(scroll, max_scroll, visible)
            if thumb.collidepoint(event.pos):
                self._grab = event.pos[1] - thumb.top
                return scroll
            page = -visible if event.pos[1] < thumb.top else visible
            return max(0, min(max_scroll, scroll + page))

        if self._grab is None:
            return None
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._grab = None
            return scroll
        if event.type == pygame.MOUSEMOTION:
            if not event.buttons[0]:  # the release was missed (the window lost the mouse): the drag is over
                self._grab = None
                return None
            travel = self.track.height - self.thumb_rect(scroll, max_scroll, visible).height
            if travel <= 0:
                return scroll
            top = max(0, min(travel, event.pos[1] - self._grab - self.track.top))
            return round(top * max_scroll / travel)
        return None
