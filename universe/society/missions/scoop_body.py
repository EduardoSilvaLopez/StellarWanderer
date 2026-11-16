"""The base of the missions that take a probe of a body with the scoop and bring it to the portal base (`ScoopStar`,
`ScoopGiant`).

The scoop fills the probe by itself while it stays open where the kind says (`can_collect`, see `Ship.collect_probe`).
The probe is data, like the scan of an asteroid: no cargo, and the mission keeps its progress. It is offered at the
portal base and shown at every settlement (see mission_board.py), but delivered at the base alone. A kind says what the
probe is of (`subject`), where it fills, what it asks and what the base answers, and what an offer is for (`_target`).

Idea for later: an offer of a giant could ask for a minimum outside pressure, the deeper the better paid, which would tie
the mission to the `PRESSURE_MAX` of each ship (the Shabby Miner could only take the shallow ones)."""

from __future__ import annotations

import logging
import random
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from galaxies.seeds import of_text

from .mission import DONE, FAILED, Mission

if TYPE_CHECKING:
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player
    from spaceships.ship import Ship

logger = logging.getLogger(__name__)


class ScoopBody(Mission):
    """Take a probe of a body, then bring it to the portal base."""
    COLLECTION_SECONDS = 600.0  # of game time with the scoop open where it fills, to fill the probe

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
    def offer(cls, day: datetime, outpost: Settlement, chance: random.Random) -> Optional[ScoopBody]:
        return cls.generate(day, outpost)

    @classmethod
    def generate(cls, created_at: datetime, outpost: Settlement) -> Optional[ScoopBody]:
        """The offer made on the day of `created_at`: its seed is the outpost and the day. None when the system has
        nothing to take a probe of."""
        seed = of_text(f"{outpost.full_keys()} {cls.KIND} {created_at.date().isoformat()}")
        target = cls._target(outpost, seed)
        if target is None:
            return None
        terms = cls.terms_at(outpost.kind)
        days = random.Random(seed).randint(terms.deadline_days_min, terms.deadline_days_max)
        return cls(
            **target,
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=outpost.full_keys(),
            issuer_kind=outpost.kind,
            destination_kind=outpost.kind,
        )

    @classmethod
    @abstractmethod
    def _target(cls, outpost: Settlement, seed: int) -> Optional[dict]:
        """What the offer is for, as the constructor's arguments (empty when the kind has one target), chosen from the
        seed; None when the outpost's system has no such body."""
    # endregion

    # region The mission
    def system_key(self) -> str:
        return self.issuer_settlement.stellar_system.get_alterations_key()

    @abstractmethod
    def subject(self) -> str:
        """What the probe is of, to go in a sentence: "the corona"."""

    @abstractmethod
    def can_collect(self, ship: Ship) -> bool:
        """Whether the probe fills now: the scoop, if it is open, takes the probe here."""

    def collect(self, game_seconds: float) -> None:
        """The probe fills for `game_seconds` more. Says so when it is full."""
        was_full = self.probe_progress >= 1.0
        self.probe_progress = min(1.0, self.probe_progress + game_seconds / self.COLLECTION_SECONDS)
        if self.probe_progress >= 1.0 and not was_full:
            import galaxies.people.player as player_module
            player_module.current_player.ship.notification.set(
                f"Probe of {self.subject()} complete. Bring it to the portal base.")

    def progress(self) -> str:
        if self.accepted_at is None:
            return ''
        if self.status == DONE:
            return f"The probe of {self.subject()} was delivered."
        if self.status == FAILED:
            return f"The probe of {self.subject()} was not delivered in time."
        if self.probe_progress >= 1.0:
            return "The probe is complete: bring it to the portal base."
        return f"The probe is {self.probe_progress:.0%} full."

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
        return f"Your probe of {self.subject()} is only {self.probe_progress:.0%} full."

    def give_reward(self, player: Player) -> None:
        import game_environment as gem
        now = gem.current_environment.date_time
        time_left = max(0.0, (self.deadline - now).total_seconds() / (self.deadline - self.created_at).total_seconds())
        reputation_change: float = self.terms.reward * time_left
        player.reputation += reputation_change
        logger.info(
            f"MISSION COMPLETE: probe of {self.subject()}. Reputation +{reputation_change} = {player.reputation}"
            )

    def fail(self, player: Player) -> None:
        reputation_change: float = self.terms.failure_penalty
        player.reputation += reputation_change
        logger.info(f"MISSION FAILED: probe of {self.subject()} not delivered. "
                    f"Reputation {reputation_change} = {player.reputation}")
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {**super().serialize(), 'probe_progress': self.probe_progress}
    # endregion
