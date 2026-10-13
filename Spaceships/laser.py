from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from Galaxies.rock import Rock

if TYPE_CHECKING:
    from Spaceships.ship import Ship

class Laser:
    def __init__(self, ship: Ship):
        self.ship = ship
        self.hitting_rock: Optional[Rock] = None
        self.firing: bool = False

    def fire(self, targeted_rock: Optional[Rock], time_passed: int) -> None:
        self.hitting_rock = targeted_rock
        self.firing = True
        if (self.hitting_rock):
            self.hitting_rock.increase_temperature(time_passed)

    def cease_fire(self) -> None:
        if (not self.firing):
            return
        self.firing = False
        self.hitting_rock = None
