from typing import List
from abc import abstractmethod
from datetime import datetime

import logging
from Dialogs.messages import Message

import game_environment as gem
from Galaxies.People.person import Person
from Galaxies.outpost import Outpost

logger = logging.getLogger(__name__)

class Conversation:
    @abstractmethod
    def generate(interlocutor: Person) -> Conversation:
        if isinstance(interlocutor.residency, Outpost):
            from .Conversations.reporting_in_outpost import ReportingInOutpost
            return ReportingInOutpost(interlocutor, interlocutor.residency).start()

    def __init__(self, interlocutor: Person):
        self.interlocutor: Person = interlocutor
        self.date_time: datetime = gem.current_environment.date_time
        self.interaction_lines: List[str] = []

    def prepare_message(self, title: str, text: str, button_dicts: List[dict]) -> Message:
        '''Gets a dict of dicts with "text" for every button and the related effects.'''
        result: Message = None
        if len(button_dicts) == 1:
            result = Message(
                title=title,
                text=text,
                buttons=[ button_dicts[0]['text'] ]
            )
        elif len(button_dicts) == 2:
            result = Message(
                title=title,
                text=text,
                buttons=[ button_dicts[0]['text'], button_dicts[1]['text'] ]
            )
        else:
            result = Message(
                title=title,
                text=text,
                buttons=[ button_dicts[0]['text'], button_dicts[1]['text'], button_dicts[2]['text'] ]
            )
        return result
    
    def close(self, interaction_lines: List[str]):
        self.interlocutor.log_update()
        self.interlocutor.interactions[self.date_time] = interaction_lines
        logger.debug("Finished.")