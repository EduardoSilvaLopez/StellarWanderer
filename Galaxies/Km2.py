from __future__ import annotations

import logging; logger = logging.getLogger(__name__)

import datetime
import random
from typing import List, TYPE_CHECKING, Optional

from Updating.Updatable import Updatable

import Galaxies.Constants
from Galaxies.Rock import Rock
from Galaxies.OreField import OreField

if TYPE_CHECKING:
    from Galaxies.World import World

class Km2:

    SIZE = 1000  # Size of a Km2 in meters (1 km x 1 km)

    def __init__(self, parent_world: World, longitude: int, latitude: int, saved_alterations: dict):
        self.parent_world = parent_world
        self.longitude: int = longitude
        self.latitude: int = latitude
        self.seed: int = (self.longitude + self.latitude + self.parent_world.seed) % Galaxies.Constants.SEEDS_SCALING

        self.is_altered: bool = False
        alterations_key: str = self.get_alterations_key()
        own_alterations: Optional[dict] = saved_alterations.get(alterations_key) if saved_alterations is not None else None
        if own_alterations is not None:
            self.set_altered()

        my_random: random.Random = random.Random(self.seed)
        rocksCount: int = max(my_random.gauss(50, 10), 0)
        self.rocks: List[Rock] = []
        self.molten_rocks: List[str] = []
        self.ore_fields: List[OreField] = []

        all_rocks_alterations: Optional[dict] = own_alterations.get('rocks') if own_alterations is not None else None
        molten_rocks: Optional[dict] = own_alterations.get('molten_rocks') if own_alterations is not None else None
        for i in range(int(rocksCount)):
            rock_lon = self.longitude + my_random.randint(0, 1000)
            rock_lat = self.latitude + my_random.randint(0, 1000)
            rock_key = f"{rock_lon} {rock_lat}"
            if molten_rocks is not None and rock_key in molten_rocks:
                logger.debug(f"Molten rock detected at ({rock_key})")
                self.molten_rocks.append(rock_key)
                continue
            newRock = Rock(
                self,
                rock_lon,
                rock_lat,
                all_rocks_alterations
                )
            self.rocks.append(newRock)

        ore_fields: Optional[dict] = own_alterations.get('ore_fields') if own_alterations is not None else None
        if ore_fields and len(ore_fields) > 0:
            self.ore_fields = [OreField.generate_loaded(self, f) for f in ore_fields]

        logger.debug(f"Km2 created at {self.longitude}, {self.latitude}. {len(self.rocks)} rocks, {len(self.molten_rocks)} molten, {len(self.ore_fields)} ore fields.")

    def set_altered(self) -> Km2:
        self.is_altered = True
        if not self.parent_world.is_altered:
            self.parent_world.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations = dict()

        # Rocks
        rocks = dict()
        for rock in self.rocks:
            rock_alterations = rock.get_alterations()
            if rock_alterations is None:
                continue
            rocks[rock.get_alterations_key()] = rock_alterations
        alterations['rocks'] = rocks

        # Molten rocks
        alterations['molten_rocks'] = self.molten_rocks

        # Ore fields
        alterations['ore_fields'] = [f.serialize() for f in self.ore_fields]

        if len(rocks) + len(self.molten_rocks) + len(self.ore_fields) <= 0:
            return None

        return alterations

    def stop_updating_rocks(self) -> None:
        for rock in self.rocks:
            rock.stop_updating()
        logger.info(f"Stop updating: {self.longitude} {self.latitude}")

    def start_updating_rocks(self, update_time: datetime) -> None:
        for rock in self.rocks:
            rock.start_updating(update_time)
        logger.info(f"Start updating: {self.longitude} {self.latitude}")

    def melt_rock(self, tgt_rock: Rock) -> Km2:
        self.molten_rocks.append(tgt_rock.get_alterations_key())
        self.rocks.remove(tgt_rock)
        if tgt_rock.is_ore_rich():
            self.ore_fields.append(OreField.generate_new(tgt_rock))
        return self
