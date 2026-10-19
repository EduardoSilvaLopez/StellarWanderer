"""The mission board of an outpost, opened with Numpad 5 while the scanner has the outpost, and only for a pilot whose
reputation is MIN_REPUTATION or more. It is shown by MissionBoardDialog (common/dialogs/mission_board_dialog.py).

Opening it counts as a visit to the outpost (`Outpost.last_visited`), not as speaking with the com officer
(`Person.last_communication_at`): the ship is not restocked or repaired here, that takes talking to the com officer.

The board belongs to its outpost (`Outpost.mission_board`), and so do its offers: they stay on the board while the outpost is in
memory, and are not saved (a save or load starts with the offers the outpost makes then). `update_missions` decides which
offers there are when the board is opened. Each offer can be taken, and each mission the player has taken can be delivered.
An offer's deadline is fixed when the offer is made, so taking it late does not give more time. An offer can also be taken by
somebody else before that (`Mission.taken_by_others_at`, drawn from its seed): it is then gone from the board."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional

import galaxies.people.player as player_module
from common import audio
from galaxies.missions import Mission, OPEN, DeliverOre, DeliverPackage
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player

MIN_REPUTATION = 10.0  # the board is for pilots the outposts trust (the same reputation for every political entity)
DATE_FORMAT = '%Y-%m-%d %H:%M'  # the deadlines on the board

class MissionBoard:

    def __init__(self, outpost: Outpost) -> None:
        self.outpost: Outpost = outpost
        self.offers: List[Mission] = []
        self.title: str = f'Outpost "{outpost.name}", message board'

    def update_missions(self, now: datetime) -> None:
        self.offers = [offer for offer in self.offers if offer.deadline > now and not offer.is_taken_by_others(now)]

        # Insert new offers, by type, day by day from the day of the last visit to today (each day asks each type). A first
        # visit looks back 28 days: it gives good chances. The day of the last visit is included, since a visit may have been
        # a talk and not the board; an offer already on the board, one the player has taken (or done or failed), or one
        # that has expired or has been taken by somebody else, is not made again.
        known: set = {offer.seed for offer in self.offers} | {mission.seed for mission in self.player.missions}
        first_day = self.outpost.last_visited if self.outpost.last_visited else now - timedelta(days=28)
        day = first_day.replace(hour=0, minute=0, second=0, microsecond=0)
        while day < now:
            offers: List[Mission] = []

            new_offer = DeliverOre.offered_on(day, self.outpost)
            if new_offer is not None:
                offers.append(new_offer)

            new_offer = DeliverPackage.offered_on(day, self.outpost)
            if new_offer is not None:
                offers.append(new_offer)

            # New types come here.

            for offer in offers:
                if offer.deadline > now and not offer.is_taken_by_others(now) and offer.seed not in known:
                    self.offers.append(offer)
                    known.add(offer.seed)
            day += timedelta(days=1)

    @staticmethod
    def is_available(player: Player) -> bool:
        return player.those_who_share.reputation >= MIN_REPUTATION

    @property
    def player(self) -> Player:
        """The current player, looked up at each use: a new game or a load replaces the Player object."""
        return player_module.current_player

    def mine(self) -> List[Mission]:
        """The missions which can be completed here."""
        dest_keys = self.outpost.full_keys()
        return [m for m in self.player.missions if m.destination == dest_keys and m.status == OPEN]

    def accept(self, offer: Mission) -> None:
        """The player takes an offer: it leaves the board for the player's missions. Too late if its deadline has passed
        (it is removed from the board at the next update)."""
        if offer not in self.offers:
            return
        now = gem.current_environment.date_time
        if offer.deadline <= now:
            self.player.ship.notification.set(f"Too late: {offer.title()}.")
            return
        self.offers.remove(offer)
        offer.accept(now)
        self.player.missions.append(offer)
        self.player.ship.notification.set(f"Mission taken: {offer.title()}.")
        audio.play('mission_taken')

    def deliver(self, mission: Mission) -> Optional[str]:
        """The player brings what a mission they have taken asks for. Returns the reward text, to show, when it is done.
        Not enough: they are told what is missing, and nothing is returned."""
        if mission not in self.mine():
            return None
        if not mission.can_complete(self.player):
            self.player.ship.notification.set(mission.shortfall(self.player))
            return None
        mission.finish(self.player)
        audio.play('mission_delivered')
        return mission.reward_text(self.player)
