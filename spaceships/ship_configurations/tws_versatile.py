from __future__ import annotations

from spaceships.cargo_hold import CargoHold
from spaceships.ship import Ship


class TwsVersatile(Ship):
    """A versatile, still mining-oriented ship. Less cargo than a standard miner, though."""

    NAME = 'TWS Versatile'
    COCKPIT_TEXTURE = 'cockpit_ths_versatile.png'
    ENERGY_MAX = 4e9  # Wh
    PRECARIOUSNESS = 0.15  # The maximum is 1. Better ships will decrease this.
    PRESSURE_MAX = 1e6 # Pa . 1e5 is one atmosphere.
    FORWARD_BACKWARD_ACC = 30.0  # meters per second squared
    UP_DOWN_ACC = 30.0  # m/s^2
    RIGHT_LEFT_ACC = 15  # m/s^2
    BRAKE_ACC = 30.0  # m/s^2, never less than the acceleration
    HEIGHT = 4
    WIDTH = 4
    DEPTH = 6
    MASS = 10000  # Kg

    class StandardHold(CargoHold):
        CAPACITY = 5000
        AIR_MAX = 120.0
        WATER_MAX = 110.0
        FOOD_MAX = 100.0

    CARGO_HOLD = StandardHold
