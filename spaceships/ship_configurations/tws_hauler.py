from __future__ import annotations

from spaceships.cargo_hold import CargoHold
from spaceships.ship import Ship


class TwsHauler(Ship):
    """A massive hauler for large amounts of ore."""

    NAME = 'TWS Hauler'
    COCKPIT_TEXTURE = 'cockpit_ths_miner.png'
    ENERGY_MAX = 2.5e9  # Wh
    ENGINE_ENERGY_PER_MOMENTUM = 40.0  # J per (kg*m/s): with ENERGY_MAX, 4e6 m/s of change of velocity per battery
    PRECARIOUSNESS = 0.1  # The maximum is 1. Better ships will decrease this.
    PRESSURE_MAX = 5e5 # Pa . 1e5 is one atmosphere.
    FORWARD_BACKWARD_ACC = 16.0  # meters per second squared
    UP_DOWN_ACC = 16.0  # m/s^2
    RIGHT_LEFT_ACC = 5  # m/s^2
    BRAKE_ACC = 20.0  # m/s^2, never less than the acceleration
    HEIGHT = 6
    WIDTH = 6
    DEPTH = 12
    MASS = 20000  # Kg

    class StandardHold(CargoHold):
        CAPACITY = 20000
        AIR_MAX = 180.0
        WATER_MAX = 170.0
        FOOD_MAX = 160.0

    CARGO_HOLD = StandardHold
