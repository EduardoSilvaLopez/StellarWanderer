from __future__ import annotations
import math
from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar


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
    RAW_WATER_WEIGHT = 1.0  # per Kg: the room a Kg of raw water takes, as ore does
    MINE_WEIGHT = 200.0

    INITIAL_MINES = 2
    MINES_MAX = 5  # the most mines the hold takes from an outpost

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
        self.raw_water: float = 0.0  # Kg, scooped from an icy world (see DeliverWater); not a supply of the outposts

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
        self.raw_water = old.raw_water
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
        result.raw_water = src['raw_water']
        return result

    def serialize(self) -> dict:
        return {
            'configuration': type(self).__qualname__,
            'air': self.air,
            'water': self.water,
            'food': self.food,
            'mines': self.mines,
            'ore': self.ore,
            'raw_water': self.raw_water,
        }

    def used_capacity(self) -> float:
        cargo = [self.air, self.water, self.food, self.mines, self.ore, self.raw_water]
        weights = [CargoHold.AIR_WEIGHT, CargoHold.WATER_WEIGHT, CargoHold.FOOD_WEIGHT, CargoHold.MINE_WEIGHT,
                   CargoHold.ORE_WEIGHT, CargoHold.RAW_WATER_WEIGHT]
        return sum(x*y for x, y in zip(cargo, weights))

    def free_capacity(self) -> float:
        return self.capacity - self.used_capacity()

    def load(self, supply: Supply, units: float) -> float:
        """Takes up to `units` of `supply` from the outpost into the hold: up to the supply's maximum and the room left.
        Whole units only for a supply that comes in whole units. Returns the units taken."""
        stock = getattr(self, supply.key)
        room = min(supply.maximum(self) - stock, self.free_capacity() / supply.weight)
        taken = min(units, room)
        if taken <= 0:
            return 0
        if supply.whole:
            taken = math.floor(taken)
        setattr(self, supply.key, stock + taken)
        return taken

    def unload(self, supply: Supply, units: float) -> float:
        """Gives up to `units` of `supply` from the hold back: down to none. Returns the units given."""
        stock = getattr(self, supply.key)
        given = min(units, stock)
        if given <= 0:
            return 0
        if supply.whole:
            given = math.floor(given)
        setattr(self, supply.key, stock - given)
        return given


@dataclass(frozen=True)
class Supply:
    """What an outpost gives a hold, in the cargo list: `key` is the hold's attribute that holds the stock, `weight` the
    room one unit takes, `maximum` the most the hold takes (from the hold itself), and `whole` says the units are whole
    (mines). The list SUPPLIES is what the outpost's cargo view shows, one row each."""

    key: str
    label: str
    unit: str
    weight: float
    maximum: Callable[[CargoHold], float]
    whole: bool = False


SUPPLIES: tuple[Supply, ...] = (
    Supply('air', 'Air', 'days', CargoHold.AIR_WEIGHT, lambda hold: hold.air_max),
    Supply('water', 'Water', 'days', CargoHold.WATER_WEIGHT, lambda hold: hold.water_max),
    Supply('food', 'Food', 'days', CargoHold.FOOD_WEIGHT, lambda hold: hold.food_max),
    Supply('mines', 'Mines', 'mines', CargoHold.MINE_WEIGHT, lambda hold: CargoHold.MINES_MAX, whole=True),
)
