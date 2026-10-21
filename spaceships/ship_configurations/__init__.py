"""The ship configurations. Importing this package loads every configuration, which registers its class by name (see
Ship.by_name and CargoHold.by_name), so a saved ship can be built again."""

from spaceships.ship_configurations.ths_miner import ThsMiner
from spaceships.ship_configurations.ths_shabby_miner import ShabbyThsMiner

__all__ = ['ThsMiner', 'ShabbyThsMiner']
