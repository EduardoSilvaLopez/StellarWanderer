from __future__ import annotations

import datetime
import random
from typing import List, TYPE_CHECKING

import Galaxies.Constants
from Galaxies.Rock import Rock
from Updating.Updatable import Updatable

if TYPE_CHECKING:
    from Galaxies.World import World

class Km2:

    SIZE = 1000  # Size of a Km2 in meters (1 km x 1 km)

    def __init__(self, parent_world: World, longitude: int, latitude: int, saved_alterations: dict):
        self.parent_world = parent_world
        self.longitude = longitude
        self.latitude = latitude
        self.seed = (self.longitude + self.latitude + self.parent_world.seed) % Galaxies.Constants.SEEDS_SCALING

        self.is_altered = False
        alteration_key = self.get_alterations_key()
        if saved_alterations is not None and alteration_key in saved_alterations:
            self.set_altered()

        my_random = random.Random(self.seed)
        rocksCount = max(my_random.gauss(50, 10), 0)
        self.rocks: List[Rock] = []
        for i in range(int(rocksCount)):
            newRock = Rock(self, self.longitude + my_random.randint(0, 1000), self.latitude + my_random.randint(0, 1000), saved_alterations)
            self.rocks.append(newRock)

    def set_altered(self) -> Km2:
        self.is_altered = True
        if not self.parent_world.is_altered:
            self.parent_world.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations = dict()

        for rock in self.rocks:
            rock_alterations = rock.get_alterations()
            if rock_alterations is None: continue
            alterations[rock.get_alterations_key()] = rock_alterations

        if alterations == {}:
            return None

        return alterations

    def stop_updating_rocks(self) -> None:
        for rock in self.rocks:
            rock.stop_updating()
        print("Stop updating: ", self.longitude, " ", self.latitude)

    def start_updating_rocks(self) -> None:
        for rock in self.rocks:
            rock.restart_updating()
        print("Start updating: ", self.longitude, " ", self.latitude)
