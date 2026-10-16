from __future__ import annotations

import logging
from random import Random

from datetime import datetime, timedelta
import math
from typing import TYPE_CHECKING, Optional

from common.updating import Updatable
from common.updating import update_queue

if TYPE_CHECKING:
    from galaxies.km2 import Km2

logger = logging.getLogger(__name__)


class Rock(Updatable):
    TEMP_RISE_RATE = 500.0  # Temp. raise for a 1 square cube rock in 1 second.
    BASE_COOLING_PERIOD = 60 * 60  # Once per hour.
    COOLING_FACTOR = 0.999  # Loose 0.1% of their temperature. For 1m3.
    TEMP_MAX = 2000.0  # Boom.
    ORE_RICH_THRESHOLD = 0.9998

    def __init__(self, parent_km2: Km2, longitude: int, latitude: int, saved_parent_alterations: dict) -> None:
        import random
        self.parent_km2: Km2 = parent_km2
        my_random: Random = random.Random(parent_km2.seed + 1e3*latitude + longitude)
        self.size: float = abs(my_random.lognormvariate(math.log(10), 0.8))
        self.longitude: int = longitude
        # Height of the rock's centre above the ground, in metres (the rock is drawn and hit-tested
        # around this point, so it can sit partly under the ground).
        self.altitude: float = max(0.3 - abs(my_random.gauss(0, 0.25)), -0.5) * self.size
        self.latitude: int = latitude
        self.orientation: float = my_random.random() * 180 - 90
        self.tilt: float = my_random.random() * 45
        self.composition: float = self._calculate_initial_composition(my_random)
        self.initial_color: tuple = self._calculate_initial_color(my_random)
        # Seed of the rock's irregular shape (graphics/rock_shape.py). Drawn last, so every value above is as before.
        self.shape_seed: int = my_random.getrandbits(32)
        self.temperature: float = 0.0
        self._adjust_color()

        self.last_updated_at: Optional[datetime] = None
        self.next_update_at: Optional[datetime] = None
        alterations_key: str = self.get_alterations_key()
        if saved_parent_alterations is not None:
            rock_alterations = saved_parent_alterations.get(alterations_key)
            if rock_alterations is not None:
                self._set_last_updated(datetime.strptime(rock_alterations['last_updated_at'], '%Y-%m-%d %H:%M:%S.%f'))
                if 'temperature' in rock_alterations:
                    self.temperature = rock_alterations['temperature']
                    self._adjust_color()

                self.next_update_at = self.last_updated_at + timedelta(seconds=1)
                update_queue.add(self)
                logger.info(f"Altered rock loaded at {self.longitude}, {self.latitude} with temperature {self.temperature}°. Queue size: {len(update_queue._queue)}")

    def _set_last_updated(self, new_date_time: datetime) -> Rock:
        self.last_updated_at = new_date_time
        if not self.parent_km2.is_altered:
            self.parent_km2.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.longitude) + ' ' + str(self.latitude)

    def get_alterations(self) -> dict:
        '''The change, expressed as dictionary.'''
        if self.temperature == 0.0:
            return None

        result: dict = {"temperature": self.temperature}
        if self.last_updated_at:
            result['last_updated_at'] = self.last_updated_at.strftime('%Y-%m-%d %H:%M:%S.%f')
        return result

    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        ''' Called by UpdateQueue after removing the object form it (it can re-insert, but FIFO)'''
        if not self.get_alterations():
            return

        if self.next_update_at is None:
            return  # Already running.

        cooling_period = self.BASE_COOLING_PERIOD * self.size**0.66
        if self.last_updated_at is None:
            # No idea how much type passed. For rocks, this is critical. Prepare for next time and leave.
            self.last_updated_at = game_date_time
            self.next_update_at = game_date_time + timedelta(seconds=cooling_period)
            update_queue.add(self)
            logger.info(f"Rock ready to be updated next time. Queue size: {len(update_queue._queue)}")
            return

        time_passed = game_date_time - self.last_updated_at
        periods_passed = time_passed.total_seconds() / self.BASE_COOLING_PERIOD

        self.temperature = self.COOLING_FACTOR**periods_passed * self.temperature
        if self.temperature < 0.1:
            self.temperature = 0
            self.next_update_at = None
            logger.info(f"Rock won't be updated anymore, too cold. Queue size: {len(update_queue._queue)}")
        else:
            self.next_update_at = game_date_time + timedelta(seconds=cooling_period)
            update_queue.add(self)

        self._adjust_color()
        self._set_last_updated(game_date_time)

        logger.debug(f"Temperature reduced: {self.temperature}. Queue size: {len(update_queue._queue)}")

    def stop_updating(self) -> None:
        if not self.get_alterations():
            return

        if self.next_update_at is None:
            return  # Already not updating.

        self.next_update_at = None
        update_queue.remove(self)
        logger.info(f"Rock won't be updated anymore, at ({self.longitude}, {self.latitude}). Queue size: {len(update_queue._queue)}")

    def start_updating(self, update_time: datetime) -> None:
        if not self.get_alterations():
            return
        if self.next_update_at is not None:
            return  # Already updating.
        self.next_update_at = update_time  # Immediately
        update_queue.add(self)
        logger.info(f"Rock will be updated again, at {self.temperature}°. Queue size: {len(update_queue._queue)}")

    def _calculate_initial_composition(self, my_random: Random) -> float:
        if my_random.random() < self.parent_km2.parent_world.ore_prevalence:
            result = Rock.ORE_RICH_THRESHOLD + my_random.random() * (1.0 - Rock.ORE_RICH_THRESHOLD)
        else:
            result = my_random.random()
        return result

    def is_ore_rich(self) -> bool:
        return self.composition > Rock.ORE_RICH_THRESHOLD

    def get_purity(self) -> float:
        '''Not a percentage of how much ore, but a percentile of the distribution.'''
        if not self.is_ore_rich():
            return 0.0
        return (self.composition - Rock.ORE_RICH_THRESHOLD) / (1.0 - Rock.ORE_RICH_THRESHOLD)

    def ore_per_m3(self) -> float:
        '''Ore (in Kg) per cubic meter of rock. 100% pure would be ~2,500,000,000 Kg. Normal is 2 Kg :D'''
        if not self.is_ore_rich():
            return 0.0
        return min(2500000000, 1/(1.0 - self.get_purity()))

    def _calculate_initial_color(self, my_random: Random) -> tuple:
        # Ore-rich are yellow-ish
        if self.is_ore_rich():
            base_r = 128 + int(64 * self.get_purity()) + my_random.randint(0, 8)
            base_g = 128 + int(64 * self.get_purity()) + my_random.randint(0, 8)
            base_b = 32 + my_random.randint(0, 8)
        else:
            base_r = 96 + my_random.randint(0, 32)
            base_g = 96 + my_random.randint(0, 32)
            base_b = 80 + my_random.randint(0, 32)

        return (base_r, base_g, base_b)

    def _adjust_color(self) -> Rock:
        temperature_increase = int(math.sqrt(self.temperature))
        self.color = tuple(min(value + temperature_increase, 255) for value in self.initial_color)
        return self

    def increase_temperature(self, delta_time: float) -> Rock:
        delta_temp = Rock.TEMP_RISE_RATE * delta_time / (self.size ** 3)  # Assuming size is in meters, and temperature rise is proportional to volume
        self.temperature += delta_temp

        if self.temperature >= Rock.TEMP_MAX:
            self.temperature = 0.0
            self.parent_km2.melt_rock(self)
            return

        self._adjust_color()
        if self.next_update_at is None:
            import game_environment as gem
            self.start_updating(gem.current_environment.date_time)  # First time we just get ready anyway.
        return self
