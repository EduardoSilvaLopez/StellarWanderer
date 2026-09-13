from Galaxies.StellarSystem import StellarSystem

class Galaxy():

    def __init__(self, seeds_delta):
        self.seed = seeds_delta # The galaxy's seed is just the seed_delta from the user.
        self.stellar_systems = []
        self.is_altered = False

    def set_altered(self):
        self.is_altered = True

    def add_stellar_system(self, x, y, z):
        new_system = StellarSystem(self, x, y, z)
        self.stellar_systems.append(new_system)
        return new_system