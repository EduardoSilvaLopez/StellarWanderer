"""The mission board of an outpost, opened with Numpad 5 while the scanner has the outpost, and only for a pilot whose
reputation is MIN_REPUTATION or more.

Opening it counts as a visit to the outpost (`Outpost.last_visited`), not as speaking with the com officer
(`Person.last_communication_at`): the ship is not restocked or repaired here, that takes talking to the com officer.

The offers are made when the board opens (`Outpost.generate_missions`) and kept only while it stays open: leave, and
somebody else takes them. It is a chain of messages (show_message), as it runs inside the frame: the board lists the
pilot's open missions from this outpost (a button each, to deliver) and the offers (a button each, for the detail, where
they can be taken), and Leave. Esc leaves."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

import galaxies.people.player as player_module
from common.dialogs.messages import Message, show_message
from galaxies.missions import DATE_FORMAT, OPEN, Mission
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player

MIN_REPUTATION = 10.0  # the board is for pilots the outposts trust (the same reputation for every political entity)


class MissionBoard:

    def __init__(self, outpost: Outpost, offers: List[Mission]) -> None:
        self.outpost: Outpost = outpost
        self.offers: List[Mission] = offers
        self.title: str = f'Outpost "{outpost.name}", message board'

    @staticmethod
    def is_available(player: Player) -> bool:
        return player.those_who_share.reputation >= MIN_REPUTATION

    @property
    def player(self) -> Player:
        """The current player, looked up at each use: a new game or a load replaces the Player object."""
        return player_module.current_player

    def open(self) -> None:
        """Shows the board. The caller has already counted the visit."""
        self._show('')

    def _mine(self) -> List[Mission]:
        """The missions the player has taken from this outpost and not yet delivered or lost."""
        reference = self.outpost.reference()
        return [m for m in self.player.missions if m.issuer == reference and m.status == OPEN]

    def _show(self, notice: str) -> None:
        mine = self._mine()
        offers = list(self.offers)

        text: str = notice
        text += "Your missions:\n" + (
            ''.join(f" - {m.title()}, until {m.deadline.strftime(DATE_FORMAT)}.\n" for m in mine) if mine else " - None.\n")
        text += "\nAvailable:\n" + (''.join(f" - {m.title()}.\n" for m in offers) if offers else " - Nothing new.\n")

        buttons: List[str] = [f"Deliver: {m.title()}" for m in mine] + [f"Take: {m.title()}" for m in offers] + ["Leave"]

        def on_result(index: Optional[int]) -> None:
            if index is None or index == len(buttons) - 1:
                return
            if index < len(mine):
                self._deliver(mine[index])
            else:
                self._offer(offers[index - len(mine)])

        show_message(Message(self.title, text, buttons), on_result)

    def _offer(self, mission: Mission) -> None:
        text = (
            f"{mission.description()}\n\n"
            f"{mission.reward_text()}"
        )

        def on_result(index: Optional[int]) -> None:
            if index == 0:
                self.offers.remove(mission)
                mission.accept(gem.current_environment.date_time)
                self.player.missions.append(mission)
                self._show(f"Mission taken: {mission.title()}.\n\n")
            else:
                self._show('')

        show_message(Message(self.title, text, ["Take it", "Back"]), on_result)

    def _deliver(self, mission: Mission) -> None:
        if not mission.can_complete(self.player):
            self._show(f"{mission.shortfall(self.player)}\n\n")
            return
        mission.finish(self.player)
        show_message(Message("MISSION COMPLETED", f"{mission.title()}.\n\n{mission.reward_text()}", ["OK"]))
