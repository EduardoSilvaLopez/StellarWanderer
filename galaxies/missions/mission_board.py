"""The mission board of an outpost, for a pilot whose reputation is MIN_REPUTATION or more. It is the Missions option of
the outpost's screen (OutpostMissions, common/dialogs/mission_board_dialog.py), which updates its offers when it opens.
A pilot below MIN_REPUTATION sees no offers, but still the missions they took from here (the Taken column), so that the
option is there while one is open here (see OutpostScreenDialog._shows_option).

The board belongs to its settlement (`Settlement.mission_board`), and so do its offers: they stay on the board while the
settlement is in memory. They are not saved: an offer is drawn from its settlement, kind and day alone, and lives at
most the longest deadline of its terms (`LOOK_BACK_DAYS`), so `update_missions` finds every offer that can still be
alive by looking back that far,
however the board was visited, saved or loaded. Each offer can be taken, and each mission the player has taken can be
delivered. An offer's deadline is fixed when the offer is made, so taking it late does not give more time. An offer can
also be taken by somebody else before that (`Mission.taken_by_others_at`, drawn from its seed): it is then gone from the
board."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional

import logging

from common import audio
import galaxies.people.player as player_module
from galaxies.missions import Mission, OPEN, DeliverOre, DeliverPackage, DeliverWater, ScanAsteroid, ScanRock
from galaxies.missions.terms import check_terms
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player

logger = logging.getLogger(__name__)

MIN_REPUTATION = 20.0  # the board is for pilots the outposts trust (the same reputation for every political entity)
DATE_FORMAT = '%Y-%m-%d %H:%M'  # the deadlines on the board
KINDS = (DeliverOre, DeliverPackage, DeliverWater, ScanRock, ScanAsteroid)  # what a board offers: a new kind of mission
# comes here
LOOK_BACK_DAYS = max(terms.deadline_days_max for kind in KINDS for terms in kind.TERMS.values())  # an older offer
# has expired, whatever its kind and settlement
check_terms(KINDS)  # every kind has terms for every kind of settlement: stop here, at start-up, if one is missing

class MissionBoard:

    def __init__(self, outpost: Settlement) -> None:
        self.outpost: Settlement = outpost
        self.offers: List[Mission] = []
        self.updated_at: Optional[datetime] = None  # not saved: only so that the days already asked are not asked again

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

    def update_missions(self, now: datetime) -> None:
        logger.debug(f"Updating offers. {len(self.offers)} in the beginning.")
        self.offers = [offer for offer in self.offers if offer.deadline > now and not offer.is_taken_by_others(now)]

        # Insert the offers, day by day from LOOK_BACK_DAYS ago (or the last update, if it is later) to today: each day
        # asks each kind. The day of the last update is asked again, as it was not over. An offer already on the board,
        # one the player has taken (or done or failed), or one that has expired or has been taken by somebody else, is
        # not added.
        known: set = {offer.seed for offer in self.offers} | {mission.seed for mission in self.player.missions}
        first_day = now - timedelta(days=LOOK_BACK_DAYS)
        if self.updated_at is not None:
            first_day = max(first_day, self.updated_at)
        day = first_day.replace(hour=0, minute=0, second=0, microsecond=0)
        while day < now:
            for kind in KINDS:
                offer = kind.offered_on(day, self.outpost)
                if (offer is not None and offer.deadline > now and not offer.is_taken_by_others(now)
                        and offer.seed not in known):
                    self.offers.append(offer)
                    known.add(offer.seed)
            day += timedelta(days=1)
        self.updated_at = now
        logger.debug(f"Offers updated. {len(self.offers)} now.")

    def accept(self, offer: Mission) -> None:
        """The player takes an offer: it leaves the board for the player's missions. Too late if its deadline has
        passed (it is removed from the board at the next update)."""
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
        """The player brings what a mission they have taken asks for. Returns the reward text, to show, when it is
        done. Not enough: they are told what is missing, and nothing is returned."""
        if mission not in self.mine():
            return None
        if not mission.can_complete(self.player):
            self.player.ship.notification.set(mission.shortfall(self.player))
            return None
        mission.finish(self.player)
        audio.play('mission_delivered')
        return mission.reward_text(self.player)
