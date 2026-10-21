from __future__ import annotations

from spaceships.cargo_hold import CargoHold
from spaceships.ship import Ship


class ThsMiner(Ship):
    """The standard miner of Those-Who-Share."""

    ENERGY_MAX = 400e9  # Wh, where 1e9 is 1 GWh . Daily european consumption is ~ 42GWh (0.042 TWh)
    PRECARIOUSNESS = 0.8  # The maximum is 1. Better ships will decrease this.
    TEMP_SHIELD_REDUCTION = 1  # Maximum external temperature allowed, which brings TEMP_MAX inside the ship.

    class StandardHold(CargoHold):
        CAPACITY = 10000
        AIR_MAX = 40.0
        WATER_MAX = 38.0
        FOOD_MAX = 36.0

    CARGO_HOLD = StandardHold
