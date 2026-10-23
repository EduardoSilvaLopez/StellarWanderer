"""The player goes back to the dockmaster."""

from __future__ import annotations
from typing import Optional
import logging

from common.dialogs.messages import Message, ShowMessage, show_message
from galaxies.outpost import Outpost
from galaxies.people.player import Player
from ..person import Person
from ..conversation import Conversation

logger = logging.getLogger(__name__)

class OutpostReportFurther(Conversation):
    def __init__(self, player: Player, interlocutor: Person, outpost: Outpost, show: ShowMessage = show_message
                 ) -> None:
        super().__init__(player, interlocutor, show)
        self.outpost: Outpost = outpost
        self.title: str = "Reporting Back"

    def start(self) -> None:
        self.outpost.update_handle(self.player.ship, self.date_time)  # handling going on: the levels as they are now
        time_to_handle: float = self.outpost.get_time_to_handle(self.player.ship)

        handle_info_or_question: str = "Your ship is ready."
        do_ask: bool = False
        time_str: str = self._time_as_string(int(time_to_handle))
        if time_to_handle > 0:
            handle_info_or_question = f"Your ship will be ready in {time_str}."
        elif self.player.ship.cargo_hold.ore > 0:
            handle_info_or_question = f"Shall we start unloading the ore? It should be ready in {time_str}."
            do_ask = True

        text: str = handle_info_or_question

        # Prepare the buttons:
        buttons = ['<Accept>', '<Reject>'] if do_ask else ['Ok.']

        self.show(Message(
                title=self.title,
                text=text,
                buttons=buttons,
                open_sound='radio_open'
                ), self._unload_the_ore_answered if do_ask else self._finish
            )

    @staticmethod
    def _time_as_string(time_in_secs: int) -> str:
        if time_in_secs < 2*60:
            return "very soon"
        if time_in_secs < 2*60*60:
            return str(1 + (time_in_secs // 60)) + " minutes"
        return str(1 + (time_in_secs // (60 * 60))) + " hours"

    def _unload_the_ore_answered(self, chosen_button: Optional[int]) -> OutpostReportFurther:
        if chosen_button == 0:
            self.outpost.handling_includes_ore = True
            self.outpost.start_handle(self.player.ship)
        self._finish(chosen_button)
        return self

    def _finish(self, chosen_button: int) -> OutpostReportFurther:
        self.interlocutor.last_communication_at = self.date_time
        self.close()
        return self
