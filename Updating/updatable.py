"""Interface for objects that need periodic updates."""

from abc import ABC, abstractmethod
from datetime import datetime


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
