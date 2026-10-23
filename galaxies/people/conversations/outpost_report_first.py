"""The report to the outpost's dockmaster (the Dockmaster button of the outpost screen, which shows its messages in its
own panel). A stub: what is said is still to be written."""

from __future__ import annotations
from typing import Optional
import logging

from common.dialogs.messages import Message, ShowMessage, show_message
from galaxies.outpost import Outpost
from galaxies.people.player import Player
from ..person import Person
from ..conversation import Conversation

logger = logging.getLogger(__name__)

class OutpostReportFirst(Conversation):
    def __init__(self, player: Player, interlocutor: Person, outpost: Outpost, show: ShowMessage = show_message
                 ) -> None:
        super().__init__(player, interlocutor, show)
        self.outpost: Outpost = outpost
        self.title: str = "Reporting"
        self.time_since_last_visit: Optional[float] = None if not self.outpost.last_visited\
            else (self.date_time - self.outpost.last_visited).total_seconds()
        self.introduction_to_outpost_given = self.time_since_last_visit is not None

    def start(self) -> None:
        oit: str = '' if self.introduction_to_outpost_given else self._generate_outpost_introduction_text()
        self.introduction_to_outpost_given = True

        it: str = self.generate_introduction_text()

        time_to_handle: float = self.outpost.get_time_to_handle(self.player.ship)

        time_str: str = self._time_as_string(int(time_to_handle))
        handle_info: str = f"We will start reparing and recharging up your ship. It should be ready {time_str}."

        do_ask: bool = self.player.ship.cargo_hold.ore > 0
        ore_question: str = f"\n\nShall we start unloading the ore, {self.player.get_title()}?" \
            if do_ask else ''

        text: str = oit + it + handle_info + ore_question

        # Prepare the buttons:
        buttons = ['Yes', 'Not yet, please'] if do_ask else ['Ok']

        self.show(Message(
                title=self.title,
                text=text,
                buttons=buttons,
                open_sound='radio_open'
                ), self._finish
            )

    def _generate_outpost_introduction_text(self) -> str:
         return (
             f"Welcome to {self.outpost.name}, {self.player.get_title()} {self.player.surname}."
            " We are new but we can take care about you.\n\n" if self.interlocutor.sociability100 > 20 else '\n\n'
            "We take care of your ship, you handle the cargo. Maintenance and recharge need some time, though.\n\n"
         )

    @staticmethod
    def _time_as_string(time_in_secs: int) -> str:
        if time_in_secs < 2*60:
            return "very soon"
        if time_in_secs < 2*60*60:
            return "in " + str(1 + (time_in_secs // 60)) + " minutes"
        return "in " + str(1 + (time_in_secs // (60 * 60))) + " hours"

    def _finish(self, chosen_button: Optional[int]) -> OutpostReportFirst:
        if chosen_button == 0:
            self.outpost.handling_includes_ore = True

        if self.outpost.get_time_to_handle(self.player.ship): # Skip by absurd amounts.
            self.outpost.start_handle(self.player.ship)

        self.interlocutor.last_communication_at = self.date_time
        self.close()
        return self
