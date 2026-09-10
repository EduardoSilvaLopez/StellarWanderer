from math import sqrt
import random

class Rock:
    TEMP_RISE_RATE = 1000.0 # Temp. raise for a 1 square cube rock in 1 second.

    def __init__(self, parent_Km2, x, z):
        self.parent_chunk = parent_Km2
        my_random = random.Random(parent_Km2.seed + x + z)
        self.size = abs(my_random.gauss(0, 10))
        self.x = x
        self.y = 0.5 * self.size
        self.z = z
        self.initial_color = (32 + my_random.randint(0, 32), 32 + my_random.randint(0, 32), 32 + my_random.randint(0, 32))
        self.temperature = 0.0
        self.adjust_color()

    def increase_temperature(self, delta_time):
        delta_temp = Rock.TEMP_RISE_RATE * delta_time / (self.size ** 3)  # Assuming size is in meters, and temperature rise is proportional to volume
        self.temperature += delta_temp
        self.adjust_color()

    def adjust_color(self):
        temperature_increase = int(sqrt(self.temperature))
        self.color = (min(self.initial_color[0] + temperature_increase, 255),
                min(self.initial_color[1] + temperature_increase, 255),
                min(self.initial_color[2] + temperature_increase, 255)
                )