from __future__ import annotations
from datetime import datetime, timedelta
from math import sqrt
from typing import TYPE_CHECKING

from Updating.Updatable import Updatable
from Updating.UpdateQueue import update_queue

if TYPE_CHECKING:
    from Galaxies.Km2 import Km2

class Rock(Updatable):
    TEMP_RISE_RATE = 1000.0 # Temp. raise for a 1 square cube rock in 1 second.
    TEMP_COOLING_PERIOD = 60 # Once every minute.

    def __init__(self, parent_Km2: Km2, longitude: int, latitude: int):
        import random
        self.parent_km2 = parent_Km2
        my_random = random.Random(parent_Km2.seed + latitude + longitude)
        self.size = abs(my_random.gauss(0, 10))
        self.x = longitude
        self.y = max(0.5 - abs(my_random.gauss(0, 0.1)), -0.5) * self.size
        self.z = latitude
        self.orientation = my_random.random() * 90 - 45
        self.initial_color = (32 + my_random.randint(0, 32), 32 + my_random.randint(0, 32), 32 + my_random.randint(0, 32))
        self.temperature = 0.0
        self.adjust_color()

        self.is_altered = False
        self.saved_alterations = None
        alterations_key = self.get_alterations_key()
        if parent_Km2.saved_alterations is not None and alterations_key in parent_Km2.saved_alterations:
            self.is_altered = True
            self.saved_alterations = parent_Km2.saved_alterations[alterations_key]
            self.saved_alterations['date_time'] = parent_Km2.saved_alterations['date_time']

            if ('temperature' in self.saved_alterations):
                self.temperature = self.saved_alterations['temperature']
                self.adjust_color()

            self.next_update = self.saved_alterations['date_time'] + timedelta(seconds = 1)
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

    def update(self, game_date_time: datetime):
        if (not self.is_altered): return

        last_updated_at = self.next_update
        if (last_updated_at is None): # Re-created after loading.
            if (not self.saved_alterations): raise Exception("Altered but no alterations!?")
            last_updated_at = self.saved_alterations.get('date_time')
            if (not last_updated_at): raise Exception("Alterations without timestamp!?")

        time_passed = game_date_time - last_updated_at
        periods_passed = time_passed.total_seconds() / self.TEMP_COOLING_PERIOD

        self.temperature = (0.999 ** periods_passed) * self.temperature #TODO: remove magic number.
        if self.temperature < 1.0:
            self.next_update = None
            self.temperature = 0
        else:
            self.next_update = game_date_time + timedelta(seconds = self.TEMP_COOLING_PERIOD)
            update_queue.add(self)
            print("Temperature reduced: " + str(self.temperature))
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
            self.next_update = GameEnvironment.singleton.date_time + timedelta(seconds = 5) #TODO: remove magic number.
            update_queue.add(self)

    def adjust_color(self):
        temperature_increase = int(sqrt(self.temperature))
        self.color = tuple(min(value + temperature_increase, 255) for value in self.initial_color)
