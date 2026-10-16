import datetime
import logging
import math
from typing import Optional
from common.game_logging import reset_people_almanack
from galaxies.body import Body
from galaxies.galaxy import Galaxy
from galaxies.stellar_system import StellarSystem
from galaxies.world import World
from common.vector3 import Vector3

logger = logging.getLogger(__name__)


class GameEnvironment:
    EPOCH = datetime.datetime(700, 1, 1)

    NEAREST_BODY_RECHECK_FRAMES = 30  # ~0.5s at 60 FPS; a real-frame throttle, not game-time (time_scale can run to 1,000,000x)
    NEAREST_BODY_HYSTERESIS = 0.05  # a candidate must be >5% closer to replace the current nearest_body, to avoid flip-flop

    def __init__(self, galactic_seed: float, date_time: datetime.datetime, galaxy_alterations: Optional[dict], people_alterations: Optional[dict]) -> None:
        reset_people_almanack()  # a new environment is a new game or a load: the people will be written as they are created
        self.date_time = date_time
        if galaxy_alterations:
            galaxy_alterations['date_time'] = date_time
        self.galaxy: Galaxy = Galaxy(galactic_seed, galaxy_alterations)
        self.nearest_body: Body = None  # a world or the star of nearest_system
        self.nearest_system: StellarSystem = None
        self._nearest_body_recheck_countdown: int = 0
        self.persons: dict = people_alterations if people_alterations else {}

    def generate_default(self) -> None:
        from galaxies.orbit import Orbit

        self.nearest_system = self.galaxy.add_stellar_system(26000.0, 0.0, 0.0)
        current_orbit: Orbit = self.nearest_system.get_orbit(3.0)
        self.nearest_body = current_orbit.planets[0].moons[0]
        logger.info(f"Initial world's radius: {self.nearest_body.radius}")

    @property
    def nearest_world(self) -> Optional[World]:
        """The nearest body when it is a world, else None (the star). For the code that needs a surface: bound mode,
        the scanner, the mines, the world map. Everything else asks for nearest_body."""
        return self.nearest_body if self.nearest_body is not None and self.nearest_body.is_world else None

    def refresh_nearest_body(self, player_position: Vector3) -> None:
        """Re-pick nearest_body from the star and the worlds of the current nearest_system. Throttled
        to once every NEAREST_BODY_RECHECK_FRAMES calls (real frames, not game
        time). A candidate only replaces the current nearest_body if it's more
        than NEAREST_BODY_HYSTERESIS closer (distance to the centre), to avoid flip-flopping between two
        similarly-distant bodies. Call only while unbound — see
        Navigation.update_position_and_velocity."""
        self._nearest_body_recheck_countdown -= 1
        if self._nearest_body_recheck_countdown > 0:
            return
        self._nearest_body_recheck_countdown = GameEnvironment.NEAREST_BODY_RECHECK_FRAMES

        current_distance = math.dist(player_position, self.nearest_body.calculate_stellar_position(self.date_time))
        for body in self.nearest_system.get_all_bodies():
            if body is self.nearest_body:
                continue
            distance = math.dist(player_position, body.calculate_stellar_position(self.date_time))
            if distance < current_distance * (1 - GameEnvironment.NEAREST_BODY_HYSTERESIS):
                self.nearest_body = body
                current_distance = distance


current_environment: GameEnvironment = None
