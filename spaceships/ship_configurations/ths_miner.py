from __future__ import annotations

from spaceships.cargo_hold import CargoHold
from spaceships.ship import Ship


class ThsMiner(Ship):
    """The standard miner of Those-Who-Share. Its hull is a box of 4 m high, 4 m wide and 8 m deep."""

    NAME = 'THS miner'
    ENERGY_MAX = 1500e9  # Wh, where 1e9 is 1 GWh . Daily european consumption is ~ 42GWh (0.042 TWh)
    PRECARIOUSNESS = 0.8  # The maximum is 1. Better ships will decrease this.
    TEMP_SHIELD_REDUCTION = 1  # Maximum external temperature allowed, which brings TEMP_MAX inside the ship.
    FORWARD_BACKWARD_ACC = 15.0  # meters per second squared
    BRAKE_ACC = 15.0  # m/s^2, never less than the acceleration
    HEIGHT = 4
    WIDTH = 4
    DEPTH = 8

    class StandardHold(CargoHold):
        CAPACITY = 10000
        AIR_MAX = 60.0
        WATER_MAX = 56.0
        FOOD_MAX = 50.0

    CARGO_HOLD = StandardHold
