"""Deliver ore: bring some ore to the outpost that asked for it. The ore is taken from the cargo hold on delivery.

An offer is drawn from its seed alone: the same outpost and day always give the same offer, and its seed (kept in a save)
gives back the days, the quantity and whether, and when, somebody else takes the offer."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional
import random

from .mission import Mission, register, seed_of

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player


@register
class DeliverOre(Mission):
    """Bring `quantity` ore to the outpost that asked for it. The ore is taken from the cargo hold on delivery."""

    KIND = 'deliver_ore'
    CHANCES_PER_DAY = 0.99
    QUANTITY_MIN_1E2 = 1
    QUANTITY_MAX_1E2 = 10
    DAYS_MIN = 5
    DAYS_MAX = 15
    TAKEN_BY_OTHERS_CHANCE_PER_DAY = 0.1  # each day of an offer's life, from the day it is made: the chance somebody takes it

    def __init__(self, quantity: Optional[int] = None, **common: Any) -> None:
        super().__init__(**common)
        # Drawn in this order every time, from the seed. A loaded mission passes its own deadline and quantity, which win.
        days = self.my_random.randint(DeliverOre.DAYS_MIN, DeliverOre.DAYS_MAX)
        amount = self.my_random.randint(DeliverOre.QUANTITY_MIN_1E2, DeliverOre.QUANTITY_MAX_1E2) * 100
        # One roll for each day of the offer's life, the first success being the day somebody else takes it, and a moment
        # in that day. The same draws every time, whatever the outcome.
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        if self.deadline is None:
            self.deadline = self.created_at + timedelta(days=days)
        self.quantity: int = amount if quantity is None else quantity
        taken_day = next((index for index, roll in enumerate(rolls) if roll < DeliverOre.TAKEN_BY_OTHERS_CHANCE_PER_DAY), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

    @staticmethod
    def offered_on(day: datetime, outpost: Outpost) -> Optional[DeliverOre]:
        """The offer `outpost` makes on the day of `day`, or None when it makes none that day. Drawn from the outpost and the
        day only, so it is the same however the board was visited."""
        chance = random.Random(seed_of(f"{outpost.full_keys()} {DeliverOre.KIND} offer {day.date().isoformat()}"))
        if chance.random() >= DeliverOre.CHANCES_PER_DAY:
            return None
        return DeliverOre.generate(day, outpost)

    @staticmethod
    def generate(created_at: datetime, outpost: Outpost) -> DeliverOre:
        """The offer made on the day of `created_at`: its seed is the outpost and the day."""
        seed = seed_of(f"{outpost.full_keys()} {DeliverOre.KIND} {created_at.date().isoformat()}")
        return DeliverOre(
            seed=seed,
            issuer=outpost.full_keys(),
            issuer_name=outpost.address(),
            created_at=created_at,
        )

    def title(self) -> str:
        return f"Deliver {self.quantity} PGM ore" # Later REE and others, see Copilot chat.

    def description(self) -> str:
        return f"A factory needs {self.quantity} Kg of PGM ore. It is to be delivered here, at {self.issuer_name}. Please bring them in time, Pilot."

    def can_complete(self, player: Player) -> bool:
        return player.ship.cargo_hold.ore >= self.quantity

    def complete(self, player: Player) -> None:
        player.those_who_share.reputation += 0.012 * self.quantity
        player.ship.cargo_hold.ore -= self.quantity

    def shortfall(self, player: Player) -> str:
        return f"You carry {player.ship.cargo_hold.ore:g} ore, and the mission asks for {self.quantity}."

    def reward_text(self) -> str:
        rnd = random.Random(self.seed)  # the same text each time it is shown
        mineral = rnd.choice(['platinum', 'palladium', 'rhodium', 'iridium', 'osmium', 'ruthenium'])
        return f"Thank you, citizen, this {mineral}-rich ore will help the Community."

    def serialize(self) -> dict:
        return {**super().serialize(), 'quantity': self.quantity}

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverOre:
        return DeliverOre(source['quantity'], **Mission._common(source))
