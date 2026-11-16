'''The game's date, kept in one place. Everything that lets game time pass moves this clock (the frames of the cockpit,
the work and the chat of the pilot in a settlement, the time of a forced return), and everything that shows or uses
the date reads it from here. Nothing keeps a copy of the date: a copy would not move with the clock.'''

from __future__ import annotations
import datetime

from galaxies.constants import EPOCH

# datetime tops out at year 9999
MAX_SECONDS = (datetime.datetime.max.replace(microsecond=0) - EPOCH).total_seconds()


class GameClock:
    """The date as seconds since EPOCH: a float, so that many small advances add up without rounding each one."""

    def __init__(self, date_time: datetime.datetime) -> None:
        self.seconds: float = (date_time - EPOCH).total_seconds()

    @property
    def now(self) -> datetime.datetime:
        return EPOCH + datetime.timedelta(seconds=self.seconds)

    def advance(self, seconds: float) -> None:
        """Game time passes by `seconds`. The date stops at the last one a datetime can hold."""
        self.seconds = min(self.seconds + seconds, MAX_SECONDS)
