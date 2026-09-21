import datetime
from Galaxies.Galaxy import Galaxy

class GameEnvironment:
    EPOCH = datetime.datetime(500, 1, 1)

    singleton = None

    def __init__(self, galactic_seed, date_time, saved_alterations):
        self.date_time = date_time
        if (saved_alterations): saved_alterations['date_time'] = date_time
        self.galaxy = Galaxy(galactic_seed, saved_alterations)
        self.current_world = None
        GameEnvironment.singleton = self

    def generate_default(self):
        self.current_world = self.galaxy\
            .add_stellar_system(26000, 0, 0)\
            .add_orbit(150000000000)\
            .add_world(180)
        print("Initial planet's radius: " + str(self.current_world.radius))

    @staticmethod
    def new_game(seed):
        '''Create a new game with the given seed, initializing GameEnvironment and Player singletons.

        Args:
            seed: The galactic seed for the new game (int)
        '''
        print(f"Starting new game with seed: {seed}")

        # Create a new GameEnvironment with the given seed
        environment = GameEnvironment(seed, datetime.now())
        GameEnvironment.singleton = environment

        # Spawn player in the first world they encounter
        player = Player()
        player.spawn_in_environment(environment)
        Player.singleton = player

        print("New game started")


