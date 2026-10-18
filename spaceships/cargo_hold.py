from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from spaceships.ship import Ship


class CargoHold:
    # Days left at which air, water and food show their warning: red in the cargo list, and the ship's notice.
    WARNING_DAYS = {'air': 5.0, 'water': 2.0, 'food': 2.0}

    INITIAL_AIR_MAX = 25.0
    INITIAL_WATER_MAX = 25.0
    INITIAL_FOOD_MAX = 25.0
    INITIAL_ORE_MAX = 5000
    INITIAL_MINES_MAX = 5
    INITIAL_MINES = 2

    def __init__(self, ship: Ship) -> None:
        self.parent_ship: Ship = ship

        self.air_max: float = self.INITIAL_AIR_MAX
        self.air: float = self.air_max
        self.water_max: float = self.INITIAL_WATER_MAX
        self.water: float = self.water_max
        self.food_max: float = self.INITIAL_FOOD_MAX
        self.food: float = self.food_max
        self.mines_max: int = self.INITIAL_MINES_MAX
        self.mines: int = self.INITIAL_MINES
        self.ore = 0.0

    @staticmethod
    def load(ship: Ship, src: dict) -> CargoHold:
        result = CargoHold(ship)
        result.air_max = src['air_max']
        result.water_max = src['water_max']
        result.food_max = src['food_max']
        result.mines_max = src['mines_max']
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
            'air_max': self.air_max,
            'air': self.air,
            'water_max': self.water_max,
            'water': self.water,
            'food_max': self.food_max,
            'food': self.food,
            'mines_max': self.mines_max,
            'mines': self.mines,
            'ore': self.ore,
        }
