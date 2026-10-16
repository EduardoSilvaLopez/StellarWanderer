"""Time-based updates: the Updatable interface and the singleton queue that calls them when they are due."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List


class Updatable(ABC):
    """Abstract base class for objects that support time-based updates.

    Classes implementing this interface will be managed by UpdateQueue,
    which calls update() when get_next_update() has passed.
    """

    @abstractmethod
    def get_next_update(self) -> datetime:
        """Return the datetime when this object should next be updated.

        Returns:
            datetime: The next scheduled update time.
        """
        pass

    @abstractmethod
    def update(self, game_date_time: datetime) -> None:
        """Perform the update operation.

        This method is called by UpdateQueue when the current time has
        passed the time returned by get_next_update().
        """
        pass


class UpdateQueue:
    """Internal UpdateQueue class. Use the module-level `update_queue` instance."""

    def __init__(self):
        """Initialize the update queue."""
        self._queue: List[Updatable] = []

    def add(self, updatable: Updatable) -> None:
        """Add an Updatable object to the queue.

        Args:
            updatable: An object implementing the Updatable interface.
        """
        self._queue.append(updatable)

    def remove(self, updatable: Updatable) -> None:
        """Remove an Updatable object from the queue.

        Args:
            updatable: The object to remove.
        """
        if updatable in self._queue:
            self._queue.remove(updatable)

    def clear(self) -> None:
        """Empty the queue. Used by reset of the game for some reason."""
        self._queue.clear()

    def __contains__(self, updatable: object) -> bool:
        return updatable in self._queue

    def update(self, current_date_time: datetime) -> None:
        """Update all objects whose next update time has passed.

        Iterates through the queue, calls update() on any Updatable
        whose get_next_update() returns a time <= current_date_time,
        then removes them from the queue.

        Args:
            current_date_time: The current datetime to check against.
        """
        # Create a list of objects to update (iterate over a copy to avoid
        # modifying the list while iterating)
        to_update = [obj for obj in self._queue if obj.get_next_update() <= current_date_time]

        # Update each object and remove it from the queue
        for obj in to_update:
            self.remove(obj)
            obj.update(current_date_time) # May re-insert.

    def __len__(self) -> int:
        """Return the number of objects currently in the queue."""
        return len(self._queue)

# Singleton instance: use this anywhere in the application
update_queue = UpdateQueue()
