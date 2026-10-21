from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar


if TYPE_CHECKING:
    from spaceships.ship import Ship


class CargoHold(ABC):
    """What the ship carries: air, water, food, mines and ore, and the room they take. A configuration (a subclass,
    see spaceships/ship_configurations) gives the capacity and the maxima; the stock is saved, and the configuration is
    found again by its qualified name (the class name, prefixed by the ship's name for a hold of a ship)."""

    # Days left at which air, water and food show their warning: red in the cargo list, and the ship's notice.
    WARNING_DAYS = {'air': 5.0, 'water': 2.0, 'food': 2.0}

    AIR_WEIGHT = 0.1
    WATER_WEIGHT = 2.0
    FOOD_WEIGHT = 1.0
    ORE_WEIGHT = 1.0
    MINE_WEIGHT = 200.0

    INITIAL_MINES = 2

    # Set by each configuration, never here.
    CAPACITY: ClassVar[int]
    AIR_MAX: ClassVar[float]
    WATER_MAX: ClassVar[float]
    FOOD_MAX: ClassVar[float]

    # Every configuration, by qualified name (ShabbyThsMiner.StandardHold, not StandardHold: two holds share that name).
    by_name: ClassVar[dict[str, type[CargoHold]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        CargoHold.by_name[cls.__qualname__] = cls

    def __init__(self, ship: Ship) -> None:
        self.parent_ship: Ship = ship

        self.air: float = self.air_max
        self.water: float = self.water_max
        self.food: float = self.food_max
        self.mines: int = self.INITIAL_MINES
        self.ore: int = 0

    # region Configuration
    @property
    def capacity(self) -> int:
        return self.CAPACITY

    @property
    def air_max(self) -> float:
        return self.AIR_MAX

    @property
    def water_max(self) -> float:
        return self.WATER_MAX

    @property
    def food_max(self) -> float:
        return self.FOOD_MAX

    def take_stock_from(self, old: CargoHold) -> CargoHold:
        """Takes the stock of `old`: mines, ore, air, water and food. An air, water or food maximum that changed refills
        its stock instead. The capacity is not stock, so nothing refills it."""
        self.mines = old.mines
        self.ore = old.ore
        self.air = self.air_max if self.air_max != old.air_max else old.air
        self.water = self.water_max if self.water_max != old.water_max else old.water
        self.food = self.food_max if self.food_max != old.food_max else old.food
        return self
    # endregion

    @staticmethod
    def deserialize(ship: Ship, src: dict) -> CargoHold:
        result = CargoHold.by_name[src['configuration']](ship)
        result.air = src['air']
        result.water = src['water']
        result.food = src['food']
        result.mines = src['mines']
        result.ore = src['ore']
        return result

    def serialize(self) -> dict:
        return {
            'configuration': type(self).__qualname__,
            'air': self.air,
            'water': self.water,
            'food': self.food,
            'mines': self.mines,
            'ore': self.ore,
        }

    def used_capacity(self) -> float:
        cargo = [self.air, self.water, self.food, self.mines, self.ore]
        weights = [CargoHold.AIR_WEIGHT, CargoHold.WATER_WEIGHT, CargoHold.FOOD_WEIGHT, CargoHold.MINE_WEIGHT,
                   CargoHold.ORE_WEIGHT]
        return sum(x*y for x, y in zip(cargo, weights))

    def free_capacity(self) -> float:
        return self.capacity - self.used_capacity()
