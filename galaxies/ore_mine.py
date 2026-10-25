from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from datetime import datetime, timedelta

import logging
import random

from common.updating import Updatable, update_queue
from galaxies import seeds

if TYPE_CHECKING:
    from galaxies.ore_fields import OreField

logger = logging.getLogger(__name__)


class OreMine(Updatable):
    EXTRACTION_POWER: int = 0.5 # To tune the game. Maybe later different kinds of mines.
    EXTRACTION_PERIOD: int = 3600
    MAX_CAPACITY: int = 20000
    # Geometry of a mine: a vertical cylinder standing on the ground. Graphics draws it with these and
    # the scanner's beam hits it with these, so the two always agree.
    MINE_RADIUS: float = 4.0  # metres
    MINE_HEIGHT: float = 8.0  # metres
    MINE_MIN_DISTANCE = 10 * MINE_RADIUS  # between mines.

    def __init__(
            self,
            parent_field: OreField,
            longitude: int = 0,
            latitude: int = 0,
            orientation: float = 0.0,
            saved_attributes: Optional[dict] = None
            ) -> None:
        self.parent_field: OreField = parent_field
        if saved_attributes is None:
            self.longitude: float = longitude
            self.latitude: float = latitude
            self.orientation: float = orientation
            self.content: int = 0
            self.last_updated_at: Optional[datetime] = None
            self.next_update_at: Optional[datetime] = None
        else:
            self.longitude: float = saved_attributes['longitude']
            self.latitude: float = saved_attributes['latitude']
            self.orientation: float = saved_attributes['orientation']
            self.content: int = saved_attributes['content']
            self.last_updated_at: Optional[datetime] = \
                datetime.strptime(saved_attributes['last_updated_at'], '%Y-%m-%d %H:%M:%S.%f') \
                if 'last_updated_at' in saved_attributes else None
            self.next_update_at: Optional[datetime] = \
                datetime.strptime(saved_attributes['next_update_at'], '%Y-%m-%d %H:%M:%S.%f') \
                if 'next_update_at' in saved_attributes else None

        self.parent_field.parent_km2.parent_world.registered_mines.append((self.longitude, self.latitude))
        update_queue.add(self)

        logger.info(f"Ore Mine created at {self.longitude}, {self.latitude}. Content: {self.content}.")

    is_external: bool = False  # see ExternalMine

    def is_inactive(self, game_date_time: datetime) -> bool:
        """Whether the mine looks out of use (see ExternalMine). The player's mines never do."""
        return False

    def serialize(self) -> dict:
        result = {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'orientation': self.orientation,
            'content': self.content
            }
        if self.last_updated_at:
            result['last_updated_at'] = self.last_updated_at.strftime('%Y-%m-%d %H:%M:%S.%f')
        if self.next_update_at:
            result['next_update_at'] = self.next_update_at.strftime('%Y-%m-%d %H:%M:%S.%f')
        return result

    def get_next_update(self) -> datetime:
        import game_environment as gem
        if self.next_update_at is None:
            return gem.current_environment.date_time
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        # Called by the queue (which took this mine out first) or by Km2.start_updating (which only calls it when the
        # mine is not queued). Queued already means a second entry would be made: fail early.
        if self in update_queue:
            raise RuntimeError(f"Mine at {self.longitude}, {self.latitude} updated while queued: a second queue entry.")
        if self.last_updated_at is None:
            # This mine did not start working. Start now.
            self.last_updated_at = game_date_time
            self.next_update_at = game_date_time + timedelta(seconds=self.EXTRACTION_PERIOD)
            update_queue.add(self)
            logger.info(f"Mine at {self.longitude}, {self.latitude} starts to work.")
            return

        # Under one period: nothing is extracted, the time is saved for the next update.
        if self._extract_completed_periods(game_date_time) == 0:
            self.next_update_at = game_date_time + timedelta(seconds=self.EXTRACTION_PERIOD)
            update_queue.add(self)
            return

        if self.parent_field.remaining_ore <= 0:
            logger.info("Mine won't be updated anymore, field depleted.")
            self.next_update_at = None
            return

        self.next_update_at = game_date_time + timedelta(seconds=self.EXTRACTION_PERIOD)
        update_queue.add(self)

    def _extract_completed_periods(self, game_date_time: datetime) -> float:
        """Extracts the whole extraction periods since last_updated_at, and returns how many there were (0 if under
        one). The part of a period still running is left for later."""
        periods_passed = (game_date_time - self.last_updated_at).total_seconds() // OreMine.EXTRACTION_PERIOD
        if periods_passed < 1.0:
            return 0
        self.last_updated_at += timedelta(seconds=periods_passed * OreMine.EXTRACTION_PERIOD)
        self.content += self.parent_field.extract(
            self.EXTRACTION_POWER * periods_passed, OreMine.MAX_CAPACITY - self.content
            )
        return periods_passed

    def stop_updating(self) -> None:
        import game_environment as gem
        update_queue.remove(self)
        if self.last_updated_at is not None:
            self._extract_completed_periods(gem.current_environment.date_time)  # the periods finished before stopping
        self.next_update_at = None


class ExternalMine(OreMine):
    """A mine of other, unseen miners, alone in the centre of an external ore field (`OreField.external_from_rock`).

    Generated by the world, so it is no alteration: it is not saved, not registered in the world's mines and not in the
    update queue. It holds no ore, and the scanner says it is not ours. An ore-rich rock may become one from a date in
    the years after EPOCH (`conversion_date`), each rock with its own, and one that is more than INACTIVE_AFTER old is
    drawn with the texture of an unused mine; nothing else differs.
    """
    UNDISCOVERED_SHARE: float = 0.1  # of the ore-rich rocks, which never become external
    CONVERSION_WINDOW: float = 100 * 365.25 * 86400.0  # s after EPOCH in which all the others have become external
    FRONT_LOADING: float = 1.5  # above 1, more conversions early in the window; 1 spreads them evenly
    INACTIVE_AFTER: float = 10 * 365.25 * 86400.0  # s

    is_external = True

    def __init__(self, parent_field: OreField, converted_at: datetime) -> None:
        # No super().__init__: it registers the mine and queues it.
        self.parent_field: OreField = parent_field
        self.longitude: float = parent_field.longitude
        self.latitude: float = parent_field.latitude
        self.orientation: float = parent_field.orientation
        self.content: int = 0
        self.converted_at: datetime = converted_at

    @staticmethod
    def conversion_date(km2_seed: int, longitude: int, latitude: int) -> Optional[datetime]:
        """When the ore-rich rock at this place becomes external, or None if it never does. Fixed by the seed, so a Km2
        made again looks the same on the same date, and the external ones only grow with time."""
        import game_environment as gem
        my_random = random.Random(seeds.derive(km2_seed, 'external', longitude, latitude))
        if my_random.random() < ExternalMine.UNDISCOVERED_SHARE:
            return None
        seconds = ExternalMine.CONVERSION_WINDOW * my_random.random() ** ExternalMine.FRONT_LOADING
        return gem.GameEnvironment.EPOCH + timedelta(seconds=seconds)

    def is_inactive(self, game_date_time: datetime) -> bool:
        return (game_date_time - self.converted_at).total_seconds() > ExternalMine.INACTIVE_AFTER

