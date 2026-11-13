"""Broken instruments, and the repair mode. Each instrument registers its rectangle as it is drawn
(`Broken.register`), so that a broken one can be painted over, greyed and cracked, with its label and without its
numbers, and so that a click finds it. Each region of the cockpit (the upper part, the console) is painted
once it is drawn.

Repair mode starts with a click on the repair kits of the cargo: the mouse becomes a hammer. A left-click on a broken
instrument mends it with a repair kit, and the mode goes on while kits are left. Any other click, and a right-click,
ends the mode."""

from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple
import pygame

from spaceships.malfunction import Instrument

if TYPE_CHECKING:
    from spaceships.ship import Ship

BROKEN_FACE = (30, 32, 36)
BROKEN_EDGE = (78, 82, 88)
BROKEN_CRACK = (150, 155, 162)
BROKEN_TEXT = (110, 115, 122)

# A small hammer, its head at the top left, which is also the hotspot. X is black, a dot is transparent.
HAMMER = [
    "................",
    ".XXXXXXXX.......",
    "XXXXXXXXXX......",
    "XXXXXXXXXX......",
    "XXXXXXXXXX......",
    ".XXXXXXXX.......",
    "....XXXX........",
    "...XXXX.........",
    "..XXXX..........",
    ".XXXX...........",
    "XXXX............",
    "XXX.............",
    "XX..............",
    "X...............",
    "................",
    "................",
]
HAMMER_HOTSPOT = (2, 2)


def _ship() -> Optional[Ship]:
    """The ship of the game being played, if there is one."""
    import galaxies.people.player as player_module
    player = player_module.current_player
    return None if player is None else player.ship


class Broken:
    """The instruments' rectangles of the last draw of each region, and the look of a broken instrument."""

    _region: str = 'upper'
    _rects: Dict[str, Dict[Instrument, pygame.Rect]] = {}

    @staticmethod
    def begin(region: str) -> None:
        """Starts the drawing of `region`: the rectangles of its instruments are the ones registered from now on."""
        Broken._region = region
        Broken._rects[region] = {}

    @staticmethod
    def register(instrument: Instrument, rect: pygame.Rect) -> None:
        """The instrument is drawn at `rect` in the region being drawn."""
        Broken._rects.setdefault(Broken._region, {})[instrument] = rect

    @staticmethod
    def is_broken(instrument: Instrument) -> bool:
        ship = _ship()
        return ship is not None and instrument in ship.broken

    @staticmethod
    def paint(region: str, surface: pygame.Surface, fonts: Any, h: int) -> None:
        """Paints over each broken instrument drawn in `region`: greyed, cracked, with its label and no numbers."""
        ship = _ship()
        if ship is None:
            return
        font = fonts.get(max(9, int(h * 0.017)))
        for instrument, rect in Broken._rects.get(region, {}).items():
            if instrument in ship.broken:
                Broken._paint_one(surface, font, instrument, rect)

    @staticmethod
    def _paint_one(surface: pygame.Surface, font: Any, instrument: Instrument, rect: pygame.Rect) -> None:
        surface.set_clip(rect)
        pygame.draw.rect(surface, BROKEN_FACE, rect)
        # The cracks: zigzags from a point near the middle, the same for the same instrument every time.
        rng = random.Random(instrument.name)
        step = min(rect.width, rect.height) * 0.12
        for _ in range(rng.randint(2, 3)):
            x = rect.left + rect.width * rng.uniform(0.3, 0.7)
            y = rect.top + rect.height * rng.uniform(0.3, 0.7)
            angle = rng.uniform(0.0, math.tau)
            points = [(x, y)]
            for _ in range(rng.randint(4, 7)):
                angle += rng.uniform(-0.8, 0.8)
                length = step * rng.uniform(0.5, 1.0)
                x, y = x + math.cos(angle) * length, y + math.sin(angle) * length
                points.append((x, y))
            pygame.draw.lines(surface, BROKEN_CRACK, False, points, 1)
        pygame.draw.rect(surface, BROKEN_EDGE, rect, 1)
        label = font.render(instrument.value, True, BROKEN_TEXT)
        surface.blit(label, label.get_rect(center=rect.center))
        surface.set_clip(None)

    @staticmethod
    def instrument_at(position: Tuple[int, int]) -> Optional[Instrument]:
        """The broken instrument drawn under `position`, if there is one."""
        ship = _ship()
        if ship is None:
            return None
        for rects in Broken._rects.values():
            for instrument, rect in rects.items():
                if instrument in ship.broken and rect.collidepoint(position):
                    return instrument
        return None


class Repair:
    """The repair mode: a repair kit in hand, the mouse is a hammer until the mode ends."""

    active: bool = False

    @staticmethod
    def start() -> None:
        Repair.active = True
        Repair._set_cursor(lambda: pygame.mouse.set_cursor(*Repair._hammer_cursor()))

    @staticmethod
    def cancel() -> None:
        Repair.active = False
        Repair._set_cursor(lambda: pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW))

    @staticmethod
    def _set_cursor(change: Callable[[], None]) -> None:
        """The mouse's look is only a hint: a system that cannot change it keeps the arrow, and the game goes on."""
        try:
            change()
        except pygame.error:
            pass

    @staticmethod
    def click(position: Tuple[int, int], button: int, ship: Ship) -> None:
        """A click in repair mode: a left-click on a broken instrument mends it with a kit, and the mode goes on
        while kits are left. Any other click ends the mode."""
        if button == 1:
            instrument = Broken.instrument_at(position)
            if instrument is not None and ship.repair_instrument(instrument) and ship.cargo_hold.repair_kit > 0:
                return
        Repair.cancel()

    @staticmethod
    def _hammer_cursor() -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, ...], Tuple[int, ...]]:
        data, mask = pygame.cursors.compile(HAMMER, black='X', white='.', xor='o')
        return (16, 16), HAMMER_HOTSPOT, data, mask
