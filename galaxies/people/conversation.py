from __future__ import annotations
from typing import List, Optional
from abc import ABC, abstractmethod
from datetime import datetime

import logging
from common.dialogs.messages import Message

import game_environment as gem
from galaxies.people.person import Person
from galaxies.outpost import Outpost

logger = logging.getLogger(__name__)


class Conversation(ABC):
    def __init__(self, interlocutor: Person) -> None:
        self.interlocutor: Person = interlocutor.meet()
        self.date_time: datetime = gem.current_environment.date_time
        self.interaction_lines: List[str] = []

    @staticmethod
    def generate(interlocutor: Person) -> Optional[Conversation]:
        """Starts the conversation that fits the interlocutor's residency, and returns it (None if there is none
        yet)."""
        if isinstance(interlocutor.residency, Outpost):
            from .conversations.reporting_in_outpost import ReportingInOutpost
            conversation = ReportingInOutpost(interlocutor, interlocutor.residency)
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

    def close(self) -> None:
        """Ends the conversation: the interlocutor remembers it, with its interaction_lines."""
        self.interlocutor.last_communication_at = self.date_time
        self.interlocutor.interactions[self.date_time.replace(microsecond=0)] = self.interaction_lines
        self.interlocutor.record()
        self.interlocutor.log_description()
        logger.debug("Finished.")
