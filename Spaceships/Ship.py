from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from Spaceships.CargoHold import CargoHold
from Spaceships.Laser import Laser
if TYPE_CHECKING:
    from Player import Player

class Ship:
    HEIGHT = 10 # meters, up to the camera

    UP_DOWN_SPEED = 1  # meters per second
    RIGHT_LEFT_SPEED = 10  # meters per second
    FORWARD_BACKWARD_SPEED = 10  # meters per second
    ROTATION_SPEED = 10  # degrees per game second

    def __init__(self, owner: Player) -> None:
        self.owner = owner
        self.laser = Laser(self)
        self.cargo_hold: CargoHold = CargoHold(self)

    @staticmethod
    def load(owner: Player, src: dict) -> Ship:
        result = Ship(owner)
        result.cargo_hold = CargoHold.load(result, src['cargo_hold'])
        return result

    def serialize(self) -> dict:
        return {
            'cargo_hold': self.cargo_hold.serialize()
        }
