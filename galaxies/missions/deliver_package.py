"""Deliver package: bring some package to another outpost."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

from datetime import datetime, timedelta
import random

import logging
from .mission import Mission, register, seed_of

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player

@register
class DeliverPackage(Mission):
    """Bring a package to an outpost."""

    KIND = 'deliver_package'
    CHANCES_PER_DAY = 0.99
    DAYS_MIN = 5
    DAYS_MAX = 10
    TAKEN_BY_OTHERS_CHANCE_PER_DAY = 0.1  # each day of an offer's life, from the day it is made: the chance somebody takes it

    def __init__(self, **common: Any) -> None:
        super().__init__(**common)

        # Drawn in this order every time, from the seed: the days (generate draws them first, for the deadline).
        days = self.my_random.randint(DeliverPackage.DAYS_MIN, DeliverPackage.DAYS_MAX)
        # One roll for each day of the offer's life, the first success being the day somebody else takes it, and a moment
        # in that day. The same draws every time, whatever the outcome.
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        taken_day = next((index for index, roll in enumerate(rolls) if roll < DeliverPackage.TAKEN_BY_OTHERS_CHANCE_PER_DAY), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

    @classmethod
    def offer(cls, day: datetime, outpost: Outpost, chance: random.Random) -> Optional[DeliverPackage]:
        # The destinations: every other outpost of the system, in the order the worlds list them.
        candidates = [other for world in outpost.planet.stellar_system.get_all_worlds()
                      for other in world.outposts.values() if other is not outpost]
        if not candidates:
            return None  # nowhere to bring a package to
        return cls.generate(day, chance.choice(candidates), outpost)

    @staticmethod
    def generate(created_at: datetime, destination_outpost: Outpost, outpost: Outpost) -> DeliverPackage:
        """The offer made on the day of `created_at`, from `outpost` to `destination_outpost`."""
        seed = seed_of(f"{outpost.full_keys()} {DeliverPackage.KIND} {created_at.date().isoformat()}")
        days = random.Random(seed).randint(DeliverPackage.DAYS_MIN, DeliverPackage.DAYS_MAX)  # the first draw of the seed, as in __init__
        return DeliverPackage(
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=destination_outpost.full_keys(),
        )

    def title(self) -> str:
        return f"Deliver a package to {self.destination_outpost.name}"

    def description(self) -> str:
        return f"We need you to deliver an urgent package to {self.destination_outpost.address()}."

    def can_complete(self, player: Player) -> bool:
        return True

    def complete(self, player: Player) -> None:
        import game_environment as gem
        if self.deadline == self.created_at:
            logger.error(f"self.deadline ({self.deadline}) == self.created_at ({self.created_at})")
            return

        speed_factor: float = (self.deadline - gem.current_environment.date_time).total_seconds() \
            / (self.deadline - self.created_at).total_seconds()

        player.those_who_share.reputation += 10.0 * speed_factor
        # Unfair but realistic, if the offer was old, you cannot bring it *so* fast.

    def shortfall(self, player: Player) -> str:
        return f"Bring the package to {self.destination_outpost.name}."

    def reward_text(self) -> str:
        rnd = random.Random(self.seed)  # the same text each time it is shown
        package = rnd.choice(['medicine', 'drug', 'equipment', 'gift', 'delicacy'])
        return f"Thank you, citizen, this {package} was really expected."

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverPackage:
        return DeliverPackage(**Mission._common(source))
