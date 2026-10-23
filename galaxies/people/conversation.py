from __future__ import annotations
from typing import List
from abc import ABC, abstractmethod
from datetime import datetime

import logging
from common.dialogs.messages import ShowMessage, show_message

from galaxies.people.player import Player
import game_environment as gem
from galaxies.people.person import Person

logger = logging.getLogger(__name__)


class Conversation(ABC):
    """A conversation shows its messages through `show`: show_message, a dialog over the cockpit, unless the one who
    starts it gives another place, such as the panel of the outpost screen. A subclass sets its own `title`, the
    heading of its messages."""

    def __init__(self, player: Player, interlocutor: Person, show: ShowMessage = show_message) -> None:
        self.player: Player = player
        self.interlocutor: Person = interlocutor.meet()
        self.date_time: datetime = gem.current_environment.date_time
        self.interaction_lines: List[str] = []
        self.show: ShowMessage = show
        self.is_closed: bool = False

    @abstractmethod
    def start(self) -> None:
        """Shows the first message of the conversation."""

    def generate_introduction_text(self) -> str:
         if self.interlocutor.last_communication_at is None:
            return (
                f"I am {self.interlocutor.name}, {self.interlocutor.role.name}.\n\n"\
                    if self.interlocutor.sociability100 > 20 else f"Name's {self.interlocutor.name}.\n\n"
            )
         return ''

    def close(self) -> None:
        """Ends the conversation: the interlocutor remembers it, with its interaction_lines. Closing it again does
        nothing, so whoever shows it can close it too when it is left half way."""
        if self.is_closed:
            return
        self.is_closed = True
        self.interlocutor.last_communication_at = self.date_time
        self.interlocutor.interactions[self.date_time.replace(microsecond=0)] = self.interaction_lines
        self.interlocutor.record()
        self.interlocutor.log_description()
        logger.debug("Finished.")
