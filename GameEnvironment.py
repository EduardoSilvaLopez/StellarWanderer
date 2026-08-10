import random

class GameEnvironment:
    curEnv = None
    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000

    def __init__(self, galacticSeed):
        self.galacticSeed = galacticSeed
        self.galacticRandom = random.Random(galacticSeed)
        self.solarRandom = random.Random(self.galacticRandom.randint(1, 1000000000))
        self.orbitalRandom = random.Random(self.solarRandom.randint(1, 1000000000))
        self.planetRandom = random.Random(self.orbitalRandom.randint(1, 1000000000))
        self.planetRadius = self.planetRandom.gauss(GameEnvironment.EARTHLIKE_RADIUS_AVERAGE, GameEnvironment.EARTHLIKE_RADIUS_SIGMA)
        while self.planetRadius <= 0:
            self.planetRadius = self.planetRandom.gauss(GameEnvironment.EARTHLIKE_RADIUS_AVERAGE, GameEnvironment.EARTHLIKE_RADIUS_SIGMA)
        print("Initial planet's radius: " + str(self.planetRadius))
        curEnv = self
