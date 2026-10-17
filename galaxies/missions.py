"""Missions: what an outpost asks of the pilot (shown by mission_board.py).

An outpost makes its offers when the pilot opens its board (`Outpost.generate_missions`); they are not saved. The ones the
pilot takes go to `Player.missions` and stay there for good, with their status (OPEN, DONE or FAILED): that list is
the only place missions are saved.

Each kind of mission is a subclass with its own objective, registered with `@_register`. A mission knows whether the
player can complete it (`can_complete`) and what that takes from them (`complete`). The reward (`reward_text`, `give_reward`)
and the effects of failing (`fail`) are decided later, per kind.

An OPEN mission is in the `update_queue` for its deadline (it is an Updatable): when the deadline passes it becomes
FAILED, the ship says so, and `fail` runs. The queue is emptied on every new game and load, so `Player.deserialize` puts
the OPEN missions back. DeliverOre is the first kind: bring some ore to the outpost that asked for it."""

from __future__ import annotations
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Optional, Type
import random

from common.updating import Updatable, update_queue

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player

DATE_FORMAT = '%Y-%m-%d %H:%M'

OPEN = 'open'  # taken, not yet delivered and not yet late
DONE = 'done'
FAILED = 'failed'

_KINDS: Dict[str, Type[Mission]] = {}


def _register(kind: Type[Mission]) -> Type[Mission]:
    _KINDS[kind.KIND] = kind
    return kind


class Mission(Updatable):
    """What every mission has: who asked for it, how long the player has once they take it, when they did and its status.
    Subclasses add the objective."""

    KIND: str = ''

    def __init__(self, issuer: str, issuer_name: str, duration: timedelta, accepted_at: Optional[datetime] = None,
                 status: str = OPEN) -> None:
        self.issuer: str = issuer  # Outpost.reference() of the outpost that asked for it
        self.issuer_name: str = issuer_name  # where that is, for the player: Outpost.place()
        self.duration: timedelta = duration
        self.accepted_at: Optional[datetime] = accepted_at  # None while it is only an offer
        self.status: str = status

    @property
    def deadline(self) -> Optional[datetime]:
        """The date and time it is too late, None while the mission has not been taken."""
        return None if self.accepted_at is None else self.accepted_at + self.duration

    def accept(self, now: datetime) -> None:
        """The player takes the offer: the clock starts."""
        self.accepted_at = now
        self.status = OPEN
        update_queue.add(self)

    def watch_deadline(self) -> None:
        """Puts an OPEN mission back in the update queue, after a load."""
        if self.status == OPEN:
            update_queue.add(self)

    def finish(self, player: Player) -> None:
        """The player delivers it: takes what it asks, closes it and gives the reward. Call only if can_complete."""
        self.complete(player)
        self.status = DONE
        update_queue.remove(self)
        self.give_reward(player)

    # Updatable: the deadline
    def get_next_update(self) -> datetime:
        return self.deadline

    def update(self, game_date_time: datetime) -> None:
        """The deadline has passed."""
        import galaxies.people.player as player_module
        player = player_module.current_player
        self.status = FAILED
        player.ship.notification.set(f"Mission failed: {self.title()}.")
        self.fail(player)

    @abstractmethod
    def title(self) -> str:
        ...

    @abstractmethod
    def description(self) -> str:
        """What the mission asks, as the outpost says it, for the offer's detail."""

    @abstractmethod
    def can_complete(self, player: Player) -> bool:
        ...

    @abstractmethod
    def complete(self, player: Player) -> None:
        """Takes from the player what the mission asks."""

    @abstractmethod
    def shortfall(self, player: Player) -> str:
        """What the player still lacks, for the message shown when they try to complete it without enough."""

    def reward_text(self) -> str:
        return "Reward"  # placeholder: the rewards are decided later

    def give_reward(self, player: Player) -> None:
        """Gives the reward. Nothing yet."""

    def fail(self, player: Player) -> None:
        """The effects of failing, per kind. Nothing yet."""

    def serialize(self) -> dict:
        return {
            'kind': self.KIND,
            'issuer': self.issuer,
            'issuer_name': self.issuer_name,
            'duration_seconds': self.duration.total_seconds(),
            'accepted_at': None if self.accepted_at is None else self.accepted_at.isoformat(),
            'status': self.status,
        }

    @staticmethod
    def deserialize(source: dict) -> Mission:
        return _KINDS[source['kind']]._deserialize(source)

    @classmethod
    @abstractmethod
    def _deserialize(cls, source: dict) -> Mission:
        ...

    @staticmethod
    def _common(source: dict) -> dict:
        """The arguments every mission's constructor takes, from its serialized form."""
        return {
            'issuer': source['issuer'],
            'issuer_name': source['issuer_name'],
            'duration': timedelta(seconds=source['duration_seconds']),
            'accepted_at': None if source['accepted_at'] is None else datetime.fromisoformat(source['accepted_at']),
            'status': source['status'],
        }


@_register
class DeliverOre(Mission):
    """Bring `quantity` ore to the outpost that asked for it. The ore is taken from the cargo hold on delivery."""

    KIND = 'deliver_ore'
    QUANTITY_MIN = 100
    QUANTITY_MAX = 500
    DAYS_MIN = 5
    DAYS_MAX = 15

    def __init__(self, quantity: int, **common: object) -> None:
        super().__init__(**common)
        self.quantity: int = quantity

    @staticmethod
    def generate(outpost: Outpost, my_random: random.Random) -> DeliverOre:
        return DeliverOre(
            my_random.randint(DeliverOre.QUANTITY_MIN, DeliverOre.QUANTITY_MAX),
            issuer=outpost.reference(), issuer_name=outpost.place(),
            duration=timedelta(days=my_random.randint(DeliverOre.DAYS_MIN, DeliverOre.DAYS_MAX)),
        )

    def title(self) -> str:
        return f"Deliver {self.quantity} ore"

    def description(self) -> str:
        return f"We need {self.quantity} ore here, at {self.issuer_name}. You would have {self.duration.days} days."

    def can_complete(self, player: Player) -> bool:
        return player.ship.cargo_hold.ore >= self.quantity

    def complete(self, player: Player) -> None:
        player.ship.cargo_hold.ore -= self.quantity

    def shortfall(self, player: Player) -> str:
        return f"You carry {player.ship.cargo_hold.ore:g} ore, and the mission asks for {self.quantity}."

    def serialize(self) -> dict:
        return {**super().serialize(), 'quantity': self.quantity}

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverOre:
        return DeliverOre(source['quantity'], **Mission._common(source))
