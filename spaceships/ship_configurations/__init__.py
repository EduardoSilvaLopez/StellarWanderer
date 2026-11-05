"""The ship configurations. Importing this package loads every configuration, which registers its class by name (see
Ship.by_name and CargoHold.by_name), so a saved ship can be built again."""

from spaceships.ship_configurations.tws_miner import TwsMiner
from spaceships.ship_configurations.tws_shabby_miner import ShabbyTwsMiner
from spaceships.ship_configurations.tws_versatile import TwsVersatile

__all__ = ['TwsMiner', 'ShabbyTwsMiner', 'TwsVersatile']
