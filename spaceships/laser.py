from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import time

from common import audio
from galaxies.rock import Rock

if TYPE_CHECKING:
    from spaceships.ship import Ship


class Laser:
    """The ship's laser: fired at the rock the scanner targets, heating it. Its sounds: a zap when it is switched on,
    the beam's loop while it fires, and a sizzle while it is on a rock. `fired_at` is when it was switched on (a
    time.monotonic() value), which the muzzle flash of graphics/laser.py starts from."""

    def __init__(self, ship: Ship) -> None:
        self.ship = ship
        self.hitting_rock: Optional[Rock] = None
        self.firing: bool = False
        self.fired_at: float = float('-inf')

    def fire(self, targeted_rock: Optional[Rock], time_passed: int) -> None:
        if not self.firing:
            audio.play('laser_on')
            self.fired_at = time.monotonic()
        self.hitting_rock = targeted_rock
        self.firing = True
        audio.set_loop('laser', True)
        audio.set_loop('laser_hit', targeted_rock is not None)
        if self.hitting_rock:
            self.hitting_rock.increase_temperature(time_passed)
            # 222Wh for 1 degree 1 ton. Laser can 500 degrees so ~10KWh per second.
            self.ship.energy -= 20 * time_passed * Rock.TEMP_RISE_RATE

    def cease_fire(self) -> None:
        if not self.firing:
            return
        self.firing = False
        audio.set_loop('laser', False)
        audio.set_loop('laser_hit', False)
        self.hitting_rock = None
