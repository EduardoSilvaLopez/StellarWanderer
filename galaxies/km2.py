from __future__ import annotations

from datetime import datetime
import math
import random
from typing import List, TYPE_CHECKING, Optional

import logging

from galaxies import seeds
from galaxies.rock import Rock
from galaxies.ore_fields import OreField
from common.updating import update_queue

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.world import World

logger = logging.getLogger(__name__)


class Km2:

    SIZE = 1000  # Size of a Km2 in meters (1 km x 1 km)

    def __init__(self, parent_world: World, longitude: int, latitude: int, saved_alterations: dict) -> None:
        from galaxies.outpost import Outpost  # local: the outpost module needs the world, which needs this one
        self.parent_world = parent_world
        self.longitude: int = longitude
        self.latitude: int = latitude
        self.seed: int = seeds.derive(self.parent_world.seed, 'km2', self.longitude, self.latitude)

        self.is_altered: bool = False
        own_alterations: Optional[dict] = ((saved_alterations or {}).get('Km2s') or {}).get(self.get_alterations_key())
        if own_alterations is not None:
            self.set_altered()
        own: dict = own_alterations or {}

        # From the planet (if at all):
        self.outpost: Optional[Outpost] = None
        if not self.parent_world.parent_planet:
            self.outpost = self.parent_world.get_outpost_for(self)
            if self.outpost:
                self.outpost.prepare()

        my_random: random.Random = random.Random(self.seed)
        rocks_count: int = max(int(parent_world.rocks_prevalence * my_random.gauss(60, 20)), 0)
        self.rocks: List[Rock] = []
        self.molten_rocks: List[str] = []
        self.ore_fields: List[OreField] = []

        all_rocks_alterations: Optional[dict] = own.get('rocks')
        molten_rocks: Optional[dict] = own.get('molten_rocks')
        outpost_center = ((self.outpost.longitude, self.outpost.latitude)
                          if self.outpost else None)
        rich_ore_count: int = 0
        for _ in range(int(rocks_count)):
            rock_lon = self.longitude + my_random.randint(0, 999)
            rock_lat = self.latitude + my_random.randint(0, 999)
            if outpost_center and math.hypot(rock_lon - outpost_center[0], rock_lat
                                             - outpost_center[1]) < Outpost.CLEARED_RADIUS:
                continue  # COULD still collide with an outpost of a nearby Km - this would be funny, not a bug.
            rock_key = f"{rock_lon} {rock_lat}"
            if molten_rocks is not None and rock_key in molten_rocks:
                logger.debug(f"Molten rock detected at ({rock_key})")
                self.molten_rocks.append(rock_key)
                continue
            new_rock = Rock(
                self,
                rock_lon,
                rock_lat,
                all_rocks_alterations
                )
            self.rocks.append(new_rock)
            if new_rock.is_ore_rich():
                rich_ore_count += 1

        ore_fields: Optional[dict] = own.get('ore_fields')
        if ore_fields:
            self.ore_fields = [OreField.deserialize(self, f) for f in ore_fields]

        if self.is_altered:
            logger.debug(f"Km2 created at {self.longitude}, {self.latitude}. {len(self.rocks)} rocks, {rich_ore_count} "
            f"ore-rich, {len(self.molten_rocks)} molten, {len(self.ore_fields)} ore fields.")

    # region Alterations
    def set_altered(self) -> Km2:
        self.is_altered = True
        if not self.parent_world.is_altered:
            self.parent_world.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations = {}

        # Rocks - only altered
        rocks = {}
        for rock in self.rocks:
            rock_alterations = rock.get_alterations()
            if rock_alterations is None:
                continue
            rocks[rock.get_alterations_key()] = rock_alterations
        alterations['rocks'] = rocks

        # Molten rocks - all are alterations
        alterations['molten_rocks'] = self.molten_rocks

        # Ore fields - all are alterations
        alterations['ore_fields'] = [f.serialize() for f in self.ore_fields]

        if len(rocks) + len(self.molten_rocks) + len(self.ore_fields) <= 0:
            return None

        return alterations
    # endregion

    # region Updating
    def stop_updating(self) -> None:
        for rock in self.rocks:
            rock.stop_updating()

        for mine in (m for field in self.ore_fields for m in field.mines):
            mine.stop_updating()

        logger.info(f"Stop updating: {self.longitude} {self.latitude}")

    def start_updating(self, update_time: datetime) -> None:
        for rock in self.rocks:
            rock.start_updating(update_time)

        for mine in (m for field in self.ore_fields for m in field.mines):
            if mine not in update_queue:  # a mine already queued keeps its entry (see OreMine.update)
                mine.update(update_time)

        logger.info(f"Start updating: {self.longitude} {self.latitude}")
    # endregion

    def melt_rock(self, tgt_rock: Rock) -> Km2:
        self.molten_rocks.append(tgt_rock.get_alterations_key())
        self.rocks.remove(tgt_rock)
        self.set_altered()
        if tgt_rock.is_ore_rich():
            self.ore_fields.append(OreField.from_rock(tgt_rock))
        return self
