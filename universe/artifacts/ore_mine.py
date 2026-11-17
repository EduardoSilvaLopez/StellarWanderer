from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from datetime import datetime, timedelta

import logging
import random
from functools import cached_property

from common.updating import Updatable, update_queue
from universe.structure import seeds

if TYPE_CHECKING:
    from universe.artifacts.ore_fields import OreField

logger = logging.getLogger(__name__)


class OreMine(Updatable):
    MAX_EXTRACTION_PER_SECOND: float = 1 / 60  # One Kg per minute absolute maximum, later depends on mine.
    EXTRACTION_POWER: float = 0.4 # To tune the game. Maybe later different kinds of mines.
    EXTRACTION_PERIOD: int = 3600
    MAX_CAPACITY: int = 20000
    # Geometry of a mine: a vertical cylinder standing on the ground. Graphics draws it with these and
    # the scanner's beam hits it with these, so the two always agree.
    MINE_RADIUS: float = 4.0  # metres
    MINE_HEIGHT: float = 8.0  # metres
    MINE_MIN_DISTANCE = 10 * MINE_RADIUS  # between mines.
    # While the mine codes of the system are sold and not denounced (see _sells_for_credits), this share of each
    # extraction becomes credits instead of ore, at CREDITS_PER_ORE per kg. Tunable.
    CREDITS_SHARE: float = 0.75
    CREDITS_PER_ORE: int = 100
    # The scraps the ship takes from a mine that is empty and whose field is depleted, when it is scrapped.
    SCRAPS_FROM_MINE: int = 100
    INACTIVE_AFTER: float = 10 * 365.25 * 86400.0  # s of being unused (see ExternalMine) after which a mine looks old
    TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

    def __init__(
            self,
            parent_field: OreField,
            longitude: float = 0.0,
            latitude: float = 0.0,
            orientation: float = 0.0,
            saved_attributes: Optional[dict] = None
            ) -> None:
        self.parent_field: OreField = parent_field
        if saved_attributes is None:
            self.longitude: float = longitude
            self.latitude: float = latitude
            self.orientation: float = orientation
            self.content: float = 0.0  # Kg: the one place ore is fractional, it accumulates until the ship takes whole Kg
            self.credits: int = 0
            self.last_updated_at: Optional[datetime] = None
            self.next_update_at: Optional[datetime] = None
            self.given_away_at: Optional[datetime] = None
        else:
            self.longitude: float = saved_attributes['longitude']
            self.latitude: float = saved_attributes['latitude']
            self.orientation: float = saved_attributes['orientation']
            self.content: float = saved_attributes['content']
            self.credits: int = saved_attributes.get('credits', 0)  # saved only when not 0
            self.last_updated_at: Optional[datetime] = \
                datetime.strptime(saved_attributes['last_updated_at'], '%Y-%m-%d %H:%M:%S.%f') \
                if 'last_updated_at' in saved_attributes else None
            self.next_update_at: Optional[datetime] = \
                datetime.strptime(saved_attributes['next_update_at'], '%Y-%m-%d %H:%M:%S.%f') \
                if 'next_update_at' in saved_attributes else None
            self.given_away_at: Optional[datetime] = \
                datetime.strptime(saved_attributes['given_away_at'], self.TIME_FORMAT) \
                if 'given_away_at' in saved_attributes else None

        registered = self.parent_field.parent_km2.parent_world.registered_mines
        if self.given_away_at is None and (self.longitude, self.latitude) not in registered:
            registered.append((self.longitude, self.latitude))  # (a loaded world lists its mines already)
        if self.given_away_at is None:
            update_queue.add(self)

        logger.info(f"Ore Mine created at {self.longitude}, {self.latitude}. Content: {self.content}.")

    @property
    def is_external(self) -> bool:
        """Whether the mine is not the pilot's (see ExternalMine): one the pilot has given away (see give_away)."""
        return self.given_away_at is not None

    @cached_property
    def ground_height(self) -> float:
        """The height of the ground the mine stands on, in metres above the datum (the ground does not change)."""
        return self.parent_field.parent_km2.parent_world.ground_height(self.longitude, self.latitude)

    def is_inactive(self, game_date_time: datetime) -> bool:
        """Whether the mine looks out of use (see ExternalMine): the pilot's mines never do, but one the pilot has given
        away does as time passes."""
        return self.given_away_at is not None and (game_date_time - self.given_away_at).total_seconds() \
            > self.INACTIVE_AFTER

    def give_away(self, game_date_time: datetime) -> None:
        """The pilot gives the control of the mine away: from now it is not theirs. It stays in its field, still an
        alteration, but it works no more, holds no ore or credits and is no more registered in its world (the map).
        The same changes as `give_away_serialized`, which RockyWorld.give_away_mines completes."""
        update_queue.remove(self)
        self.content = 0.0
        self.credits = 0
        self.next_update_at = None
        self.given_away_at = game_date_time
        registered = self.parent_field.parent_km2.parent_world.registered_mines  # the world's map shows only the own
        registered[:] = [position for position in registered if position != (self.longitude, self.latitude)]

    @staticmethod
    def give_away_serialized(mine: dict, game_date_time: datetime) -> None:
        """What `give_away` does to a mine that is not in memory yet, in its saved form (`serialize`), so the save is
        the same as if its Km2 had been loaded first."""
        mine['content'] = 0.0
        mine.pop('credits', None)
        mine.pop('next_update_at', None)
        mine['given_away_at'] = game_date_time.strftime(OreMine.TIME_FORMAT)

    def serialize(self) -> dict:
        result = {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'orientation': self.orientation,
            'content': self.content
            }
        if self.credits:
            result['credits'] = self.credits
        if self.last_updated_at:
            result['last_updated_at'] = self.last_updated_at.strftime('%Y-%m-%d %H:%M:%S.%f')
        if self.next_update_at:
            result['next_update_at'] = self.next_update_at.strftime('%Y-%m-%d %H:%M:%S.%f')
        if self.given_away_at:
            result['given_away_at'] = self.given_away_at.strftime(self.TIME_FORMAT)
        return result

    def get_next_update(self) -> datetime:
        import game_environment as gem
        if self.next_update_at is None:
            return gem.current_environment.date_time
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        # Called by the queue (which took this mine out first) or by Km2.start_updating (which only calls it when the
        # mine is not queued). Queued already means a second entry would be made: fail early.
        if self.given_away_at is not None:
            return  # not ours anymore: it works no more
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
        one). The part of a period still running is left for later. What is extracted is ore, except that with the
        mine codes sold (see _sells_for_credits) CREDITS_SHARE of it becomes credits: the field loses the same, and no
        credits come when nothing is extracted."""
        if self.last_updated_at is None:
            raise Exception("Somehow this mine was never updated, which is not possible at this point.")

        time_passed = (game_date_time - self.last_updated_at).total_seconds()
        periods_passed = time_passed // OreMine.EXTRACTION_PERIOD
        if periods_passed < 1.0:
            return 0
        self.last_updated_at += timedelta(seconds=periods_passed * OreMine.EXTRACTION_PERIOD)
        extracted = self.parent_field.extract(
            self.EXTRACTION_POWER * periods_passed,
            min(OreMine.MAX_CAPACITY - self.content, time_passed * OreMine.MAX_EXTRACTION_PER_SECOND)
            )
        if self._sells_for_credits():
            self.credits += int(extracted * self.CREDITS_SHARE * self.CREDITS_PER_ORE)
            extracted *= 1 - self.CREDITS_SHARE
        self.content += extracted
        return periods_passed

    def _sells_for_credits(self) -> bool:
        """Whether this mine sells its extraction for credits: the pilot has sold the mine codes of this mine's system
        and has not denounced the smugglers since (the flags `sold mine codes <system seed>` and `ratted ore smugglers
        <system seed>` of the Those-Who-Share standing, see settlement_chat)."""
        import universe.society.people.player as gpp  # local: the player loads the world, which loads this module
        from universe.society.politics import political_entity
        system = self.parent_field.parent_km2.parent_world.stellar_system
        flags = gpp.current_player.political_status[political_entity.THOSE_WHO_SHARE].flags
        return f"sold mine codes {system.seed}" in flags and f"ratted ore smugglers {system.seed}" not in flags

    def stop_updating(self) -> None:
        if self.given_away_at is not None:
            return
        import game_environment as gem
        update_queue.remove(self)
        if self.last_updated_at is not None:
            self._extract_completed_periods(gem.current_environment.date_time)  # the periods finished before stopping
        self.next_update_at = None

    def scrap(self) -> None:
        """The mine is taken down: it stops working, and leaves its field and its world."""
        self.stop_updating()
        self.parent_field.mines.remove(self)
        registered = self.parent_field.parent_km2.parent_world.registered_mines
        registered[:] = [position for position in registered if position != (self.longitude, self.latitude)]


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

    @property
    def is_external(self) -> bool:
        return True

    def __init__(self, parent_field: OreField, converted_at: datetime) -> None:
        # No super().__init__: it registers the mine and queues it.
        self.parent_field: OreField = parent_field
        self.longitude: float = parent_field.longitude
        self.latitude: float = parent_field.latitude
        self.orientation: float = parent_field.orientation
        self.content: float = 0.0
        self.credits: int = 0
        self.given_away_at: Optional[datetime] = None
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
        return (game_date_time - self.converted_at).total_seconds() > self.INACTIVE_AFTER

