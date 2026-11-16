"""The ship configurations. Importing this package loads every configuration, which registers its class by name (see
Ship.by_name and CargoHold.by_name), so a saved ship can be built again."""

from universe.artifacts.spaceships.configurations.tws_hauler import TwsHauler
from universe.artifacts.spaceships.configurations.tws_miner import TwsMiner
from universe.artifacts.spaceships.configurations.tws_shabby_miner import ShabbyTwsMiner
from universe.artifacts.spaceships.configurations.tws_versatile import TwsVersatile

__all__ = ['TwsHauler', 'TwsMiner', 'ShabbyTwsMiner', 'TwsVersatile']
