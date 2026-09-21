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
    TEMP_COOLING_FACTOR = 0.999 # Loose 0.1% of their temperature.

    def __init__(self, parent_Km2: Km2, longitude: int, latitude: int, saved_parent_alterations: dict):
        import random
        self.parent_km2 = parent_Km2
        my_random = random.Random(parent_Km2.seed + latitude + longitude)
        self.size = abs(my_random.gauss(0, 10))
        self.x = longitude
        self.y = max(0.5 - abs(my_random.gauss(0, 0.25)), -0.5) * self.size
        self.z = latitude
        self.orientation = my_random.random() * 180 - 90
        self.tilt = my_random.random() * 45
        self.initial_color = (40 + my_random.randint(0, 32), 40 + my_random.randint(0, 32), 40 + my_random.randint(0, 32))
        self.temperature = 0.0
        self.adjust_color()

        self.last_updated_at = None
        self.next_update_at = None
        alterations_key = self.get_alterations_key()
        if saved_parent_alterations is not None and alterations_key in saved_parent_alterations:
            self.set_last_updated(parent_Km2.saved_parent_alterations['date_time'])
            saved_alterations = parent_Km2.saved_alterations[alterations_key]

            if ('temperature' in saved_alterations):
                self.temperature = saved_alterations['temperature']
                self.adjust_color()

            self.next_update_at = self.last_updated_at + timedelta(seconds = 1)
            update_queue.add(self)
            print("Altered rock loaded at ", self.temperature, "° . Queue size", len(update_queue._queue))

    def set_last_updated(self, new_date_time: datetime) -> Rock:
        self.last_updated_at = new_date_time
        if not self.parent_km2.is_altered:
            self.parent_km2.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.x) + ' ' + str(self.z)

    def get_alterations(self) -> dict:
        '''The change, expressed as dictionary.'''
        if self.last_updated_at is None:
            return None
        return {"temperature": self.temperature}

    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        if self.next_update_at is None:
            return # Already running.

        if self.last_updated_at is None:
            # No idea how much type passed. For rocks, this is critical. Prepare for next time and leave.
            self.last_updated_at = game_date_time
            self.next_update_at = game_date_time + timedelta(seconds = self.TEMP_COOLING_PERIOD)
            update_queue.add(self)
            print("Rock ready to be updated next time. Queue size: ", len(update_queue._queue))
            return

        time_passed = game_date_time - self.last_updated_at
        periods_passed = time_passed.total_seconds() / self.TEMP_COOLING_PERIOD

        self.temperature = (self.TEMP_COOLING_FACTOR ** periods_passed) * self.temperature
        if self.temperature < 1.0:
            self.temperature = 0
            self.next_update_at = None
            print("Rock won't be updated anymore, too cold. Queue size", len(update_queue._queue))
        else:
            self.next_update_at = game_date_time + timedelta(seconds = self.TEMP_COOLING_PERIOD)
            update_queue.add(self)

        self.adjust_color()
        self.set_last_updated(game_date_time)

        print("Temperature reduced: ", str(self.temperature), ". Queue size: ", len(update_queue._queue))

    def stop_updating(self) -> None:
        if self.next_update_at is None:
            return # Already not updating.

        self.next_update_at = None
        update_queue.remove(self)
        print("Rock won't be updated anymore, at (", self.x, ", ", self.z, ") . Queue size", len(update_queue._queue))

    def start_updating(self, update_time: datetime) -> None:
        if self.next_update_at is not None:
            return # Already updating.
        self.next_update_at = update_time # Immediately
        update_queue.add(self)
        print("Rock will be updated again, at ", self.temperature, "° . Queue size", len(update_queue._queue))

    def increase_temperature(self, delta_time: float, game_date_time: datetime) -> Rock:
        delta_temp = Rock.TEMP_RISE_RATE * delta_time / (self.size ** 3)  # Assuming size is in meters, and temperature rise is proportional to volume
        self.temperature += delta_temp

        self.adjust_color()
        if self.next_update_at is None:
            self.start_updating(game_date_time) # First time we just get ready anyway.
        return self

    def adjust_color(self) -> Rock:
        temperature_increase = int(sqrt(self.temperature))
        self.color = tuple(min(value + temperature_increase, 255) for value in self.initial_color)

        return self
