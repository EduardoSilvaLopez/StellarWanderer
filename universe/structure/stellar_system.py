from __future__ import annotations

import logging
import math
import random
from datetime import datetime
from typing import TYPE_CHECKING

import galaxies.constants
from galaxies.people import knowledge
from common.units import format_compact_distance
from galaxies import seeds
from galaxies.asteroid import Asteroid, AsteroidKey
from galaxies.asteroid_belt import AsteroidBelt
from galaxies.body import Body
from galaxies.orbit import Orbit
from galaxies.orbit_layout import OrbitKind, OrbitLayout
from galaxies.outpost import Outpost
from galaxies.portals.portal import Portal
from galaxies.portals.portal_base import PortalBase
from galaxies.politics import political_entity
from galaxies.rocky_world import RockyWorld
from galaxies.star import Star
from galaxies.world import World

if TYPE_CHECKING:
    from galaxies.galaxy import Galaxy
    from galaxies.politics.expansion_history import SystemHistory

logger = logging.getLogger(__name__)

class StellarSystem:

    # region Generation
    def __init__(self, parent_galaxy: Galaxy, star: Star, saved_alterations: dict) -> None:
        ''' Using galactic coordinates here, in ly: the system is where its star is. The star is given by the galaxy.'''
        self.parent_galaxy: Galaxy = parent_galaxy
        self.x, self.y, self.z = star.position
        self.seed: int = seeds.derive(star.seed, 'system')
        my_random: random.Random = random.Random(self.seed)

        # Only the initial star has a history so far; it gives the system its entity.
        self.history: SystemHistory | None = parent_galaxy.initial_history \
            if star.position == galaxies.constants.INITIAL_STAR_POSITION else None
        self.political_entity: political_entity.PoliticalEntity | None = \
            self.history.entity if self.history is not None else None
        # When the system was colonised, which is also when its portal base was founded.
        self.founded_at: datetime | None = self.history.founded_at if self.history is not None else None
        self.star: Star = star  # the system's star, as a body ships can navigate to
        self.star.attach_to(self)
        self.name: str = self.star.name + " System"
        knowledge.current_knowledge.learn_system(self.get_alterations_key())

        self.is_altered: bool = False
        self.saved_alterations: dict | None = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            own_alterations: dict = saved_alterations[alterations_key]
            own_alterations['date_time'] = saved_alterations['date_time']
            self.saved_alterations = own_alterations
        self.star.hidden = bool((self.saved_alterations or {}).get('star', {}).get('hidden', False))
        # A system has a portal base, and the Portal it protects, only if its history says so (see _place_settlements):
        # the pilot may arrive by hand to one that has neither.
        self.portal_base: PortalBase | None = None
        self.portal: Portal | None = None

        self.orbits: list[Orbit] = self._generate_orbits(my_random)

        # The free-living asteroids that matter (a mission's target), by the seed of the offer they come from. Saved by
        # that seed alone: each is rebuilt from it (see Asteroid.free_living).
        self.free_asteroids: dict[int, Asteroid] = {}
        for offer_seed, saved in (self.saved_alterations or {}).get('free_asteroids', {}).items():
            self.free_asteroids[int(offer_seed)] = Asteroid.free_living(self, int(offer_seed)).apply_alterations(saved)
        # The free-living asteroids taken whole by a scoop: gone for good (see Asteroid.consume).
        self.consumed_free: set[int] = {int(offer_seed) for offer_seed in
                                        (self.saved_alterations or {}).get('consumed_free', [])}

        self._place_settlements()

    def _place_settlements(self) -> None:
        """Gives the system the settlements of its history: the first is the portal base (with the Portal it protects),
        each other one an outpost on a rocky world (a planet or a moon) other than the initial moon. The first outpost
        goes to the initial planet, so the pilot has one near; each of the rest is drawn from a seed of its own, so its
        world does not change when the history grows. A system without a history has no settlement at all. The base is
        made after the system's saved state, which holds its visits and handling."""
        if self.history is None:
            return
        settlements: list[list[datetime]] = self.history.settlements
        self.portal_base = PortalBase(self, settlements[0], (self.saved_alterations or {}).get('portal_base'))
        self.portal = Portal(self.portal_base)  # nothing about it is saved
        rocky_worlds = [world for world in self.get_all_worlds() if isinstance(world, RockyWorld)]
        initial_planet = next((world for world in rocky_worlds if world.is_initial_planet()), None)
        initial_moon = initial_planet.moons[0] if initial_planet is not None and initial_planet.moons else None
        eligible = [world for world in rocky_worlds if world is not initial_moon]
        now = self.parent_galaxy.history.now
        for number, dates in enumerate(settlements[1:], start=1):
            if dates[0] > now:  # not founded yet: the history knows it, the system does not
                continue
            if number == 1 and initial_planet is not None:
                world = initial_planet
            else:
                world = random.Random(seeds.derive(self.seed, 'settlement', number)).choice(eligible)
            outpost = Outpost(world, (world.saved_alterations or {}).get('outposts'), dates)
            world.outposts[outpost.get_alterations_key()] = outpost  # May overwrite: the key is the place.

    def consume_free_asteroid(self, offer_seed: int) -> None:
        """The scoop has taken the free-living asteroid of the offer whole: it is gone, and the system is altered."""
        self.free_asteroids.pop(offer_seed, None)
        self.consumed_free.add(offer_seed)
        self.set_altered()

    def forget_free_asteroid(self, offer_seed: int) -> None:
        """Forgets a kept free-living asteroid: it is no longer in the system, and it is not made again."""
        self.free_asteroids.pop(offer_seed, None)

    def promote_free_asteroid(self, offer_seed: int) -> Asteroid:
        """The free-living asteroid of the offer's seed as a kept one (made if it was not); the system is marked as
        altered."""
        asteroid = self.free_asteroids.get(offer_seed)
        if asteroid is None:
            asteroid = Asteroid.free_living(self, offer_seed)
            self.free_asteroids[offer_seed] = asteroid
            self.set_altered()
        if asteroid.hidden:  # a mission asks for it: it is shown
            asteroid.set_hidden(False)
        return asteroid

    def _generate_orbits(self, my_random: random.Random) -> list[Orbit]:
        """The orbits of the system, nearest first and numbered 1.0, 2.0...: earthlike planets, asteroid belts and
        jovian planets, at distances that follow the star's luminosity (see orbit_layout.py); none for a star of type O.
        The initial system always has an earthlike planet in orbit `OrbitLayout.INITIAL_ORBIT_NUMBER`. The layout is
        logged."""
        is_initial_system = self.star.position == galaxies.constants.INITIAL_STAR_POSITION
        layout = OrbitLayout.generate(self.star, my_random, is_initial_system)
        orbits = [
            (AsteroidBelt if plan.kind is OrbitKind.ASTEROID_BELT else Orbit)(
                self, plan.number, plan.kind, plan.distance, self.saved_alterations)
            for plan in layout.plans
        ]
        self._log_orbits(layout, orbits)
        return orbits

    def _log_orbits(self, layout: OrbitLayout, orbits: list[Orbit]) -> None:
        scales = layout.scales
        logger.info(
            f"Orbits of {self.name}: {len(orbits)} orbits. Star {self.star.type.name}: luminosity "
            f"{scales.luminosity:.3g} W, mass {scales.mass:.3g} kg. "
            f"Inner edge {format_compact_distance(scales.inner_edge)}, "
            f"snow line {format_compact_distance(scales.snow_line)}."
        )
        if layout.attempts > 1:
            logger.info(f" - Initial system: {layout.attempts} layouts drawn for the initial planet"
                        + (" (none did: the fixed layout was used)" if layout.needed_fallback else ""))
        for orbit in orbits:
            period = math.tau * math.sqrt(
                orbit.distance_from_star ** 3 / (World.GRAVITATIONAL_CONSTANT * self.star.mass)
            )
            logger.info(
                f" - Orbit {orbit.number}: {orbit.kind.value}, {format_compact_distance(orbit.distance_from_star)}, "
                f"period {period:.3g} s"
            )
    # endregion

    # region Bodies
    def get_orbit(self, number: float) -> Orbit | None:
        return next((orbit for orbit in self.orbits if orbit.number == number), None)

    def get_all_bodies(self) -> list[Body]:
        """The star first, then the portal base (if it has one), then every world (each planet before its moons), then the asteroids of
        the ongoing missions."""
        base = [] if self.portal_base is None else [self.portal_base]
        return [self.star] + base + self.get_all_worlds() + self.mission_asteroids()

    def mission_asteroids(self) -> list[Asteroid]:
        """The asteroids of the pilot's accepted, not yet finished scan missions whose target is in this system. They
        are shown, and can be targeted and fixed to."""
        # Local: the player imports the missions, which import this package.
        import galaxies.people.player as player_module
        from galaxies.missions import OPEN, DeliverWater, ScanAsteroid
        player = player_module.current_player
        if player is None:
            return []
        key = self.get_alterations_key()
        asteroids = [mission.asteroid() for mission in player.missions
                     if isinstance(mission, (ScanAsteroid, DeliverWater)) and mission.status == OPEN
                     and mission.asteroid_site is not None and mission.asteroid_site['system'] == key]
        return [asteroid for asteroid in asteroids if asteroid is not None]

    def asteroid_from_site(self, site: dict) -> Asteroid:
        """The asteroid that `Asteroid.site` describes, in this system: the kept one if it is kept (a belt's relevant
        one, or a free-living one of `free_asteroids`), else one made from the site. The same asteroid as before the
        save."""
        if site['belt'] is None:
            return self.free_asteroids.get(site['seed']) or Asteroid.free_living(self, site['seed'])
        belt = self.get_orbit(float(site['belt']))
        if not isinstance(belt, AsteroidBelt):
            raise ValueError(f"No asteroid belt at orbit {site['belt']} of {self.name}")
        key = AsteroidKey.from_ints(site['key'].split())
        return belt.relevant.get(key) or belt.build(key)

    def is_mission_target(self, asteroid: Asteroid) -> bool:
        """Whether an open mission of the pilot is about this asteroid: it can be neither hidden nor forgotten then."""
        # Local: as mission_asteroids, the missions import this package.
        import galaxies.people.player as player_module
        from galaxies.missions import OPEN, DeliverWater, ScanAsteroid
        player = player_module.current_player
        if player is None:
            return False
        key = self.get_alterations_key()
        site = asteroid.site()
        return any(isinstance(mission, (ScanAsteroid, DeliverWater)) and mission.status == OPEN
                   and mission.asteroid_site is not None and mission.asteroid_site['system'] == key
                   and all(mission.asteroid_site[name] == value for name, value in site.items())
                   for mission in player.missions)

    def promoted_asteroids(self) -> list[Asteroid]:
        """The asteroids that matter in this system, whatever became of their missions: the relevant ones of its belts,
        then the free-living ones."""
        from galaxies.asteroid_belt import AsteroidBelt
        result = [asteroid for orbit in self.orbits if isinstance(orbit, AsteroidBelt)
                  for asteroid in orbit.relevant.values()]
        return result + list(self.free_asteroids.values())

    def settlements(self) -> list:
        """Every settlement of the system: its outposts, world by world, then the portal base if it has one."""
        outposts = [outpost for world in self.get_all_worlds() for outpost in world.outposts.values()]
        return outposts + ([] if self.portal_base is None else [self.portal_base])

    def get_all_worlds(self) -> list[World]:
        result: list[World] = []
        for orbit in self.orbits:
            for planet in orbit.planets:
                result.append(planet)
                result.extend(planet.moons)
        return result
    # endregion

    # region Alterations
    def set_altered(self) -> StellarSystem:
        self.is_altered = True
        self.parent_galaxy.set_altered()
        return self

    def get_alterations_key(self) -> str:
        '''The integer cell of the star, so that the key is the same whatever the float position.'''
        return " ".join(str(c) for c in self.star.cell)

    def get_alterations(self) -> dict | None:
        alterations = {}
        if self.is_altered:
            if self.star.hidden:
                alterations['star'] = {'hidden': True}
            base_alterations = self.portal_base.get_alterations() if self.portal_base is not None else None
            if base_alterations:
                alterations['portal_base'] = base_alterations
            for orbit in self.orbits:
                if orbit.is_altered:
                    orbit_alterations: dict | None = orbit.get_alterations()
                    if orbit_alterations:
                        alterations[orbit.get_alterations_key()] = orbit_alterations
            if self.free_asteroids:
                alterations['free_asteroids'] = {str(offer_seed): asteroid.get_alterations()
                                                 for offer_seed, asteroid in self.free_asteroids.items()}
            if self.consumed_free:
                alterations['consumed_free'] = sorted(self.consumed_free)
        if not alterations:
            return None
        return alterations
    # endregion

    def markdown(self) -> str:
        '''Markdown of the system itself: its name and place. Its bodies have their own entries (see the knowledge
        dialog).'''
        return (
            f"## {self.name} ({self.political_entity.name if self.political_entity else ''})\n"
            f"* Galactic coordinates ({self.x}ly, {self.y}ly, {self.z}ly )\n"
        )
