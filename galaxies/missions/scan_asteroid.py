"""Scan an asteroid somewhere in the system and come back with the information.

The target is one of two kinds, chosen when the offer is made, from the mission's seed. In a system with a belt it is,
for the most part, a cosmetic asteroid of that belt (an `AsteroidKey`: see asteroid_belt.py) of a medium or big size;
the pilot's taking the mission promotes it (`accept`), so an offer nobody takes leaves the belt as it was. For
FREE_LIVING_CHANCE of the offers, and always in a system without a belt, it is a free-living asteroid
(`Asteroid.free_living`), rebuilt from the system and the mission's seed; taking the mission keeps it in the system
(`StellarSystem.promote_free_asteroid`), which saves its seed. The texts name only the asteroid. The pilot scans it
with the scanner beam (see `Scanner`): the scan is kept by the asteroid (`Asteroid.scan_progress`), and the mission can
be completed, back at the outpost, when it is done.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from galaxies.seeds import of_text

from .mission import DONE, FAILED, OPEN, Mission, register
from galaxies.missions.terms import Terms
from galaxies.settlement_kind import SettlementKind

if TYPE_CHECKING:
    from galaxies.asteroid import Asteroid
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player

logger = logging.getLogger(__name__)

@register
class ScanAsteroid(Mission):
    """Scan an asteroid, then come back."""
    KIND = 'scan_asteroid'
    # The numbers that depend on the kind of settlement that asks; the outposts' are tuned, and the portal base's
    # start at a frequency of 0 (no offers yet).
    TERMS = {
        SettlementKind.OUTPOST: Terms(
            frequency=0.03,
            taken_by_others=0.01,
            deadline_days_min=45,
            deadline_days_max=90,
            reward=50.0,
            failure_penalty=-2.0
            ),
        SettlementKind.PORTAL_BASE: Terms(
            frequency=0.06,
            taken_by_others=0.01,
            deadline_days_min=45,
            deadline_days_max=90,
            reward=50.0,
            failure_penalty=-2.0
            ),
    }
    REPUTATION_BELT_MEAN_DISTANCE = 4.0e11  # Earh belt taken as reference, for the reward.
    FREE_LIVING_CHANCE = 0.10  # Of the offers in a system with a belt: the target belongs to no belt

    def __init__(
            self, asteroid_site: dict | None = None,
            **common: Any) -> None:
        super().__init__(**common)

        # Drawn in this order every time, from the seed.
        days = self.my_random.randint(self.terms.deadline_days_min, self.terms.deadline_days_max)
        rolls = [self.my_random.random() for _ in range(days)]
        moment = self.my_random.random()

        taken_day = next(
            (index for index, roll in enumerate(rolls) if roll < self.terms.taken_by_others),
            None
            )
        self.taken_by_others_at = None if taken_day is None else self.created_at + timedelta(days=taken_day + moment)


        # Only drawn for a new offer; a loaded mission keeps what it was given.
        self.asteroid_site: dict | None = asteroid_site
        if self.asteroid_site is None:
            self.asteroid_site = self._choose_asteroid_site()
        self._asteroid: Asteroid | None = None  # made when needed, not saved

    # region The asteroid
    def _choose_asteroid_site(self) -> dict | None:
        """The target, from the mission's seed: None if the belt has no asteroid in the place drawn (no offer then)."""
        from galaxies.asteroid import Asteroid  # local: these modules need the galaxy package to load first
        from galaxies.asteroid_belt import AsteroidBelt
        system = self.issuer_settlement.stellar_system
        belts = [orbit for orbit in system.orbits if isinstance(orbit, AsteroidBelt)]
        is_free_living = not belts or self.my_random.random() < ScanAsteroid.FREE_LIVING_CHANCE
        tier = self.my_random.choices(
            [tier for tier, _ in Asteroid.FREE_TIERS], [weight for _, weight in Asteroid.FREE_TIERS]
            )[0]
        site = {'system': system.get_alterations_key(), 'belt': None, 'key': None, 'seed': None}
        if is_free_living:
            site['seed'] = self.seed
            return site
        belt = self.my_random.choice(belts)
        key = belt.random_key(self.my_random, tier, belt.time_in_epoch(self.created_at)[0])
        if key is None:
            return None
        site['belt'] = int(belt.number)
        site['key'] = str(key)
        return site

    def asteroid(self) -> Asteroid:
        """The target. For an asteroid of a belt, the promoted one if it is, else one made for the moment
        (the belt is not changed)."""
        if self._asteroid is None:
            import game_environment as gem
            from galaxies.asteroid import Asteroid, AsteroidKey
            system = gem.current_environment.galaxy.system_of_key(self.asteroid_site['system'])
            if self.asteroid_site['belt'] is None:
                self._asteroid = system.free_asteroids.get(self.asteroid_site['seed']) \
                    or Asteroid.free_living(system, self.asteroid_site['seed'])
            else:
                belt = system.get_orbit(float(self.asteroid_site['belt']))
                key = AsteroidKey.from_ints(self.asteroid_site['key'].split())
                self._asteroid = belt.relevant.get(key) or belt.build(key)
        return self._asteroid
    # endregion

    # region Offer
    @classmethod
    def offer(cls, day: datetime, outpost: Settlement, chance: random.Random) -> ScanAsteroid | None:
        mission = cls.generate(day, outpost)
        if mission.asteroid_site is None:
            return None  # no asteroid could be found for it
        return mission

    @staticmethod
    def generate(created_at: datetime, outpost: Settlement) -> ScanAsteroid:
        """The offer made on the day of `created_at`: its seed is the outpost and the day."""
        seed = of_text(f"{outpost.full_keys()} {ScanAsteroid.KIND} {created_at.date().isoformat()}")
        days = random.Random(seed).randint(ScanAsteroid.terms_at(outpost.kind).deadline_days_min,
                                       ScanAsteroid.terms_at(outpost.kind).deadline_days_max)
             # the first draw of the seed, as in __init__
        return ScanAsteroid(
            seed=seed,
            issuer=outpost.full_keys(),
            created_at=created_at,
            deadline=created_at + timedelta(days=days),
            destination=outpost.full_keys(),
            issuer_kind=outpost.kind,
            destination_kind=outpost.kind,
        )
    # endregion

    # region The mission
    def accept(self, now: datetime) -> None:
        """The pilot takes the offer: the asteroid is promoted (kept and saved: by its belt, or by its system if it
        is free-living), so it is the one the mission asks for."""
        super().accept(now)
        import game_environment as gem
        from galaxies.asteroid import AsteroidKey
        system = gem.current_environment.galaxy.system_of_key(self.asteroid_site['system'])
        if self.asteroid_site['belt'] is None:
            self._asteroid = system.promote_free_asteroid(self.asteroid_site['seed'])
            return
        belt = system.get_orbit(float(self.asteroid_site['belt']))
        self._asteroid = belt.promote(AsteroidKey.from_ints(self.asteroid_site['key'].split()))

    def progress(self) -> str:
        if self.accepted_at is None:
            return ''
        if self.status == DONE:  # the asteroid may be forgotten by now: the history keeps what was done
            return f"The asteroid {self.asteroid().name} was scanned."
        if self.status == FAILED:
            return f"The asteroid {self.asteroid().name} was not scanned in time."
        if self.asteroid().scan_progress >= 1.0:
            return (f"The asteroid {self.asteroid().name} is scanned: bring the results to "
                    f"{self.issuer_settlement.name}.")
        return f"The asteroid {self.asteroid().name} is scanned {self.asteroid().scan_progress:.0%}."

    def target_body(self) -> Asteroid:
        return self.asteroid()

    def title(self) -> str:
        return f"Scan the asteroid {self.asteroid().name}."

    def description(self) -> str:
        return (
            f"We have found an interesting asteroid, {self.asteroid().name}."
            f"\n\nWe need somebody to take the risk and go to scan it."
            f"\n\nMake sure you have the experience and autonomy for this mission."
            f"\n\nBring the results to here, at {self.issuer_settlement.address()}."
            )

    def can_forget(self, player: Player) -> bool:
        """Once the mission is over, its asteroid can be forgotten while it is still kept by its system or belt and no
        open mission asks for it."""
        if self.status == OPEN or any(
                isinstance(other, ScanAsteroid) and other.status == OPEN and other.asteroid_site == self.asteroid_site
                for other in player.missions):
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

    def can_complete(self, player: Player) -> bool:
        return self.asteroid().scan_progress >= 1.0

    def complete(self, player: Player) -> None:
        """Nothing is taken from the player: the scan is what was asked."""

    def shortfall(self, player: Player) -> str:
        return f"You have not scanned the asteroid {self.asteroid().name} yet."

    def give_reward(self, player: Player) -> None:
        import game_environment as gem
        reputation_change: float = self.terms.reward
        reputation_change *= self.asteroid().semi_major_axis / ScanAsteroid.REPUTATION_BELT_MEAN_DISTANCE
        reputation_change *= (gem.current_environment.date_time - self.created_at).total_seconds() \
                            / (self.deadline - self.created_at).total_seconds()
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION COMPLETE: asteroid scanned. "
                    f"Reputation +{reputation_change} = {player.those_who_share.reputation}"
                    )

    def reward_text(self, player: Player) -> str:
        return (
            f"Thank you for taking the risk, Pilot {player.surname},"
            f" knowledge about this asteroid will help the Community."
            )

    def fail(self, player: Player) -> None:
        reputation_change: float = self.terms.failure_penalty
        player.those_who_share.reputation += reputation_change
        logger.info(f"MISSION FAILED: asteroid not scanned. "
                    f"Reputation {reputation_change} = {player.those_who_share.reputation}"
                    )
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {**super().serialize(), 'asteroid_site': self.asteroid_site}

    @classmethod
    def _deserialize(cls, source: dict) -> ScanAsteroid:
        return ScanAsteroid(source['asteroid_site'], **Mission._common(source))
    # endregion
