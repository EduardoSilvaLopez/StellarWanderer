import random

class Rock:
    def __init__(self, parent_chunk, seed):
        self.parent_chunk = parent_chunk
        self.seed = seed # a float
        rnd = random.Random(seed)
        self.x = rnd.uniform(0, 1000)
        self.y = 0
        self.z = rnd.uniform(0, 1000)
        self.size = abs(rnd.gauss(0, 5))
