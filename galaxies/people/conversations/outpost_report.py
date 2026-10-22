"""The report to the outpost's dockmaster (the Report button of the outpost screen, which shows its messages in its own
panel). A stub: what is said is still to be written."""

from __future__ import annotations
from typing import List, Optional

from common.dialogs.messages import ShowMessage, show_message
from galaxies.outpost import Outpost
from ..person import Person
from ..conversation import Conversation


class OutpostReport(Conversation):
    def __init__(self, interlocutor: Person, outpost: Outpost, show: ShowMessage = show_message) -> None:
        super().__init__(interlocutor, show)
        self.outpost: Outpost = outpost
        self.title: str = "Reporting"
        self.time_since_last_visit: Optional[float] = None if not self.outpost.last_visited\
            else (self.date_time - self.outpost.last_visited).total_seconds()

    def start(self) -> None:
        if True: #self.time_since_last_visit is None:
            oit: str = self.generate_outpost_introduction_text()

        text: str = oit

        # Prepare the buttons:
        buttons = [
                {
                'text': 'Yes',
                }
                , {
                'text': 'No',
                }
            ]

        self._ask(text, buttons, self._finish)

    def generate_outpost_introduction_text(self) -> str:
         return "This is an outpost"

    def _finish(self, chosen_button: Optional[int], consequences: List[dict]) -> OutpostReport:
        self.close()
        return self
