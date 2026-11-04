"""The report to the outpost's dockmaster (the Dockmaster button of the settlement screen, which shows its messages in
its own panel). The handling of the ship starts with the Ok: a pilot who walks away from the dockmaster without it
leaves the ship as it is. A stub: what is said is still to be written."""

from __future__ import annotations
from typing import Optional
import logging

from common.dialogs.messages import Message, ShowMessage, show_message
from galaxies.settlement import Settlement
from galaxies.people.player import Player
from ..person import Person
from ..conversation import Conversation

logger = logging.getLogger(__name__)

class OutpostReportFirst(Conversation):
    def __init__(self, player: Player, interlocutor: Person, outpost: Settlement, show: ShowMessage = show_message
                 ) -> None:
        super().__init__(player, interlocutor, show)
        self.outpost: Settlement = outpost
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

        self.show(Message(
                title=self.title,
                text=oit + it + handle_info,
                buttons=['Ok'],
                open_sound='radio_open'
                ), self._ok
            )

    def _generate_outpost_introduction_text(self) -> str:
         return (
             f"Welcome to {self.outpost.name}, {self.interlocutor.get_player_title()} {self.player.surname}."
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

    def _ok(self, chosen_button: Optional[int]) -> OutpostReportFirst:
        """The Ok of the message: the handling of the ship starts (repair and recharge), unless it takes no time at
        all, and the conversation is over. A message closed by a click away never gets here."""
        if self.outpost.get_time_to_handle(self.player.ship): # Skip by absurd amounts.
            self.outpost.start_handle(self.player.ship)
        self.close()
        return self
