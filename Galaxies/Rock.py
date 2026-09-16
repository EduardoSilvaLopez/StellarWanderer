from __future__ import annotations
from datetime import timedelta
from math import sqrt
from typing import TYPE_CHECKING

from Updating.Updatable import Updatable
from Updating.UpdateQueue import update_queue

if TYPE_CHECKING:
    from Galaxies.Km2 import Km2

class Rock(Updatable):
    TEMP_RISE_RATE = 1000.0 # Temp. raise for a 1 square cube rock in 1 second.

    def __init__(self, parent_Km2: Km2, x: float, z: float, saved_alterations: dict):
        import random
        self.parent_km2 = parent_Km2
        my_random = random.Random(parent_Km2.seed + x + z)
        self.size = abs(my_random.gauss(0, 10))
        self.x = x
        self.y = max(0.5 - abs(my_random.gauss(0, 0.1)), -0.5) * self.size
        self.z = z
        self.orientation = my_random.random() * 90 - 45
        self.initial_color = (32 + my_random.randint(0, 32), 32 + my_random.randint(0, 32), 32 + my_random.randint(0, 32))
        self.temperature = 0.0
        self.adjust_color()

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations[alterations_key]
            self.saved_alterations['date_time'] = saved_alterations['date_time']

            if ('temperature' in self.saved_alterations):
                self.temperature = self.saved_alterations['temperature']
                self.adjust_color()

            self.next_update = saved_alterations['date_time'] + timedelta(seconds = 1)
            update_queue.add(self)
        else:
            self.next_update = None

    def set_altered(self):
        if not self.is_altered:
            self.is_altered = True
            self.parent_km2.set_altered()

    def get_alterations_key(self):
        return str(self.x) + ' ' + str(self.z)

    def get_alterations(self):
        '''The change, expressed as dictionary.'''
        if (not self.is_altered):
            return dict()

        return {"temperature": self.temperature}

    def get_next_update(self):
        if self.next_update is None:
            raise Exception("Next update of this rock is none, why was this asked?")
        return self.next_update

    def update(self, game_date_time):
        self.temperature = 0.8 * self.temperature
        if self.temperature < 1.0:
            self.next_update = None
            self.temperature = 0
        else:
            self.next_update = game_date_time + timedelta(seconds = 1)
            update_queue.add(self)
        self.adjust_color()
        self.set_altered()

    def increase_temperature(self, delta_time: float):
        delta_temp = Rock.TEMP_RISE_RATE * delta_time / (self.size ** 3)  # Assuming size is in meters, and temperature rise is proportional to volume
        self.temperature += delta_temp
        self.adjust_color()
        self.set_altered()

        if self.next_update is None:
            # Set this object to be updated regularly
            from GameEnvironment import GameEnvironment
            self.next_update = GameEnvironment.singleton.date_time + timedelta(seconds = 1)
            update_queue.add(self)

    def adjust_color(self):
        temperature_increase = int(sqrt(self.temperature))
        self.color = tuple(min(value + temperature_increase, 255) for value in self.initial_color)
