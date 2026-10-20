"""Scan an object and come back with the information.

There will be different kinds of objects which can be scanned. At this point, only rocks.

A rock mission asks for a rock with an adjective (weird, mysterious or strange). The rock is chosen when the offer is made, from
the mission's seed, and its place is kept in the mission (the world, the Km2 and the rock's coordinates), so it is the same
after a load. The adjective is given to the rock only when the pilot takes the mission (`accept`), so an offer nobody takes
leaves the world as it was."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional
import logging
import math
import random

from .mission import Mission, OPEN, register, seed_of

if TYPE_CHECKING:
    from galaxies.km2 import Km2
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player
    from galaxies.rock import Rock
    from galaxies.world import World

logger = logging.getLogger(__name__)


@register
class ScanObject(Mission):
    """Scan an object somewhere, then come back."""
    KIND = 'scan_object'
    CHANCES_PER_DAY = 0.20
    DAYS_MIN = 10
    DAYS_MAX = 30
    TAKEN_BY_OTHERS_CHANCE_PER_DAY = 0.1  # each day of an offer's life, from the day it is made: the chance somebody takes it

    def __init__(
            self, object_type: str = '',
            rock_site: Optional[dict] = None,
            adjective: str = '',
            was_scanned: bool = False,
            **common: Any) -> None:
        super().__init__(**common)

        # Drawn in this order every time, from the seed.
        days = self.my_random.randint(ScanObject.DAYS_MIN, ScanObject.DAYS_MAX)

        # One roll for each day of the offer's life, the first success being the day somebody else takes it, and a moment
        # in that day. The same draws every time, whatever the outcome.
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()

        taken_day = next((index for index, roll in enumerate(rolls) if roll < ScanObject.TAKEN_BY_OTHERS_CHANCE_PER_DAY), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)

        self.was_scanned: bool = was_scanned
        self.object_type: str = object_type
        # Where the rock is: 'world' is None for the planet or the index of a moon, 'km2' the longitude and latitude of its Km2,
        # 'rock' the rock's own longitude and latitude. Only drawn for a new offer; a loaded mission keeps what it was given.
        self.rock_site: Optional[dict] = rock_site
        self.adjective: str = adjective
        if self.object_type == 'rock' and self.rock_site is None:
            self.rock_site = self._choose_rock_site()
            if self.rock_site is not None:
                from galaxies.rock import Rock  # local: the rock module needs the galaxy package to load first
                self.adjective = self.my_random.choice(Rock.ADJECTIVES)

    # region The rock's site
    def _choose_rock_site(self) -> Optional[dict]:
        """A random rock that is not molten, on the planet or on one of its moons, from the mission's seed. One place is tried:
        None if that place has no rock left, or has an outpost (the people there would have scanned it themselves)."""
        from galaxies.km2 import Km2
        planet = self.issuer_outpost.planet
        index = self.my_random.randrange(len(planet.moons) + 1) - 1  # -1 is the planet itself
        world = planet if index < 0 else planet.moons[index]
        half_turn = math.pi * world.radius  # the surface's coordinates, as Navigation keeps them
        longitude = int(self.my_random.uniform(-half_turn, half_turn))
        latitude = int(world.radius * math.asin(self.my_random.uniform(-1.0, 1.0)))  # uniform over the sphere
        cell_longitude = int((longitude // Km2.SIZE) * Km2.SIZE)
        cell_latitude = int((latitude // Km2.SIZE) * Km2.SIZE)
        if any((outpost.longitude // Km2.SIZE) * Km2.SIZE == cell_longitude
               and (outpost.latitude // Km2.SIZE) * Km2.SIZE == cell_latitude for outpost in world.outposts.values()):
            return None  # checked before the Km2 is made: making one next to an outpost prepares that outpost
        km2 = self._km2_at(world, cell_longitude, cell_latitude, keep=False)
        if not km2.rocks:
            return None
        rock = self.my_random.choice(km2.rocks)  # the rocks in a Km2 are not molten: a molten one is taken out of them
        return {'world': None if index < 0 else index,
                'km2': [km2.longitude, km2.latitude],
                'rock': [rock.longitude, rock.latitude]}

    @staticmethod
    def _km2_at(world: World, cell_longitude: int, cell_latitude: int, keep: bool) -> Km2:
        """The Km2 of a cell: the one in memory if it is loaded, else a new one, which is put in the world's Km2s if
        `keep` (so that a change to it is kept), or only made for the moment."""
        from galaxies.km2 import Km2
        km2 = world.get_km2_at(cell_longitude, cell_latitude)
        if km2 is None:
            km2 = Km2(world, cell_longitude, cell_latitude, world.saved_alterations)
            if keep:
                world.km2s.append(km2)
        return km2

    def _world(self) -> World:
        """The world the rock is on: the planet of the outpost, or one of its moons."""
        planet = self.issuer_outpost.planet
        index = self.rock_site['world']
        return planet if index is None else planet.moons[index]

    def _rock_at_site(self) -> Optional[Rock]:
        """The mission's rock. Its Km2 is put in the world's Km2s if it was not loaded, so that the change is kept."""
        cell_longitude, cell_latitude = self.rock_site['km2']
        km2 = self._km2_at(self._world(), cell_longitude, cell_latitude, keep=True)
        longitude, latitude = self.rock_site['rock']
        return next((rock for rock in km2.rocks if rock.longitude == longitude and rock.latitude == latitude), None)
    # endregion

    # region Offer
    @classmethod
    def offer(cls, day: datetime, outpost: Outpost, chance: random.Random) -> Optional[ScanObject]:
        object_types = ['rock']  # Later: worlds, outposts (spionage!), mines, ore fields.
        object_type = chance.choice(object_types)
        mission = cls.generate(day, object_type, outpost)
        if object_type == 'rock' and mission.rock_site is None:
            return None  # no rock could be found for it
        return mission

    @staticmethod
    def generate(created_at: datetime, object_type: str, outpost: Outpost) -> ScanObject:
        """The offer made on the day of `created_at`: its seed is the outpost and the day."""
        seed = seed_of(f"{outpost.full_keys()} {ScanObject.KIND} {created_at.date().isoformat()}")
        days = random.Random(seed).randint(ScanObject.DAYS_MIN, ScanObject.DAYS_MAX)  # the first draw of the seed, as in __init__
        return ScanObject(
            object_type=object_type,
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=outpost.full_keys(),
        )
    # endregion

    # region The mission
    def accept(self, now: datetime) -> None:
        """The pilot takes the offer: its rock gets the adjective, so the rock is the one the mission asks for."""
        super().accept(now)
        if self.object_type != 'rock':
            return
        rock = self._rock_at_site()
        if rock is None:
            logger.warning(f"The rock of the mission {self.seed} is not there any more.")
            return
        rock.set_adjective(self.adjective)

    def on_rock_scanned(self, rock: Rock) -> None:
        """The mission's rock, scanned while the mission is taken, counts as scanned."""
        if self.status != OPEN or self.object_type != 'rock' or self.was_scanned:
            return
        if rock.parent_km2.parent_world is self._world() and [rock.longitude, rock.latitude] == self.rock_site['rock']:
            self.was_scanned = True

    def progress(self) -> str:
        if self.accepted_at is None:
            return ''
        if self.was_scanned:
            return f"The {self.adjective} {self.object_type} is scanned: bring the results to {self.issuer_outpost.name}."
        return f"The {self.adjective} {self.object_type} is not scanned yet."

    def title(self) -> str:
        return f"Scan a {self.object_type}."

    def description(self) -> str:
        world = self._world()
        longitude, latitude = self.rock_site['rock']
        return (
            f"We have found an interesting {self.adjective} {self.object_type} in ({longitude}, {latitude}) on {world.name}."
            f" Scan it, please, and bring the results to here, at {self.issuer_outpost.address()}."
        )

    def can_complete(self, player: Player) -> bool:
        return self.was_scanned

    def complete(self, player: Player) -> None:
        """Nothing is taken from the player: the scan is what was asked."""

    def shortfall(self, player: Player) -> str:
        return f"You have not scanned the {self.object_type} yet."

    def give_reward(self, player: Player) -> None:
        reputation_change: float = 0.5 # Later... depends on distance? When asteroids.
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION COMPLETE: {self.object_type} scanned. Reputation +{reputation_change} = {player.those_who_share.reputation}")

    def reward_text(self, player: Player) -> str:
        return f"Thank you {player.get_title()}, knowledge about this {self.adjective} object will help the Community."

    def fail(self, player: Player) -> None:
        reputation_change: float = -5 # If you did not have the time don't accept the mission.
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION FAILED: {self.object_type} not scanned. Reputation {reputation_change} = {player.those_who_share.reputation}")
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {**super().serialize(), 'object_type': self.object_type, 'rock_site': self.rock_site,
                'adjective': self.adjective, 'was_scanned': self.was_scanned}

    @classmethod
    def _deserialize(cls, source: dict) -> ScanObject:
        return ScanObject(source['object_type'], source['rock_site'], source['adjective'], source['was_scanned'],
                          **Mission._common(source))
    # endregion
