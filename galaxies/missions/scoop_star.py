"""Take a probe of the corona of the system's star and bring it to the portal base.

The scoop fills the probe by itself while it stays open near the star (`Ship.collect_corona`). The probe is data, like
the scan of an asteroid: no cargo, and the mission keeps its progress. It is offered at the portal base and shown at every
settlement (see mission_board.py), but delivered at the base alone."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from galaxies.seeds import of_text

from .mission import DONE, FAILED, Mission, register
from galaxies.missions.terms import Terms
from galaxies.settlement_kind import SettlementKind

if TYPE_CHECKING:
    from galaxies.body import Body
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player

logger = logging.getLogger(__name__)


@register
class ScoopStar(Mission):
    """Take a probe of the corona, then bring it to the portal base."""
    KIND = 'scoop_star'
    # The offers are made at the portal base only (see MissionBoard.OFFERED_AT_BASE): an outpost has no terms (None).
    TERMS = {
        SettlementKind.OUTPOST: None,
        SettlementKind.PORTAL_BASE: Terms(
            frequency=0.035,
            taken_by_others=0.01,
            deadline_days_min=10,
            deadline_days_max=25,
            reward=25.0,
            failure_penalty=-5.0
            ),
    }
    COLLECTION_SECONDS = 600.0  # of game time with the scoop open in range, to fill the probe

    def __init__(self, probe_progress: float = 0.0, **common: Any) -> None:
        super().__init__(**common)

        # Drawn in this order every time, from the seed.
        days = self.my_random.randint(self.terms.deadline_days_min, self.terms.deadline_days_max)
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        taken_day = next(
            (index for index, roll in enumerate(rolls) if roll < self.terms.taken_by_others),
            None
            )
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

        self.probe_progress: float = probe_progress  # 0 to 1, saved

    # region Offer
    @classmethod
    def offer(cls, day: datetime, outpost: Settlement, chance: random.Random) -> ScoopStar:
        return cls.generate(day, outpost)

    @staticmethod
    def generate(created_at: datetime, outpost: Settlement) -> ScoopStar:
        """The offer made on the day of `created_at`: its seed is the outpost and the day."""
        seed = of_text(f"{outpost.full_keys()} {ScoopStar.KIND} {created_at.date().isoformat()}")
        terms = ScoopStar.terms_at(outpost.kind)
        days = random.Random(seed).randint(terms.deadline_days_min, terms.deadline_days_max)
        return ScoopStar(
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=outpost.full_keys(),
            issuer_kind=outpost.kind,
            destination_kind=outpost.kind,
        )
    # endregion

    # region The mission
    def system_key(self) -> str:
        return self.issuer_settlement.stellar_system.get_alterations_key()

    def collect(self, game_seconds: float) -> None:
        """The probe fills for `game_seconds` more. Says so when it is full."""
        was_full = self.probe_progress >= 1.0
        self.probe_progress = min(1.0, self.probe_progress + game_seconds / ScoopStar.COLLECTION_SECONDS)
        if self.probe_progress >= 1.0 and not was_full:
            import galaxies.people.player as player_module
            player_module.current_player.ship.notification.set(
                "Probe of the corona complete. Bring it to the portal base.")

    def progress(self) -> str:
        if self.accepted_at is None:
            return ''
        if self.status == DONE:
            return "The probe of the corona was delivered."
        if self.status == FAILED:
            return "The probe of the corona was not delivered in time."
        if self.probe_progress >= 1.0:
            return "The probe is complete: bring it to the portal base."
        return f"The probe is {self.probe_progress:.0%} full."

    def target_body(self) -> Body:
        return self.issuer_settlement.stellar_system.star

    def title(self) -> str:
        return "Take a probe of the corona."

    def description(self) -> str:
        return (
            "We need a sample of the corona of our star."
            "\n\nA scoop is required to take it. A heat shield and solar panels are recommended."
            "\n\nGet close enough to the star, stop, open the scoop and let it open until the probe is full."
            "\n\nBring the probe to the portal base."
            )

    def warning(self) -> Optional[str]:
        """No scoop on the ship, and, as for any far target, what the trip may lack."""
        import galaxies.people.player as player_module
        lines = []
        if not player_module.current_player.ship.has_scoop:
            lines.append("Your ship has no scoop installed, and this mission requires one.")
        trip = super().warning()
        if trip is not None:
            lines.append(trip)
        return ' '.join(lines) if lines else None

    def can_complete(self, player: Player) -> bool:
        return self.probe_progress >= 1.0

    def complete(self, player: Player) -> None:
        """Nothing is taken from the player: the probe is data."""

    def shortfall(self, player: Player) -> str:
        return f"Your probe of the corona is only {self.probe_progress:.0%} full."

    def give_reward(self, player: Player) -> None:
        import game_environment as gem
        now = gem.current_environment.date_time
        time_left = max(0.0, (self.deadline - now).total_seconds() / (self.deadline - self.created_at).total_seconds())
        reputation_change: float = self.terms.reward * time_left
        player.reputation += reputation_change
        logger.info(f"MISSION COMPLETE: probe of the corona. Reputation +{reputation_change} = {player.reputation}")

    def reward_text(self, player: Player) -> str:
        return (
            f"Thank you, Pilot {player.surname}. The probe will tell us what the star is made of."
            )

    def fail(self, player: Player) -> None:
        reputation_change: float = self.terms.failure_penalty
        player.reputation += reputation_change
        logger.info(f"MISSION FAILED: probe of the corona not delivered. "
                    f"Reputation {reputation_change} = {player.reputation}")
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {**super().serialize(), 'probe_progress': self.probe_progress}

    @classmethod
    def _deserialize(cls, source: dict) -> ScoopStar:
        return ScoopStar(source['probe_progress'], **Mission._common(source))
    # endregion
