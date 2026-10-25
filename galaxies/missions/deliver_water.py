"""Deliver raw water: bring any amount of scooped raw water to the outpost that asked for it."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, List, Optional
import random

import logging
from galaxies.seeds import of_text
from galaxies.world_surface import SurfaceType
from .mission import OPEN, Mission, register

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player
    from galaxies.rocky_world import RockyWorld

logger = logging.getLogger(__name__)


@register
class DeliverWater(Mission):
    KIND = 'deliver_water'
    CHANCES_PER_DAY = 0.2 # Still testing. Later 0.05
    DEADLINE_DAYS_MIN = 5
    DEADLINE_DAYS_MAX = 10
    TAKEN_BY_OTHERS_CHANCE_PER_DAY = 0.2
    MINIMUM_REWARD = 1.0  # reputation and sympathy in the outpost
    REWARD_PER_KG_ICY_SYSTEM = 0.001  # per Kg when the system has an icy world: a short trip
    REWARD_PER_KG_NO_ICE = 0.01  # when it has none: the pilot must go to another system
    FAILURE_PENALTY = -20 # Promising water and not delivering is a SERIOUS problem.

    def __init__(self, **common: Any) -> None:
        super().__init__(**common)
        days = self.my_random.randint(DeliverWater.DEADLINE_DAYS_MIN, DeliverWater.DEADLINE_DAYS_MAX)
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        taken_day = next((index for index, roll in enumerate(rolls)  # rolled per day from creation until now.
                          if roll < DeliverWater.TAKEN_BY_OTHERS_CHANCE_PER_DAY), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)
        self.delivered: float = 0.0  # Kg the last delivery took, for the reward given right after it (not saved)

    @classmethod
    def offer(cls, day: datetime, outpost: Outpost, chance: random.Random) -> Optional[DeliverWater]:
        if outpost.planet.surface_type is SurfaceType.ICE:  # an outpost on an icy world does not need this.
            return None
        return cls.generate(day, outpost)

    @staticmethod
    def generate(created_at: datetime, outpost: Outpost) -> DeliverWater:
        """The offer made on the day of `created_at`: its seed is the outpost and the day."""
        seed = of_text(f"{outpost.full_keys()} {DeliverWater.KIND} {created_at.date().isoformat()}")
        # the first draw of the seed, as in __init__
        days = random.Random(seed).randint(DeliverWater.DEADLINE_DAYS_MIN, DeliverWater.DEADLINE_DAYS_MAX)
        return DeliverWater(
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=outpost.full_keys(),
        )

    def icy_worlds(self) -> List[RockyWorld]:
        """The icy worlds of the planetary system of the issuer's planet: the planet and its moons."""
        from galaxies.rocky_world import RockyWorld
        planet = self.issuer_outpost.planet
        return [world for world in [planet, *planet.moons]
                if isinstance(world, RockyWorld) and world.surface_type is SurfaceType.ICE]

    def title(self) -> str:
        return f"Deliver Water to {self.issuer_outpost.name}."

    def description(self) -> str:
        return (
            f"The water reserves are running low here at {self.issuer_outpost.address()}."
            "We need ships with scoop to retrieve and deliver us raw water. Only reliable pilots, please."
            )

    def progress(self) -> str:
        if self.status != OPEN:
            return ''
        import galaxies.people.player as player_module
        return f"Raw water in the hold: {player_module.current_player.ship.cargo_hold.raw_water:.0f} Kg."

    def can_complete(self, player: Player) -> bool:
        return player.ship.cargo_hold.raw_water > 0.0

    def complete(self, player: Player) -> None:
        """Takes all the raw water from the hold. It takes time."""
        hold = player.ship.cargo_hold
        self.delivered = hold.raw_water
        hold.raw_water = 0.0
        outpost = self.destination_outpost
        outpost.start_handle(player.ship, extra_seconds=self.delivered / outpost.UNLOAD_RAW_WATER_PER_SECOND)

    def shortfall(self, player: Player) -> str:
        return "You carry no raw water."

    def give_reward(self, player: Player) -> None:
        rate = DeliverWater.REWARD_PER_KG_ICY_SYSTEM if self.icy_worlds() else DeliverWater.REWARD_PER_KG_NO_ICE
        reputation_change: float = DeliverWater.MINIMUM_REWARD + rate * self.delivered

        player.those_who_share.reputation += reputation_change
        for crew in self.issuer_outpost.staff:
            crew.adjust_sympathy(reputation_change)

        logger.info(
            f"MISSION COMPLETE: {self.delivered} Kg of raw water delivered. Reputation +{reputation_change} = "
            f"{player.those_who_share.reputation}"
            )

    def reward_text(self, player: Player) -> str:
        return f"We thanks Pilot {player.surname} for the raw water, we start its processing immediately."

    def fail(self, player: Player) -> None:
        reputation_change: float = DeliverWater.FAILURE_PENALTY

        player.those_who_share.reputation += reputation_change
        for crew in self.issuer_outpost.staff:
            crew.adjust_sympathy(reputation_change)

        logger.info(
            f"MISSION FAILED: Raw water not brought. Reputation {reputation_change} = "
            f"{player.those_who_share.reputation}"
            )

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverWater:
        return DeliverWater(**Mission._common(source))
