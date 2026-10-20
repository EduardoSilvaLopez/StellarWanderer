from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

from datetime import datetime, timedelta
import random

import logging
from .mission import Mission, register, seed_of

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.person import Person
    from galaxies.people.player import Player

@register
class DeliverPackage(Mission):
    """Deliver package: bring some package from a person of this outpost to a person of another one."""

    KIND = 'deliver_package'
    CHANCES_PER_DAY = 0.05
    DAYS_MIN = 5
    DAYS_MAX = 25
    TAKEN_BY_OTHERS_CHANCE_PER_DAY = 0.02  # each day of an offer's life, from the day it is made: the chance somebody takes it

    def __init__(
            self, sender_seed: Optional[float] = None,
            recipient_seed: Optional[float] = None,
            **common: Any) -> None:
        super().__init__(**common)

        # Drawn in this order every time, from the seed: the days (generate draws them first, for the deadline).
        days = self.my_random.randint(DeliverPackage.DAYS_MIN, DeliverPackage.DAYS_MAX)
        # One roll for each day of the offer's life, the first success being the day somebody else takes it, and a moment
        # in that day. The same draws every time, whatever the outcome.
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        taken_day = next((index for index, roll in enumerate(rolls) if roll < DeliverPackage.TAKEN_BY_OTHERS_CHANCE_PER_DAY), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

        # The sender and the recipient are any of the staff of each outpost, which is generated here, so that nothing that
        # reads them later (the description, drawn every frame) has to create anybody. A new offer draws them from its seed;
        # a loaded mission is given the seeds of its own.
        self.issuer_outpost.generate_staff()
        self.destination_outpost.generate_staff()
        staff_size = self.issuer_outpost.STAFF_SIZE
        self.sender: Person = self.issuer_outpost.staff[self.my_random.randrange(staff_size)] \
            if sender_seed is None else self._staff_member(self.issuer_outpost, sender_seed)
        self.recipient: Person = self.destination_outpost.staff[self.my_random.randrange(staff_size)] \
            if recipient_seed is None else self._staff_member(self.destination_outpost, recipient_seed)

    @staticmethod
    def _staff_member(outpost: Outpost, seed: float) -> Person:
        """The staff member of `outpost` with that seed: it must be one of them."""
        person = outpost.person_with_seed(seed)
        if person is None:
            raise KeyError(f"The outpost {outpost.name} has no staff member with the seed {seed}.")
        return person

    # region Offer
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
    # endregion

    # region The mission
    def accept(self, now: datetime) -> None:
        """Taken: the sender and the recipient are kept in `persons`, though the player has not met them."""
        super().accept(now)
        self.sender.record()
        self.recipient.record()

    def title(self) -> str:
        return f"Deliver a package to {self.destination_outpost.name}"

    def description(self) -> str:
        return (
            f"{self.sender.get_full_name()} needs somebody to deliver an urgent package to"
            f" {self.recipient.get_full_name()} in {self.destination_outpost.address()}."
            )

    def can_complete(self, player: Player) -> bool:
        return True

    def complete(self, player: Player) -> None:
        """Nothing is taken from the player: the package is the mission."""

    def shortfall(self, player: Player) -> str:
        return f"Bring the package to {self.destination_outpost.name}."

    def give_reward(self, player: Player) -> None:
        import game_environment as gem
        if self.deadline == self.created_at:
            logger.error(f"self.deadline ({self.deadline}) == self.created_at ({self.created_at})")
            return

        speed_factor: float = (self.deadline - gem.current_environment.date_time).total_seconds() \
            / (self.deadline - self.created_at).total_seconds()

        reputation_change: float = 2.0 * speed_factor
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION COMPLETE: Package delivered at %{100*speed_factor:.0f} of time ahead of deadline. Reputation +{reputation_change} = {player.those_who_share.reputation}")
        # Unfair but realistic, if the offer was old, you cannot bring it *so* fast.

        # The main people involved are very happy.
        self.sender.adjust_sympathy(20)
        self.recipient.adjust_sympathy(25)

        # But also so the whole outpost.
        from galaxies.outpost import Outpost
        if isinstance(self.sender.residency, Outpost):
            # Everybody there cheers up.
            for s in self.sender.residency.staff:
                s.adjust_sympathy(15)
        if isinstance(self.recipient.residency, Outpost):
            for s in self.recipient.residency.staff:
                s.adjust_sympathy(10)

    def reward_text(self, player: Player) -> str:
        rnd = random.Random(self.seed)  # the same text each time it is shown
        package = rnd.choice(['medicine', 'drug', 'equipment', 'gift', 'delicacy'])
        return f"Thank you {player.get_title()}, this {package} was really expected."

    def fail(self, player: Player) -> None:
        # The main people involved are disappointed. But you tried.
        self.sender.adjust_sympathy(-5)
        self.recipient.adjust_sympathy(-2)
        logger.info("MISSION FAILED: Package not delivered on time.")
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {**super().serialize(), 'sender_seed': self.sender.seed, 'recipient_seed': self.recipient.seed}

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverPackage:
        return DeliverPackage(source['sender_seed'], source['recipient_seed'], **Mission._common(source))
    # endregion
