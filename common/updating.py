"""Time-based updates: the Updatable interface and the singleton queue that calls them when they are due."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List


class Updatable(ABC):
    """An object that UpdateQueue updates once get_next_update() has passed."""

    @abstractmethod
    def get_next_update(self) -> datetime:
        """When this object is next due."""

    @abstractmethod
    def update(self, game_date_time: datetime) -> None:
        """Called by UpdateQueue once the date has passed get_next_update(), after taking the object out of the queue
        (it may put itself back)."""


class UpdateQueue:
    """The queue of Updatables. Use the module-level `update_queue` instance."""

    def __init__(self) -> None:
        self._queue: List[Updatable] = []

    def add(self, updatable: Updatable) -> None:
        self._queue.append(updatable)

    def remove(self, updatable: Updatable) -> None:
        """Takes `updatable` out of the queue, if it is there."""
        if updatable in self._queue:
            self._queue.remove(updatable)

    def clear(self) -> None:
        """Empties the queue: a new game or a load fills it again."""
        self._queue.clear()

    def __contains__(self, updatable: object) -> bool:
        return updatable in self._queue

    def __len__(self) -> int:
        return len(self._queue)

    def update(self, current_date_time: datetime) -> None:
        """Updates every object whose next update is at or before `current_date_time`, taking each out of the queue
        first."""
        to_update = [obj for obj in self._queue if obj.get_next_update() <= current_date_time]
        for obj in to_update:
            self.remove(obj)
            obj.update(current_date_time)  # May re-insert.


update_queue = UpdateQueue()  # the singleton: use it anywhere in the application
