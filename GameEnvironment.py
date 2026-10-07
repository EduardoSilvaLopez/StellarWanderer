import datetime
import logging
from typing import Optional
from Galaxies.Galaxy import Galaxy
from Galaxies.World import World

logger = logging.getLogger(__name__)

class GameEnvironment:
    EPOCH = datetime.datetime(700, 1, 1)

    def __init__(self, galactic_seed: int, date_time: datetime.datetime, saved_alterations: Optional[dict]) -> None:
        self.date_time = date_time
        if (saved_alterations): saved_alterations['date_time'] = date_time
        self.galaxy: Galaxy = Galaxy(galactic_seed, saved_alterations)
        self.nearest_world: World = None

    def generate_default(self) -> None:
        from Galaxies.StellarSystem import StellarSystem
        from Galaxies.Orbit import Orbit

        current_system: StellarSystem = self.galaxy.add_stellar_system(26000, 0, 0)
        current_orbit: Orbit = current_system.orbits[int(len(current_system.orbits) / 2)]
        current_orbit.add_world(0)
        self.nearest_world = current_orbit.worlds[0]
        logger.info(f"Initial planet's radius: {self.nearest_world.radius}")

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