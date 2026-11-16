"""The player goes back to the dockmaster."""

from __future__ import annotations
from typing import Optional
import logging

from common.dialogs.messages import Message, ShowMessage, show_message
from galaxies.settlement import Settlement
from galaxies.people.player import Player
from ..person import Person
from ..conversation import Conversation

logger = logging.getLogger(__name__)

class OutpostReportFurther(Conversation):
    def __init__(self, player: Player, interlocutor: Person, outpost: Settlement, show: ShowMessage = show_message
                 ) -> None:
        super().__init__(player, interlocutor, show)
        self.outpost: Settlement = outpost
        self.title: str = "Reporting Back"

    def start(self) -> None:
        self.outpost.update_handle(self.player.ship, self.date_time)  # handling going on: the levels as they are now
        time_to_handle: float = self.outpost.get_time_to_handle(self.player.ship)

        text: str = "Your ship is ready."
        time_str: str = self._time_as_string(int(time_to_handle))
        ready: bool = self.outpost.is_ready(self.player.ship)  # nothing to offer, even if a few seconds are left
        starts: bool = False
        if time_to_handle > 0 and not ready:
            if self.outpost.handling_due_at is None:  # never started (the Ok of the first report was not given)
                text = f"We will start reparing and recharging up your ship. It should be ready {time_str}."
                starts = True
            else:
                text = f"Your ship will be ready {time_str}."

        self.show(Message(
                title=self.title,
                text=text,
                buttons=['Ok.'],
                open_sound='radio_open'
                ), self._start_and_finish if starts else self._finish
            )

    @staticmethod
    def _time_as_string(time_in_secs: int) -> str:
        if time_in_secs < 2*60:
            return "very soon"
        if time_in_secs < 2*60*60:
            return "in " + str(1 + (time_in_secs // 60)) + " minutes"
        return "in " + str(1 + (time_in_secs // (60 * 60))) + " hours"

    def _start_and_finish(self, chosen_button: int) -> OutpostReportFurther:
        """The Ok of the offer to start the handling: it starts, as it does with the first report's."""
        self.outpost.start_handle(self.player.ship)
        return self._finish(chosen_button)

    def _finish(self, chosen_button: int) -> OutpostReportFurther:
        self.interlocutor.last_communication_at = self.date_time
        self.close()
        return self
