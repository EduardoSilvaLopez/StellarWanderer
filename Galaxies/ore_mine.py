from typing import Optional

from datetime import datetime, timedelta

import logging
logger = logging.getLogger(__name__)

from Updating.Updatable import Updatable
from Updating.UpdateQueue import update_queue

from Galaxies import ore_fields

class OreMine(Updatable):
    EXTRACTION_PERIOD: int = 3600

    def __init__(
            self,
            parent_field: ore_fields,
            longitude: int = 0,
            latitude: int = 0,
            orientation: float = 0.0,
            saved_attributes: dict = None
            ):
        self.parent_field: ore_fields = parent_field
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

        logger.info(f"Ore Mine created at {self.longitude}, {self.latitude}. Content: {self.content}.")

        update_queue.add(self)

    def serialize(self) -> dict:
        result = {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'orientation': self.orientation,
            'content': self.content
            }
        if self.last_updated_at:
            result['last_updated_at'] = str(self.last_updated_at)
        if self.next_update_at:
            result['next_update_at'] = str(self.next_update_at)
        return result

    def get_next_update(self) -> datetime:
        from GameEnvironment import current_environment
        if self.next_update_at is None:
            return current_environment.date_time
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        if not game_date_time: # stop updating
            return
        
        if self.last_updated_at is None:
            # This mine did not start working. Start now.
            self.last_updated_at = game_date_time
            self.next_update_at = game_date_time + timedelta(seconds= self.EXTRACTION_PERIOD)
            update_queue.add(self)
            logger.info(f"Mine at {self.longitude}, {self.latitude} starts to work.")
            return

        time_passed = game_date_time - self.last_updated_at
        periods_passed = time_passed.total_seconds() // OreMine.EXTRACTION_PERIOD
        # May be under 1, save the rest for the next.
        self.last_updated_at += timedelta(seconds = periods_passed * OreMine.EXTRACTION_PERIOD)
        
        ore_extracted = self.parent_field.extract(periods_passed)
        self.content += ore_extracted
        if self.parent_field.remaining_ore <= 0:
            logger.info(f"Mine won't be updated anymore, field depleted.")
            self.next_update_at = None
            return

        self.next_update_at = game_date_time + timedelta(seconds = self.EXTRACTION_PERIOD)
        update_queue.add(self)

        logger.debug(f"Mine at {self.longitude}, {self.latitude} updated, {ore_extracted} ore extracted.")
