import datetime
from Galaxies.Galaxy import Galaxy

class GameEnvironment:
    EPOCH = datetime.datetime(500, 1, 1)

    singleton = None

    def __init__(self, galactic_seed, saved_alterations):
        self.date_time = datetime.datetime(500, 1, 1)  # Default starting date and time
        self.galaxy = Galaxy(galactic_seed, saved_alterations)
        self.current_world = None
        GameEnvironment.singleton = self

    def generate_default(self):
        self.current_world = self.galaxy\
            .add_stellar_system(26000, 0, 0)\
            .add_orbit(150000000000)\
            .add_world(180)
        print("Initial planet's radius: " + str(self.current_world.radius))
        self.current_world.add_Km2(0, 0) # by default
