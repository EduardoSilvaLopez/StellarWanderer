from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple

import math

if TYPE_CHECKING:
    from Spaceships.Ship import Ship


class CargoHold:
    class CargoElement(Enum):
        MINES = 1
        ORE = 2

    def __init__(self, ship: Ship) -> None:
        self.parent_ship: Ship = ship
        self.content: dict = {
            self.CargoElement.MINES: 0,
            self.CargoElement.ORE: 0
        }

    @staticmethod
    def load(ship: Ship, src: dict) -> CargoHold:
        result = CargoHold(ship)
        result.content[result.CargoElement.MINES] = src[result.CargoElement.MINES.name]
        result.content[result.CargoElement.ORE] = src[result.CargoElement.ORE.name]
        return result

    def serialize(self) -> dict:
        return {
            self.CargoElement.MINES.name: self.content[self.CargoElement.MINES],
            self.CargoElement.ORE.name:  self.content[self.CargoElement.ORE]
        }
