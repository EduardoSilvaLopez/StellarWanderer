from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple

import math

if TYPE_CHECKING:
    from Spaceships.ship import Ship


class CargoHold:
    # Days left at which air, water and food show their warning: red in the cargo list, and the ship's notice.
    WARNING_DAYS = {'air': 5.0, 'water': 2.0, 'food': 2.0}

    def __init__(self, ship: Ship) -> None:
        self.parent_ship: Ship = ship

        self.air: float = 28.0
        self.water: float = 28.0
        self.food: float = 28.0
        self.mines: int = 5
        self.ore = 0.0

    @staticmethod
    def load(ship: Ship, src: dict) -> CargoHold:
        result = CargoHold(ship)
        if 'air' in src:
            result.air = src['air']
        if 'water' in src:
            result.water = src['water']
        if 'food' in src:
            result.food = src['food']
        if 'mines' in src:
            result.mines = src['mines']
        if 'ore' in src:
            result.ore = src['ore']
        return result

    def serialize(self) -> dict:
        return {
            'air': self.air,
            'water': self.water,
            'food': self.food,
            'mines': self.mines,
            'ore': self.ore,
        }
