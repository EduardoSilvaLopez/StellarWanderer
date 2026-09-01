import random

class Rock:
    def __init__(self, parent_Km2, x, z):
        self.parent_chunk = parent_Km2
        my_random = random.Random(parent_Km2.seed + x + z)
        self.x = x
        self.y = 0
        self.z = z
        self.size = abs(my_random.gauss(0, 10))
