"""A notification for the pilot: a message, and optionally a time when it should be updated."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from common.updating import Updatable, update_queue

import game_environment as gem


class Notification(Updatable):
    """Holds a message. Not scheduled by default: it is only updated if its owner puts it in UpdateQueue."""

    def __init__(self) -> None:
        self.message: str = ''
        self.next_update_at: Optional[datetime] = None

    def set(self, message: str) -> Notification:
        if not message:
            return

        self.message = message
        self.next_update_at = gem.current_environment.date_time + timedelta(seconds=60)

        from galaxies.people.player import current_player
        current_player.time_scale = current_player.TIME_SCALE_MIN

        if self not in update_queue:
            update_queue.add(self)
        return self

    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        self.message = ''
        self.next_update_at = None
        return
