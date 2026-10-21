"""The base of every mission: what an outpost asks of the pilot (shown by mission_board.py).

An outpost makes its offers on its board (`MissionBoard.update_missions`), which are kept while the outpost is in memory
and not saved. The ones the pilot takes go to `Player.missions` and stay there for good, with their status (OPEN, DONE
or FAILED): that list is the only place missions are saved.

Each kind of mission is a subclass with its own objective (see deliver_ore.py), registered with `register`. A mission
knows whether the player can complete it (`can_complete`), what that takes from them (`complete`) and what it gives them
(`give_reward`, `reward_text`). The effects of failing (`fail`) are decided later, per kind.

An OPEN mission is in the `update_queue` for its deadline (it is an Updatable): when the deadline passes it becomes
FAILED, the ship says so, and `fail` runs. The queue is emptied on every new game and load, so `Player.deserialize` puts
the OPEN missions back."""

from __future__ import annotations
from abc import abstractmethod
from datetime import datetime
import random
import numpy as np
from typing import TYPE_CHECKING, Dict, Optional, Type

from common import audio
from common.updating import Updatable, update_queue
from galaxies.seeds import of_text

if TYPE_CHECKING:
    from galaxies.body import Body
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player
    from galaxies.rock import Rock

OPEN = 'open'  # taken, not yet delivered and not yet late
DONE = 'done'
FAILED = 'failed'

_KINDS: Dict[str, Type[Mission]] = {}


def register[Kind: 'Mission'](kind: Type[Kind]) -> Type[Kind]:
    """Makes a kind of mission known by its KIND, for Mission.deserialize. It returns the class unchanged, and says so
    in its type: a class decorated with it keeps its own members for the editor (`DeliverOre.generate`, references,
    rename)."""
    _KINDS[kind.KIND] = kind
    return kind


class Mission(Updatable):
    """What every mission has: who asked for it, how long the player has once they take it, when they did and its
    status. Subclasses add the objective."""

    KIND: str = ''
    CHANCES_PER_DAY: float = 0.0  # the chance a kind makes an offer on a given day; a kind that makes none keeps 0
    # the most days an offer of the kind lasts (its deadline): how far back the board looks for its offers
    DAYS_MAX: int = 0

    def __init__(self,
                 seed: int,
                 issuer: str,
                 created_at: datetime,
                 deadline: datetime,
                 destination: str,
                 accepted_at: Optional[datetime] = None,
                 status: str = OPEN,
                 ) -> None:
        self.seed: int = seed  # identifies the offer: the rest of it is drawn from it (see generate)
        self.my_random: random.Random = random.Random(self.seed)
        self.created_at: datetime = created_at  # the day the offer was made
        self.issuer: str = issuer  # Outpost.full_keys() of the outpost that asked for it
        self.destination: str = destination  # Outpost.full_keys() of the outpost it is for

        self.deadline: datetime = deadline  # fixed when the offer is made: taking it does not move it
        self.accepted_at: Optional[datetime] = accepted_at  # None while it is only an offer
        self.status: str = status
        # Set by the derived class at creation, like the deadline: when somebody else takes the offer, None if nobody
        # does. It only matters while the mission is an offer on a board; it is not saved.
        self.taken_by_others_at: Optional[datetime] = None

    # region Offers
    @classmethod
    def offered_on(cls, day: datetime, outpost: Outpost) -> Optional[Mission]:
        """The offer `outpost` makes on the day of `day`, or None when it makes none that day. Drawn from the outpost
        and the day only, so it is the same however the board was visited."""
        chance = random.Random(of_text(f"{outpost.full_keys()} {cls.KIND} offer {day.date().isoformat()}"))
        if chance.random() >= cls.CHANCES_PER_DAY:
            return None
        return cls.offer(day, outpost, chance)

    @classmethod
    @abstractmethod
    def offer(cls, day: datetime, outpost: Outpost, chance: random.Random) -> Optional[Mission]:
        """The offer itself, once the day's chance has come up: its kind decides what it asks, with `chance` if it needs
        more."""

    def is_taken_by_others(self, now: datetime) -> bool:
        """Somebody else has taken this offer by `now`, so it is no longer on the board."""
        return self.taken_by_others_at is not None and now >= self.taken_by_others_at
    # endregion

    # region Outposts
    @property
    def issuer_outpost(self) -> Outpost:
        """The outpost that asked for it, found from its keys."""
        import game_environment as gem
        return gem.current_environment.galaxy.outpost_of(self.issuer)

    @property
    def destination_outpost(self) -> Outpost:
        """The outpost it is for, found from its keys."""
        import game_environment as gem
        return gem.current_environment.galaxy.outpost_of(self.destination)
    # endregion

    # region Life of a mission
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

    def get_next_update(self) -> datetime:
        return self.deadline

    def update(self, game_date_time: datetime) -> None:
        """The deadline has passed."""
        import galaxies.people.player as player_module
        player = player_module.current_player
        self.status = FAILED
        player.ship.notification.set(f"Mission failed: {self.title()}.")
        audio.play('mission_failed')
        self.fail(player)
    # endregion

    # region What each kind gives
    def on_rock_scanned(self, rock: Rock) -> None:
        """A rock was scanned. Nothing by default."""

    def progress(self) -> str:
        """Where a taken mission stands, as a line for the player's log. Empty when there is nothing to say."""
        return ''

    @abstractmethod
    def title(self) -> str:
        """The mission in a few words, for the lists."""

    @abstractmethod
    def description(self) -> str:
        """What the mission asks, as the outpost says it, for the offer's detail."""

    def target_body(self) -> Optional[Body]:
        """The body in the issuer's system that the pilot has to travel to, if the mission takes them far: None by
        default (it is the body the long distance advice would be given for)."""
        return None

    def warning(self) -> Optional[str]:
        """A warning for the offer's detail, or None: when the long distance advice, flying from the issuer outpost to
        the target body with the ship at full energy and stores, would be "Too far", it names what the ship may lack
        (`LongDistanceAdvisor.shortage`). It never stops the player from taking the mission: they may be an expert, or
        willing to die trying."""
        import game_environment as gem
        from spaceships.long_distance_advice import LongDistanceAdvisor
        body = self.target_body()
        if body is None:
            return None
        date = gem.current_environment.date_time
        outpost = self.issuer_outpost
        position = np.array(tuple(outpost.stellar_position(date)))
        velocity = np.array(tuple(outpost.planet.calculate_stellar_velocity(date)))
        import galaxies.people.player as player_module
        lacking = LongDistanceAdvisor.shortage(player_module.current_player.ship, body, date, position, velocity)
        return None if lacking is None else f"Your ship may lack the necessary {lacking} for this trip."

    @abstractmethod
    def can_complete(self, player: Player) -> bool:
        """Whether the player has what the mission asks."""

    @abstractmethod
    def complete(self, player: Player) -> None:
        """Takes from the player what the mission asks."""

    @abstractmethod
    def shortfall(self, player: Player) -> str:
        """What the player still lacks, for the message shown when they try to complete it without enough."""

    def can_forget(self, player: Player) -> bool:
        """Whether the pilot may forget what a finished mission was about (see `forget`). Nothing by default."""
        return False

    def forget(self) -> None:
        """Forgets what the mission was about; the mission stays in the history. Nothing by default."""

    def give_reward(self, player: Player) -> None:
        """Gives the reward, after `complete` and once the mission is DONE. Nothing by default."""

    @abstractmethod
    def reward_text(self, player: Player) -> str:
        """What the outpost says when the mission is delivered."""

    def fail(self, player: Player) -> None:
        """The effects of failing, per kind. Nothing yet."""
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {
            'kind': self.KIND,
            'seed': self.seed,
            'issuer': self.issuer,
            'destination': self.destination,
            'created_at': self.created_at.isoformat(),
            'deadline': self.deadline.isoformat(),
            'accepted_at': None if self.accepted_at is None else self.accepted_at.isoformat(),
            'status': self.status,
        }

    @staticmethod
    def deserialize(source: dict) -> Mission:
        return _KINDS[source['kind']]._deserialize(source)

    @classmethod
    @abstractmethod
    def _deserialize(cls, source: dict) -> Mission:
        """The mission of this kind, from its serialized form."""

    @staticmethod
    def _common(source: dict) -> dict:
        """The arguments every mission's constructor takes, from its serialized form."""
        return {
            'seed': source['seed'],
            'issuer': source['issuer'],
            'destination': source['destination'],
            'created_at': datetime.fromisoformat(source['created_at']),
            'deadline': datetime.fromisoformat(source['deadline']),
            'accepted_at': None if source['accepted_at'] is None else datetime.fromisoformat(source['accepted_at']),
            'status': source['status'],
        }
    # endregion
