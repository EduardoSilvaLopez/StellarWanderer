from Galaxies.Galaxy import Galaxy

class GameEnvironment:
    singleton = None

    def __init__(self, galactic_seed):
        self.galaxy = Galaxy(galactic_seed).generate()
        self.current_world = self.galaxy\
            .add_stellar_system(0, 0, 0)\
            .add_orbit(1000000)\
            .add_world(0)
        print("Initial planet's radius: " + str(self.current_world.radius))
        self.current_world.add_Km2(0, 0) # by default
        GameEnvironment.singleton = self
