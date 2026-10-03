from __future__ import annotations
from cmath import sqrt
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional
import math

from Galaxies.OreField import OreField
from Galaxies.OreMine import OreMine
import GameEnvironment as gem
from Spaceships.CargoHold import CargoHold
from Spaceships.Laser import Laser
from Updating import Updatable, UpdateQueue
if TYPE_CHECKING:
    from Player import Player

class Ship(Updatable):
    HEIGHT = 10 # meters, up to the camera

    UP_DOWN_ACC = 5.0  # meters per second squared
    RIGHT_LEFT_ACC = 10  # meters per second squared
    FORWARD_BACKWARD_ACC = 10.0  # meters per second squared
    ANGULAR_ACC = 10.0  # degrees per second squared
    MAX_ANGULAR_SPEED = 90.0  # degrees per second
    BRAKE_ACC = 10.0  # meters per second squared, max deceleration while braking

    def __init__(self, owner: Player) -> None:
        self.owner = owner
        self.laser = Laser(self)
        self.cargo_hold: CargoHold = CargoHold(self)
        self.notification: str
        self.next_update_at: Optional[datetime] = None

        self.set_notification("Welcome, Comrade Commander.")

    @staticmethod
    def load(owner: Player, src: dict) -> Ship:
        result = Ship(owner)
        result.cargo_hold = CargoHold.load(result, src['cargo_hold'])
        return result

    def serialize(self) -> dict:
        return {
            'cargo_hold': self.cargo_hold.serialize()
        }

    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        self.notification = ""

    def set_notification(self, message: str) -> Ship:
        self.notification = message
        self.next_update_at = gem.current_environment.date_time + timedelta(seconds=5)
        UpdateQueue.update_queue.add(self)

    def set_mine_pressed(self) -> None:
        '''React to the "place mine" button.'''
        # Cancel is no mine.
        if self.cargo_hold.content[CargoHold.CargoElement.MINES] <= 0:
            self.set_notification("No mines available.")
            return

        # Check if rocks nearby.
        player_lon: float = self.owner.position.x
        player_lat: float = self.owner.position.z
        player_orientation: float = self.owner.orientation
        from Galaxies.Km2 import Km2
        relevant_km2s: List[Km2] = list()
        from Galaxies.Km2 import Km2
        for km2 in self.owner.position.km2.parent_world.km2s:
            if (km2.longitude // Km2.SIZE) * Km2.SIZE != km2.longitude\
                and (1 + km2.longitude // Km2.SIZE) * Km2.SIZE != km2.longitude:
                continue
            if (km2.latitude // Km2.SIZE) * Km2.SIZE != km2.latitude\
                and (1 + km2.latitude // Km2.SIZE) * Km2.SIZE != km2.latitude:
                continue
            relevant_km2s.append(km2)

        # Cancel if hitting a rock.
        hitting_a_rock = False
        for km2 in relevant_km2s:
            for rock in km2.rocks:
                if sqrt((rock.longitude - player_lon)**2 + (rock.latitude - player_lat)**2).real >= 100:
                    continue
                delta_x = rock.longitude - player_lon
                delta_z = rock.latitude - player_lat
                bearing = math.degrees(math.atan2(delta_x, delta_z))
                angle_diff = abs(player_orientation - bearing)
                angle_diff = min(angle_diff, 360 - angle_diff)
                if angle_diff > 45:
                    continue
                hitting_a_rock = True
                break        
            if hitting_a_rock:
                break
        if hitting_a_rock:
            self.set_notification("There are rocks there, we cannot place a mine.")
            return

        # Cancel if no ore field.
        front_distance = 50
        radians = math.radians(player_orientation)
        front_lon = player_lon + front_distance * math.sin(radians)
        front_lat = player_lat + front_distance * math.cos(radians)
        targeted_field: OreField = None
        closest_distance = float('inf')
        for km2 in relevant_km2s:
            for field in km2.ore_fields:
                distance_to_field = math.sqrt((field.longitude - front_lon)**2 + (field.latitude - front_lat)**2)
                if distance_to_field < field.radius and distance_to_field < closest_distance:
                    targeted_field = field
                    closest_distance = distance_to_field
        if targeted_field is None:
            self.set_notification("No ore field here.")
            return

        targeted_field.mines.append(OreMine(targeted_field, front_lon, front_lat, player_orientation))
        self.cargo_hold.content[CargoHold.CargoElement.MINES] -= 1