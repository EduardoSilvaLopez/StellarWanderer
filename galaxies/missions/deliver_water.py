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
    from galaxies.asteroid import Asteroid
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
    REWARD_PER_KG_PLANETARY_ICE = 0.001  # per Kg when the planet's system (its moons) has an icy world: a short trip
    REWARD_PER_KG_STELLAR_ICE = 0.005  # an icy world elsewhere in the star's system
    REWARD_PER_KG_ASTEROID = 0.01  # no icy world in the star's system: the water is from an asteroid
    FAILURE_PENALTY = -20 # Promising water and not delivering is a SERIOUS problem.

    def __init__(self, asteroid_site: dict | None = None, loaded: bool = False, **common: Any) -> None:
        super().__init__(**common)
        days = self.my_random.randint(DeliverWater.DEADLINE_DAYS_MIN, DeliverWater.DEADLINE_DAYS_MAX)
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()
        taken_day = next((index for index, roll in enumerate(rolls)  # rolled per day from creation until now.
                          if roll < DeliverWater.TAKEN_BY_OTHERS_CHANCE_PER_DAY), None)
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)
        self.delivered: float = 0.0  # Kg the last delivery took, for the reward given right after it (not saved)
        # The asteroid the offer shows (an optional source of the water). Drawn only for a new offer: a loaded one keeps
        # what it was given, None included.
        self.asteroid_site: dict | None = asteroid_site
        if not loaded:
            self.asteroid_site = self._choose_asteroid_site()
        self._asteroid: Asteroid | None = None  # made when needed, not saved

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

    # region The asteroid
    def _choose_asteroid_site(self) -> dict | None:
        """The asteroid the offer shows, from the seed: in the belt nearest the planet's orbit, the quarter of it
        nearest that orbit. A system with no belt has a free-living one, made for the offer. None when the sector drawn has no
        asteroid of the tier: the water can come from elsewhere."""
        from galaxies.asteroid import Asteroid
        from galaxies.asteroid_belt import AsteroidBelt
        planet = self.issuer_outpost.planet
        system = planet.parent_orbit.parent_stellar_system
        site = {'system': system.get_alterations_key(), 'belt': None, 'key': None, 'seed': None}
        belts = [orbit for orbit in system.orbits if isinstance(orbit, AsteroidBelt)]
        if not belts:
            site['seed'] = self.seed
            return site
        planet_distance = planet.parent_orbit.distance_from_star
        belt = min(belts, key=lambda candidate: abs(candidate.distance_from_star - planet_distance))
        nearest = min(max(planet_distance, belt.inner), belt.outer)  # the belt's part nearest the planet's orbit
        quarter = (belt.outer - belt.inner) / 4.0
        tiers = [tier for tier, _ in Asteroid.FREE_TIERS]
        weights = [weight for _, weight in Asteroid.FREE_TIERS]
        tier = self.my_random.choices(tiers, weights)[0]
        key = belt.random_key(self.my_random, tier, belt.time_in_epoch(self.created_at)[0],
                              (max(belt.inner, nearest - quarter), min(belt.outer, nearest + quarter)))
        if key is None:
            return None
        site['belt'] = int(belt.number)
        site['key'] = str(key)
        return site

    def asteroid(self) -> Asteroid | None:
        """The asteroid the offer shows: the kept one, else one made for the moment, the same object each time. None
        when the offer has none, or when the scoop has taken it."""
        if self.asteroid_site is None:
            return None
        import game_environment as gem
        from galaxies.asteroid import Asteroid, AsteroidKey
        system = gem.current_environment.galaxy.system_of_key(self.asteroid_site['system'])
        if self.asteroid_site['belt'] is None:
            seed = self.asteroid_site['seed']
            if seed in system.consumed_free:
                return None
            if self._asteroid is None:
                self._asteroid = system.free_asteroids.get(seed) or Asteroid.free_living(system, seed)
            return self._asteroid
        belt = system.get_orbit(float(self.asteroid_site['belt']))
        key = AsteroidKey.from_ints(self.asteroid_site['key'].split())
        if key in belt.consumed:
            return None
        if self._asteroid is None:
            self._asteroid = belt.relevant.get(key) or belt.build(key)
        return self._asteroid

    def accept(self, now: datetime) -> None:
        """The pilot takes the offer: its asteroid, if it has one left, is kept (promoted), as a scan's is."""
        super().accept(now)
        if self.asteroid() is None:
            return
        import game_environment as gem
        from galaxies.asteroid import AsteroidKey
        system = gem.current_environment.galaxy.system_of_key(self.asteroid_site['system'])
        if self.asteroid_site['belt'] is None:
            self._asteroid = system.promote_free_asteroid(self.asteroid_site['seed'])
        else:
            belt = system.get_orbit(float(self.asteroid_site['belt']))
            self._asteroid = belt.promote(AsteroidKey.from_ints(self.asteroid_site['key'].split()))

    def target_body(self) -> Optional[Asteroid]:
        """The asteroid is the target the long distance advice works for. The water does not have to come from it."""
        return self.asteroid()

    def can_forget(self, player: Player) -> bool:
        """Once the mission is over, its asteroid can be forgotten while it is still kept and no open mission asks for
        it (a scan's or another water's)."""
        from .scan_asteroid import ScanAsteroid
        if self.asteroid_site is None or self.status == OPEN or any(
                isinstance(other, (ScanAsteroid, DeliverWater)) and other.status == OPEN
                and other.asteroid_site == self.asteroid_site for other in player.missions):
            return False
        return self._kept()

    def forget(self) -> None:
        import game_environment as gem
        from galaxies.asteroid import AsteroidKey
        system = gem.current_environment.galaxy.system_of_key(self.asteroid_site['system'])
        if self.asteroid_site['belt'] is None:
            system.forget_free_asteroid(self.asteroid_site['seed'])
        else:
            belt = system.get_orbit(float(self.asteroid_site['belt']))
            belt.forget(AsteroidKey.from_ints(self.asteroid_site['key'].split()))

    def _kept(self) -> bool:
        """Whether the asteroid is still kept: by its system (free-living) or its belt."""
        import game_environment as gem
        from galaxies.asteroid import AsteroidKey
        system = gem.current_environment.galaxy.system_of_key(self.asteroid_site['system'])
        if self.asteroid_site['belt'] is None:
            return self.asteroid_site['seed'] in system.free_asteroids
        belt = system.get_orbit(float(self.asteroid_site['belt']))
        return AsteroidKey.from_ints(self.asteroid_site['key'].split()) in belt.relevant
    # endregion

    def icy_worlds(self) -> List[RockyWorld]:
        """The icy worlds of the planetary system of the issuer's planet: the planet and its moons."""
        from galaxies.rocky_world import RockyWorld
        planet = self.issuer_outpost.planet
        return [world for world in [planet, *planet.moons]
                if isinstance(world, RockyWorld) and world.surface_type is SurfaceType.ICE]

    def icy_stellar_worlds(self) -> List[RockyWorld]:
        """The icy worlds of the whole star's system: every planet and moon of it."""
        from galaxies.rocky_world import RockyWorld
        system = self.issuer_outpost.planet.parent_orbit.parent_stellar_system
        return [world for world in system.get_all_worlds()
                if isinstance(world, RockyWorld) and world.surface_type is SurfaceType.ICE]

    def reward_per_kg(self) -> float:
        """How far the water is: in the planet's system, else elsewhere in the star's system, else from an asteroid."""
        if self.icy_worlds():
            return DeliverWater.REWARD_PER_KG_PLANETARY_ICE
        if self.icy_stellar_worlds():
            return DeliverWater.REWARD_PER_KG_STELLAR_ICE
        return DeliverWater.REWARD_PER_KG_ASTEROID

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

    def warning(self) -> Optional[str]:
        """Without a scoop the water cannot be taken: a warning on the offer, before the long distance one."""
        import galaxies.people.player as player_module
        if not player_module.current_player.ship.has_scoop:
            return "Your ship has no scoop, so it cannot take raw water."
        return super().warning()

    def can_complete(self, player: Player) -> bool:
        return player.ship.cargo_hold.raw_water > 0.0

    def complete(self, player: Player) -> None:
        """Takes all the raw water from the hold, as the ore mission takes its ore: no time for the dockmaster."""
        self.delivered = player.ship.cargo_hold.raw_water
        player.ship.cargo_hold.raw_water = 0.0

    def shortfall(self, player: Player) -> str:
        return "You carry no raw water."

    def give_reward(self, player: Player) -> None:
        reputation_change: float = DeliverWater.MINIMUM_REWARD + self.reward_per_kg() * self.delivered

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

    def serialize(self) -> dict:
        return {**super().serialize(), 'asteroid_site': self.asteroid_site}

    @classmethod
    def _deserialize(cls, source: dict) -> DeliverWater:
        return DeliverWater(source['asteroid_site'], loaded=True, **Mission._common(source))
