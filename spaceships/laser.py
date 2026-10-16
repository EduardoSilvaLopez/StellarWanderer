from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from galaxies.rock import Rock

if TYPE_CHECKING:
    from spaceships.ship import Ship


class Laser:
    def __init__(self, ship: Ship) -> None:
        self.ship = ship
        self.hitting_rock: Optional[Rock] = None
        self.firing: bool = False

    def fire(self, targeted_rock: Optional[Rock], time_passed: int) -> None:
        self.hitting_rock = targeted_rock
        self.firing = True
        if self.hitting_rock:
            self.hitting_rock.increase_temperature(time_passed)
            # 222Wh for 1 degree 1 ton. Laser can 500 degrees so ~10KWh per second.
            self.ship.energy -= 20 * time_passed * Rock.TEMP_RISE_RATE

    def cease_fire(self) -> None:
        if not self.firing:
            return
        self.firing = False
        self.hitting_rock = None
