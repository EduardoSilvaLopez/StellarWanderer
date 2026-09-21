"""Singleton queue for managing periodic updates of Updatable objects."""

from datetime import datetime
from typing import List
from .Updatable import Updatable


class _UpdateQueue:
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
update_queue = _UpdateQueue()
