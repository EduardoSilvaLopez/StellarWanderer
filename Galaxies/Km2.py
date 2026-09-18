from __future__ import annotations

import datetime
import random
from typing import List, TYPE_CHECKING

import Galaxies.Constants
from Galaxies.Rock import Rock
from Updating.Updatable import Updatable

if TYPE_CHECKING:
    from Galaxies.World import World

class Km2(Updatable):

    SIZE = 1000  # Size of a Km2 in meters (1 km x 1 km)

    def __init__(self, parent_world: World, longitude: int, latitude: int, saved_alterations: dict):
        self.parent_world = parent_world
        self.longitude = longitude
        self.latitude = latitude
        self.seed = (self.longitude + self.latitude + self.parent_world.seed) % Galaxies.Constants.SEEDS_SCALING

        self.is_altered = False
        self.is_updating = False
        self.saved_alterations = None
        alteration_key = self.get_alterations_key()
        if saved_alterations is not None and alteration_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alteration_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        my_random = random.Random(self.seed)
        rocksCount = max(my_random.gauss(50, 10), 0)
        self.rocks: List[Rock] = []
        for i in range(int(rocksCount)):
            self.add_rock(self.longitude + my_random.randint(0, 1000), self.latitude + my_random.randint(0, 1000))

    def set_altered(self) -> Rock:
        self.is_altered = True
        self.parent_world.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations = dict()
        if self.is_altered:
            for rock in self.rocks:
                if rock.is_altered:
                    alterations[rock.get_alterations_key()] = rock.get_alterations()
        if alterations == {}:
            return None
        return alterations

    def get_next_update(self) -> datetime:
        if not self.is_altered:
            raise Exception("Not altered, why is this being asked?")
        if self.next_update is None:
            raise Exception("Next update of this Km2 is none, why was this asked?")
        return self.next_update

    def update(self, game_date_time: datetime) -> None:
        if not self.is_altered:
            raise Exception("Not altered, why is this being updated?")
        self.is_updating = True

        # Km2 do not need updates (yet) but must pass the command to their children.
        for rock in self.rocks:
            rock.update(game_date_time)

    def stop_updating(self) -> None:
        if not self.is_altered: return
        if not self.is_updating: return
        self.is_updating = False

        for rock in self.rocks:
            rock.stop_updating()
        print("Stop updating: ", self.longitude, " ", self.latitude)

    def restart_updating(self) -> None:
        if not self.is_altered:
            raise Exception("Not altered, what does it mean 'restart updating'?")
        if self.is_updating: return
        self.is_updating = True

        for rock in self.rocks:
            rock.restart_updating()
        print("Restart updating: ", self.longitude, " ", self.latitude)

    def add_rock(self, longitude: int, latitude: int) -> Rock:
        newRock = Rock(self, longitude, latitude)
        self.rocks.append(newRock)
        return newRock