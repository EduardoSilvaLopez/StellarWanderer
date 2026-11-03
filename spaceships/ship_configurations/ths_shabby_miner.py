from __future__ import annotations

from spaceships.cargo_hold import CargoHold
from spaceships.ship import Ship


class ShabbyThsMiner(Ship):
    """The ship a Those-Who-Share pilot starts with. Its hull is a box of 4 m high, 4 m wide and 6 m deep.
    Its cargo hold grows with the reputation: first repaired (no longer shabby), then extended."""

    NAME = 'Shabby THS miner'
    ENERGY_MAX = 400e9  # Wh, where 1e9 is 1 GWh . Daily european consumption is ~ 42GWh (0.042 TWh)
    PRECARIOUSNESS = 1  # The maximum. Better ships will decrease this.
    PRESSURE_MAX = 1.5e5 # Pa . 1e5 is one atmosphere.
    FORWARD_BACKWARD_ACC = 15.0  # meters per second squared
    UP_DOWN_ACC = 15.0  # m/s^2
    RIGHT_LEFT_ACC = 5  # m/s^2
    BRAKE_ACC = 20.0  # m/s^2, never less than the acceleration
    HEIGHT = 4
    WIDTH = 4
    DEPTH = 6
    MASS = 15000  # Kg

    class ShabbyHold(CargoHold):
        CAPACITY = 2000
        AIR_MAX = 15.0
        WATER_MAX = 15.0
        FOOD_MAX = 15.0

    class StandardHold(CargoHold):
        CAPACITY = 3000
        AIR_MAX = 20.0
        WATER_MAX = 20.0
        FOOD_MAX = 20.0

    class ExtendedHold(CargoHold):
        CAPACITY = 5000
        AIR_MAX = 24.0
        WATER_MAX = 22.0
        FOOD_MAX = 20.0

    CARGO_HOLD = ShabbyHold
