from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional
import random

import logging
from galaxies.seeds import of_text
from .mission import Mission, register
from galaxies.missions.terms import Terms
from galaxies.settlement_kind import SettlementKind

if TYPE_CHECKING:
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player

logger = logging.getLogger(__name__)

@register
class DeliverOre(Mission):
    """Deliver ore: bring some ore to the outpost that asked for it. The ore is taken from the cargo hold on delivery.

    An offer is drawn from its seed alone: the same outpost and day always give the same offer, and its seed (kept in a
    save) gives back the days, the quantity and whether, and when, somebody else takes the offer."""

    KIND = 'deliver_ore'
    # The numbers that depend on the kind of settlement that asks; the outposts' are tuned, and the portal base's
    # start at a frequency of 0 (no offers yet).
    TERMS = {
        SettlementKind.OUTPOST: Terms(
            frequency=0.3,
            taken_by_others=0.1,
            deadline_days_min=5,
            deadline_days_max=15,
            reward=0.01,
            failure_penalty=-5.0
            ),
        SettlementKind.PORTAL_BASE: Terms(
            frequency=0.0,  # Nope.
            taken_by_others=1.0,
            deadline_days_min=5,
            deadline_days_max=15,
            reward=0.01,
            failure_penalty=-5.0
            ),
    }
    QUANTITY_MIN_1E2 = 1
    QUANTITY_MAX_1E2 = 10

    def __init__(self, quantity: Optional[int] = None, **common: Any) -> None:
        super().__init__(**common)
        # Drawn in this order every time, from the seed: the days (generate draws them first, for the deadline), the
        # quantity.
        days = self.my_random.randint(self.terms.deadline_days_min, self.terms.deadline_days_max)
        amount = self.my_random.randint(DeliverOre.QUANTITY_MIN_1E2, DeliverOre.QUANTITY_MAX_1E2) * 100
        # One roll for each day of the offer's life, the first success being the day somebody else takes it, and a
        # moment in that day. The same draws every time, whatever the outcome.
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        self.quantity: int = amount if quantity is None else quantity
        taken_day = next((index for index, roll in enumerate(rolls)
                          if roll < self.terms.taken_by_others), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

    @classmethod
    def offer(cls, day: datetime, outpost: Settlement, chance: random.Random) -> Optional[DeliverOre]:
        return cls.generate(day, outpost)

    @staticmethod
    def generate(created_at: datetime, outpost: Settlement) -> DeliverOre:
        """The offer made on the day of `created_at`: its seed is the outpost and the day."""
        seed = of_text(f"{outpost.full_keys()} {DeliverOre.KIND} {created_at.date().isoformat()}")
        # the first draw of the seed, as in __init__
        days = random.Random(seed).randint(DeliverOre.terms_at(outpost.kind).deadline_days_min,
                                       DeliverOre.terms_at(outpost.kind).deadline_days_max)
        return DeliverOre(
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=outpost.full_keys(),
            issuer_kind=outpost.kind,
            destination_kind=outpost.kind,
        )

    def title(self) -> str:
        return f"Deliver {self.quantity} PGM ore" # Later REE and others, see Copilot chat.

    def description(self) -> str:
        return (f"A factory needs {self.quantity} Kg of PGM ore. "
                f"It is to be delivered here, at {self.issuer_settlement.address()}. "
                f"Please bring them in time, Pilot.")

    def can_complete(self, player: Player) -> bool:
        return player.ship.cargo_hold.ore >= self.quantity

    def complete(self, player: Player) -> None:
        player.ship.cargo_hold.ore -= self.quantity

    def shortfall(self, player: Player) -> str:
        return f"You carry {player.ship.cargo_hold.ore:g} ore, and the mission asks for {self.quantity}."

    def give_reward(self, player: Player) -> None:
        reputation_change: float = self.terms.reward * self.quantity
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION COMPLETE: {self.quantity} Kg of ore delivered. Reputation +{reputation_change} = "
        f"{player.those_who_share.reputation}")

    def reward_text(self, player: Player) -> str:
        rnd = random.Random(self.seed)  # the same text each time it is shown
        mineral = rnd.choice(['platinum', 'palladium', 'rhodium', 'iridium', 'osmium', 'ruthenium'])
        return f"Thank you Pilot {player.surname}, this {mineral}-rich ore will help the Community."

    def fail(self, player: Player) -> None:
        reputation_change: float = self.terms.failure_penalty # If you did not have the time don't accept the mission.
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION FAILED: Ore not brought. Reputation {reputation_change} = "
        f"{player.those_who_share.reputation}")

    def serialize(self) -> dict:
        return {**super().serialize(), 'quantity': self.quantity}

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverOre:
        return DeliverOre(source['quantity'], **Mission._common(source))
