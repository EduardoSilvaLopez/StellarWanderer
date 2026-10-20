from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from spaceships.ship import Ship


class CargoHold:
    # Days left at which air, water and food show their warning: red in the cargo list, and the ship's notice.
    WARNING_DAYS = {'air': 5.0, 'water': 2.0, 'food': 2.0}

    INITIAL_CARGO_CAPACITY = 2000
    AIR_WEIGHT = 0.1
    WATER_WEIGHT = 2.0
    FOOD_WEIGHT = 1.0
    ORE_WEIGHT = 1.0
    MINE_WEIGHT = 200.0

    INITIAL_AIR_MAX = 20.0
    INITIAL_WATER_MAX = 20.0
    INITIAL_FOOD_MAX = 20.0
    INITIAL_MINES = 2

    def __init__(self, ship: Ship) -> None:
        self.parent_ship: Ship = ship

        self.air_max: float = self.INITIAL_AIR_MAX
        self.air: float = self.air_max
        self.water_max: float = self.INITIAL_WATER_MAX
        self.water: float = self.water_max
        self.food_max: float = self.INITIAL_FOOD_MAX
        self.food: float = self.food_max
        self.capacity: int = self.INITIAL_CARGO_CAPACITY
        self.mines: int = self.INITIAL_MINES
        self.ore: int = 0

    @staticmethod
    def deserialize(ship: Ship, src: dict) -> CargoHold:
        result = CargoHold(ship)
        result.capacity = src['capacity']
        result.air_max = src['air_max']
        result.water_max = src['water_max']
        result.food_max = src['food_max']
        result.air = src['air']
        result.water = src['water']
        result.food = src['food']
        result.mines = src['mines']
        result.ore = src['ore']
        return result

    def serialize(self) -> dict:
        return {
            'capacity': self.capacity,
            'air_max': self.air_max,
            'air': self.air,
            'water_max': self.water_max,
            'water': self.water,
            'food_max': self.food_max,
            'food': self.food,
            'mines': self.mines,
            'ore': self.ore,
        }

    def used_capacity(self) -> float:
        cargo = [self.air, self.water, self.food, self.mines, self.ore]
        weights = [CargoHold.AIR_WEIGHT, CargoHold.WATER_WEIGHT, CargoHold.FOOD_WEIGHT, CargoHold.MINE_WEIGHT, CargoHold.ORE_WEIGHT]
        return sum(x*y for x, y in zip(cargo, weights))

    def free_capacity(self) -> float:
        return self.capacity - self.used_capacity()
