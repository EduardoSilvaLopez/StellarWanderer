from abc import abstractmethod

import logging
from typing import List

from Dialogs.messages import Message
from Galaxies.People.person import Person
from Galaxies.outpost import Outpost

logger = logging.getLogger(__name__)

class Conversation:
    @abstractmethod
    def generate(interlocutor: Person) -> Conversation:
        if isinstance(interlocutor.residency, Outpost):
            from .Conversations.reporting_in_outpost import ReportingInOutpost
            return ReportingInOutpost(interlocutor, interlocutor.residency).start()

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
                buttons=[ button_dicts[0]['text'], button_dicts[1][0], button_dicts[2]['text'] ]
            )
        return result
    
    @abstractmethod
    def finish(self):
        logger.debug("Finished.")