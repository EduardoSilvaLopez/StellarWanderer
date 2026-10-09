import datetime
import logging
import math
from typing import Optional
from Galaxies.galaxy import Galaxy
from Galaxies.stellar_system import StellarSystem
from Galaxies.world import World
from Vector3 import Vector3

logger = logging.getLogger(__name__)

class GameEnvironment:
    EPOCH = datetime.datetime(700, 1, 1)

    NEAREST_WORLD_RECHECK_FRAMES = 30  # ~0.5s at 60 FPS; a real-frame throttle, not game-time (time_scale can run to 1,000,000x)
    NEAREST_WORLD_HYSTERESIS = 0.05    # a candidate must be >5% closer to replace the current nearest_world, to avoid flip-flop

    def __init__(self, galactic_seed: int, date_time: datetime.datetime, saved_alterations: Optional[dict]) -> None:
        self.date_time = date_time
        if (saved_alterations): saved_alterations['date_time'] = date_time
        self.galaxy: Galaxy = Galaxy(galactic_seed, saved_alterations)
        self.nearest_world: World = None
        self.nearest_system: StellarSystem = None
        self._nearest_world_recheck_countdown: int = 0

    def generate_default(self) -> None:
        from Galaxies.orbit import Orbit

        self.nearest_system = self.galaxy.add_stellar_system(26000, 0, 0)
        current_orbit: Orbit = self.nearest_system.orbits[int(len(self.nearest_system.orbits) / 2)]
        self.nearest_world = current_orbit.planets[0]
        logger.info(f"Initial planet's radius: {self.nearest_world.radius}")

    def refresh_nearest_world(self, player_position: Vector3) -> None:
        """Re-pick nearest_world from the current nearest_system's worlds. Throttled
        to once every NEAREST_WORLD_RECHECK_FRAMES calls (real frames, not game
        time). A candidate only replaces the current nearest_world if it's more
        than NEAREST_WORLD_HYSTERESIS closer, to avoid flip-flopping between two
        similarly-distant worlds. Call only while unbound — see
        Player.update_position_and_velocity."""
        self._nearest_world_recheck_countdown -= 1
        if self._nearest_world_recheck_countdown > 0:
            return
        self._nearest_world_recheck_countdown = GameEnvironment.NEAREST_WORLD_RECHECK_FRAMES

        current_distance = math.dist(player_position, self.nearest_world.calculate_stellar_position(self.date_time))
        for orbit in self.nearest_system.orbits:
            for world in orbit.planets:
                if world is self.nearest_world:
                    continue
                distance = math.dist(player_position, world.calculate_stellar_position(self.date_time))
                if distance < current_distance * (1 - GameEnvironment.NEAREST_WORLD_HYSTERESIS):
                    self.nearest_world = world
                    current_distance = distance

    @staticmethod
    def new_game(seed: int) -> None:
        '''Create a new game with the given seed, initializing GameEnvironment and Player singletons.

        Args:
            seed: The galactic seed for the new game (int)
        '''
        logger.info(f"Starting new game with seed: {seed}")

        # Create a new GameEnvironment with the given seed
        current_environment = GameEnvironment(seed, datetime.now())

        # Spawn player in the first world they encounter
        from Player import Player, current_player
        current_player = Player()
        current_player.spawn_in_environment(current_environment)

        logger.info("New game started")

current_environment: GameEnvironment = None