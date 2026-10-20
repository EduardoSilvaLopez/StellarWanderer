import datetime
import logging
import math
from typing import Optional
from galaxies.body import Body
from galaxies.constants import INITIAL_STAR_POSITION
from galaxies.galaxy import Galaxy
from galaxies.orbit_layout import OrbitLayout
from galaxies.stellar_system import StellarSystem
from galaxies.world import World
from common.vector3 import Vector3

logger = logging.getLogger(__name__)


class GameEnvironment:
    EPOCH = datetime.datetime(700, 1, 1)

    def __init__(self, galactic_seed: float, date_time: datetime.datetime, galaxy_alterations: Optional[dict], people_alterations: Optional[dict]) -> None:
        self.date_time = date_time
        if galaxy_alterations:
            galaxy_alterations['date_time'] = date_time
        self.galaxy: Galaxy = Galaxy(galactic_seed, galaxy_alterations)
        # The body whose fixed zone the ship is in (the nearest one, if several), or None outside every fixed zone.
        self.fixed_body: Optional[Body] = None
        # Always set. The fixed body while the ship is in a fixed zone; once it leaves the last one, the body it was
        # fixed on until then, unless the player has cycled to another one (cycle_targeted_body).
        self.targeted_body: Body = None
        # The body the ship was last fixed to: what the savefile stores as the ship's body.
        self.last_fixed_body: Body = None
        self.nearest_system: StellarSystem = None
        self.persons: dict = people_alterations if people_alterations else {}

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

    def refresh_fixed_body(self, player_position: Vector3) -> None:
        """Pick fixed_body for this frame: the body nearest to the ship (distance from its centre) whose fixed zone holds
        it, or None when no fixed zone does. While fixed, targeted_body follows it, and last_fixed_body records it.
        Call only while unbound, see Navigation.update_position_and_velocity."""
        from spaceships.navigation import Navigation  # local: navigation imports this module

        fixed: Optional[Body] = None
        fixed_distance = math.inf
        for body in self.nearest_system.get_all_bodies():
            distance = math.dist(player_position, body.calculate_stellar_position(self.date_time))
            if distance < Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius and distance < fixed_distance:
                fixed, fixed_distance = body, distance
        self.fixed_body = fixed
        if fixed is not None:
            self.targeted_body = fixed
            self.last_fixed_body = fixed

    def cycle_targeted_body(self, step: int, player_position: Vector3) -> None:
        """Moves targeted_body `step` places (+1 or -1) through the bodies of nearest_system, sorted by distance from the
        ship, the star included, wrapping around. Only outside every fixed zone: while fixed, the target is the fixed body."""
        if self.fixed_body is not None:
            return
        bodies = sorted(
            self.nearest_system.get_all_bodies(),
            key=lambda body: math.dist(player_position, body.calculate_stellar_position(self.date_time)),
        )
        index = bodies.index(self.targeted_body) if self.targeted_body in bodies else -1
        self.targeted_body = bodies[(index + step) % len(bodies)]


current_environment: GameEnvironment = None
