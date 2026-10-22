"""The report to the outpost's com officer (the Report button of the outpost screen). A stub: what is said is still to be
written."""

from __future__ import annotations
from typing import Callable, List, Optional

from common.dialogs.messages import show_message
from galaxies.outpost import Outpost
from ..person import Person
from ..conversation import Conversation


class OutpostReport(Conversation):
    def __init__(self, interlocutor: Person, outpost: Outpost) -> None:
        super().__init__(interlocutor)
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

        self._ask(text, buttons, self.close)

    def generate_outpost_introduction_text(self) -> str:
         return "This is an outpost"

    def _ask(self, text: str, buttons: List[dict], then: Callable[[Optional[int], List[dict]], object]) -> None:
        """Shows `text` with `buttons`; the answer goes to `then`, with the buttons."""
        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: then(button_index, buttons)
            )
