from __future__ import annotations

from spaceships.cargo_hold import CargoHold
from spaceships.ship import Ship


class ShabbyThsMiner(Ship):
    """The ship a Those-Who-Share pilot starts with.
    Its cargo hold grows with the reputation: first repaired (no longer shabby), then extended."""

    ENERGY_MAX = 200e9  # Wh, where 1e9 is 1 GWh . Daily european consumption is ~ 42GWh (0.042 TWh)
    PRECARIOUSNESS = 1  # The maximum. Better ships will decrease this.
    TEMP_SHIELD_REDUCTION = 1  # Maximum external temperature allowed, which brings TEMP_MAX inside the ship.

    class ShabbyHold(CargoHold):
        CAPACITY = 2000
        AIR_MAX = 20.0
        WATER_MAX = 20.0
        FOOD_MAX = 20.0

    class StandardHold(CargoHold):
        CAPACITY = 3000
        AIR_MAX = 20.0
        WATER_MAX = 20.0
        FOOD_MAX = 20.0

    class ExtendedHold(CargoHold):
        CAPACITY = 5000
        AIR_MAX = 20.0
        WATER_MAX = 20.0
        FOOD_MAX = 20.0

    CARGO_HOLD = ShabbyHold
