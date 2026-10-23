from __future__ import annotations
from typing import Callable, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime

import logging
from common.dialogs.messages import Message, ShowMessage, show_message

from galaxies.people.player import Player
import game_environment as gem
from galaxies.people.person import Person
from galaxies.outpost import Outpost

logger = logging.getLogger(__name__)


class Conversation(ABC):
    """A conversation shows its messages through `show`: show_message, a dialog over the cockpit, unless the one who
    starts it gives another place, such as the panel of the outpost screen."""

    def __init__(self, player: Player, interlocutor: Person, show: ShowMessage = show_message) -> None:
        self.player: Player = player
        self.interlocutor: Person = interlocutor.meet()
        self.date_time: datetime = gem.current_environment.date_time
        self.interaction_lines: List[str] = []
        self.title: str = ''  # the heading of its messages; a conversation sets its own
        self.show: ShowMessage = show
        self.is_closed: bool = False

    @staticmethod
    def generate(player: Player, interlocutor: Person) -> Optional[Conversation]:
        """Starts the conversation that fits the interlocutor's residency, and returns it (None if there is none
        yet)."""
        if isinstance(interlocutor.residency, Outpost):
            from .conversations.reporting_in_outpost import ReportingInOutpost
            conversation = ReportingInOutpost(player, interlocutor, interlocutor.residency)
            conversation.start()
            return conversation
        return None

    @abstractmethod
    def start(self) -> None:
        """Shows the first message of the conversation."""

    def prepare_message(self, title: str, text: str, button_dicts: List[dict]) -> Message:
        '''A message over the radio, with one button for each dict of `button_dicts` (its "text"; the rest are the
        button's effects).'''
        return Message(
            title=title,
            text=text,
            buttons=[button['text'] for button in button_dicts],
            open_sound='radio_open'
        )

    def _ask(self, text: str, buttons: List[dict], then: Callable[[Optional[int], List[dict]], object]) -> None:
        """Shows `text` with `buttons`, under the conversation's title, where `show` puts it; the answer goes to
        `then`, with the buttons."""
        self.show(self.prepare_message(self.title, text, buttons), lambda button_index: then(button_index, buttons))

    def generate_introduction_text(self) -> str:
         if self.interlocutor.last_communication_at is None:
            return (
                f"I am {self.interlocutor.name}, {self.interlocutor.role.name}."\
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
