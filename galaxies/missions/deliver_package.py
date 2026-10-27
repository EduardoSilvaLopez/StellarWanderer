from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

from datetime import datetime, timedelta
import random

import logging
from galaxies.seeds import of_text
from .mission import Mission, register
from galaxies.missions.terms import Terms
from galaxies.settlement_kind import SettlementKind

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from galaxies.settlement import Settlement
    from galaxies.people.person import Person
    from galaxies.people.player import Player
    from galaxies.body import Body

@register
class DeliverPackage(Mission):
    """Deliver package: bring some package from a person of this outpost to a person of another one."""

    KIND = 'deliver_package'

    # The numbers that depend on the kind of settlement that asks
    TERMS = {
        SettlementKind.OUTPOST: Terms(
            frequency=0.03,
            taken_by_others=0.01,
            deadline_days_min=5,
            deadline_days_max=25,
            reward=2.0,
            failure_penalty=0.1
            ),
        SettlementKind.PORTAL_BASE: Terms(
            frequency=0.03,
            taken_by_others=0.01,
            deadline_days_min=10,
            deadline_days_max=40,
            reward=3.0,
            failure_penalty=0.1
            ),
    }

    def __init__(
            self, sender_seed: Optional[int] = None,
            recipient_seed: Optional[int] = None,
            **common: Any) -> None:
        super().__init__(**common)

        # Drawn in this order every time, from the seed: the days (generate draws them first, for the deadline).
        days = self.my_random.randint(self.terms.deadline_days_min, self.terms.deadline_days_max)
        # One roll for each day of the offer's life, the first success being the day somebody else takes it, and a
        # moment in that day. The same draws every time, whatever the outcome.
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        taken_day = next((index for index, roll in enumerate(rolls)
                          if roll < self.terms.taken_by_others), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

        # The sender and the recipient are any of the staff of each outpost, which is generated here, so that nothing
        # that reads them later (the description, drawn every frame) has to create anybody. A new offer draws them from
        # its seed; a loaded mission is given the seeds of its own.
        self.issuer_settlement.generate_staff()
        self.destination_settlement.generate_staff()
        issuer_staff = self.issuer_settlement.staff
        destination_staff = self.destination_settlement.staff
        self.sender: Person = issuer_staff[self.my_random.randrange(len(issuer_staff))] \
            if sender_seed is None else self._staff_member(self.issuer_settlement, sender_seed)
        self.recipient: Person = destination_staff[self.my_random.randrange(len(destination_staff))] \
            if recipient_seed is None else self._staff_member(self.destination_settlement, recipient_seed)

    @staticmethod
    def _staff_member(outpost: Settlement, seed: int) -> Person:
        """The staff member of `outpost` with that seed: it must be one of them."""
        person = outpost.person_with_seed(seed)
        if person is None:
            raise KeyError(f"The outpost {outpost.name} has no staff member with the seed {seed}.")
        return person

    # region Offer
    @classmethod
    def offer(cls, day: datetime, outpost: Settlement, chance: random.Random) -> Optional[DeliverPackage]:
        # The destinations: every other outpost of the system, in the order the worlds list them.
        candidates = [other for other in outpost.stellar_system.settlements() if other is not outpost]
        if not candidates:
            return None  # nowhere to bring a package to
        return cls.generate(day, chance.choice(candidates), outpost)

    @staticmethod
    def generate(created_at: datetime, destination_settlement: Settlement, outpost: Settlement) -> DeliverPackage:
        """The offer made on the day of `created_at`, from `outpost` to `destination_settlement`."""
        seed = of_text(f"{outpost.full_keys()} {DeliverPackage.KIND} {created_at.date().isoformat()}")
        # the first draw of the seed, as in __init__
        days = random.Random(seed).randint(
            DeliverPackage.terms_at(outpost.kind).deadline_days_min,
            DeliverPackage.terms_at(outpost.kind).deadline_days_max
            )
        return DeliverPackage(
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=destination_settlement.full_keys(),
            issuer_kind=outpost.kind,
            destination_kind=destination_settlement.kind,
        )
    # endregion

    # region The mission
    def accept(self, now: datetime) -> None:
        """Taken: the sender and the recipient are kept in `persons`, though the player has not met them."""
        super().accept(now)
        self.sender.record()
        self.recipient.record()

    def target_body(self) -> Body:
        return self.destination_settlement.body

    def title(self) -> str:
        return f"Deliver a package to {self.destination_settlement.name}"

    def description(self) -> str:
        return (
            f"{self.sender.get_full_name()} needs somebody to deliver an urgent package to"
            f" {self.recipient.get_full_name()} in {self.destination_settlement.address()}."
            )

    def can_complete(self, player: Player) -> bool:
        return True

    def complete(self, player: Player) -> None:
        """Nothing is taken from the player: the package is the mission."""

    def shortfall(self, player: Player) -> str:
        return f"Bring the package to {self.destination_settlement.name}."

    def give_reward(self, player: Player) -> None:
        import game_environment as gem
        if self.deadline == self.created_at:
            logger.error(f"self.deadline ({self.deadline}) == self.created_at ({self.created_at})")
            return

        speed_factor: float = (self.deadline - gem.current_environment.date_time).total_seconds() \
            / (self.deadline - self.created_at).total_seconds()

        reputation_change: float = self.terms.reward * speed_factor
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION COMPLETE: Package delivered at %{100*speed_factor:.0f} of time ahead of deadline. "
        f"Reputation +{reputation_change} = {player.those_who_share.reputation}")
        # Unfair but realistic, if the offer was old, you cannot bring it *so* fast.

        # The main people involved are very happy.
        self.sender.adjust_sympathy(25)
        self.recipient.adjust_sympathy(30)

        # But also so the whole outpost.
        from galaxies.outpost import Outpost
        if isinstance(self.sender.residency, Outpost):
            for s in self.sender.residency.staff:
                s.adjust_sympathy(150 / self.sender.residency.staff.count())
        if isinstance(self.recipient.residency, Outpost):
            for s in self.recipient.residency.staff:
                s.adjust_sympathy(100 / self.sender.residency.staff.count())

    def reward_text(self, player: Player) -> str:
        rnd = random.Random(self.seed)  # the same text each time it is shown
        package = rnd.choice(['medicine', 'drug', 'equipment', 'gift', 'delicacy'])
        return f"Thank you {self.recipient.get_player_title()}, this {package} was really expected."

    def fail(self, player: Player) -> None:
        player.those_who_share -=  self.terms.failure_penalty

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
