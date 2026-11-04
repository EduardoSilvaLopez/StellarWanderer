import datetime
import logging
import math
from typing import Optional
from galaxies.body import Body
from galaxies.constants import EPOCH as EPOCH_DATE, INITIAL_STAR_POSITION
from galaxies.galaxy import Galaxy
from galaxies.game_clock import GameClock
from galaxies.orbit_layout import OrbitLayout
from galaxies.stellar_system import StellarSystem
from galaxies.world import World
from common.vector3 import Vector3

logger = logging.getLogger(__name__)


class GameEnvironment:
    EPOCH = EPOCH_DATE

    def __init__(self, galactic_seed: int, date_time: datetime.datetime, galaxy_alterations: Optional[dict],
                 people_alterations: Optional[dict]) -> None:
        self.clock = GameClock(date_time)
        if galaxy_alterations:
            galaxy_alterations['date_time'] = date_time
        self.galaxy: Galaxy = Galaxy(galactic_seed, galaxy_alterations, date_time)
        # The body whose fixed zone the ship is in (the nearest one, if several), or None outside every fixed zone.
        self.fixed_body: Optional[Body] = None
        # Always set: the body the instruments show and the braking is measured against. While unbound the Tab key
        # moves it (cycle_targeted_body), fixed or not; it follows the fixed body only on entering a zone from outside
        # all of them, while the pilot has not chosen another one.
        self.targeted_body: Body = None
        # The body the ship was last fixed to: what the savefile stores as the ship's body.
        self.last_fixed_body: Body = None
        self.nearest_system: StellarSystem = None
        self.persons: dict = people_alterations if people_alterations else {}

    @property
    def date_time(self) -> datetime.datetime:
        """The game's date, read from the clock, which is the one that moves (see GameClock)."""
        return self.clock.now

    def generate_default(self) -> None:
        self.nearest_system = self.galaxy.add_stellar_system(self.galaxy.fixed_star_at(INITIAL_STAR_POSITION))
        current_orbit = self.nearest_system.get_orbit(float(OrbitLayout.INITIAL_ORBIT_NUMBER))
        self.fixed_body = self.targeted_body = self.last_fixed_body = current_orbit.planets[0].moons[0]
        logger.info(f"Initial world's radius: {self.fixed_body.radius}")

    @property
    def fixed_world(self) -> Optional[World]:
        """The fixed body when it is a world, else None (the star, or outside every fixed zone). For the code that needs
        a surface: bound mode, the scanner, the mines, the world map. Everything else asks for targeted_body."""
        return self.fixed_body if self.fixed_body is not None and self.fixed_body.is_world else None

    def refresh_fixed_body(self, player_position: Vector3, keep_target: bool = False) -> None:
        """Pick fixed_body for this frame: the body nearest to the ship (distance from its centre) whose fixed zone
        holds it, or None when no fixed zone does. The target follows the body the ship becomes fixed on only when the
        ship enters a zone from outside all of them, while the target is still the last fixed body: it is then the
        default, not a choice of the pilot. From one zone into another, and with `keep_target` (the autopilot flies to
        it), it stays. last_fixed_body records the body while fixed. A hidden body has no fixed zone. Call only while
        unbound, see Navigation.update_position_and_velocity."""
        from spaceships.navigation import Navigation  # local: navigation imports this module

        fixed: Optional[Body] = None
        fixed_distance = math.inf
        for body in self.nearest_system.get_all_bodies():
            if not body.is_shown:
                continue
            distance = math.dist(player_position, body.calculate_stellar_position(self.date_time))
            if distance < Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius and distance < fixed_distance:
                fixed, fixed_distance = body, distance
        previous = self.fixed_body
        self.fixed_body = fixed
        if fixed is not None:
            following = self.targeted_body is self.last_fixed_body
            self.last_fixed_body = fixed
            if previous is None and following and not keep_target:
                self.targeted_body = fixed

    def bodies_by_distance(self, player_position: Vector3) -> list[Body]:
        """The shown bodies of nearest_system sorted by distance from the ship, the star included: the order the Tab key
        goes through. Hidden ones are not in it."""
        return sorted(
            (body for body in self.nearest_system.get_all_bodies() if body.is_shown),
            key=lambda body: math.dist(player_position, body.calculate_stellar_position(self.date_time)),
        )

    def target_index(self, player_position: Vector3) -> int:
        """The place of targeted_body in bodies_by_distance, saved in the savefile; -1 if it is not there."""
        bodies = self.bodies_by_distance(player_position)
        return bodies.index(self.targeted_body) if self.targeted_body in bodies else -1

    def untarget(self, body: Body) -> None:
        """Takes the target off `body` when it is the targeted one (it was hidden or forgotten): the star, or else the
        portal base, takes its place when it is shown."""
        if self.targeted_body is not body:
            return
        for candidate in (self.nearest_system.star, self.nearest_system.portal_base):
            if candidate is not None and candidate.is_shown:
                self.targeted_body = candidate
                return

    def cycle_targeted_body(self, step: int, player_position: Vector3) -> None:
        """Moves targeted_body `step` places (+1 or -1) through bodies_by_distance, wrapping around. The caller only
        calls it while unbound: fixed on a body, the pilot may still pick any other one as the target."""
        bodies = self.bodies_by_distance(player_position)
        if not bodies:  # all of them hidden
            return
        index = self.target_index(player_position)
        self.targeted_body = bodies[(index + step) % len(bodies)]


current_environment: GameEnvironment = None
