from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional
import math

from Galaxies.ore_fields import OreField
from Galaxies.ore_mine import OreMine
import game_environment as gem
from .laser import Laser
from .cargo_hold import CargoHold
from .scanner import Scanner
from .notification import Notification
from Updating import Updatable, update_queue
if TYPE_CHECKING:
    from Galaxies.People.player import Player

class Ship(Updatable):
    """The ship's systems (scanner, laser, cargo hold) and its flight limits.

    HEIGHT is the eye height above the ground while bound (4 m): the altitude never goes below it, and the spawn
    height and the descent limit use it too. Rotation accelerations and speed limits (ANGULAR_ACC,
    MAX_ANGULAR_SPEED) are shared with the player's attitude; see Player.
    """

    HEIGHT = 4 # meters, up to the camera

    UP_DOWN_ACC = 5.0  # meters per second squared
    RIGHT_LEFT_ACC = 10  # meters per second squared
    FORWARD_BACKWARD_ACC = 10.0  # meters per second squared
    ANGULAR_ACC = 10.0  # degrees per second squared
    ANGULAR_BRAKE = 20.0  # degrees per second squared
    MAX_ANGULAR_SPEED = 45.0  # degrees per second
    BRAKE_ACC = 10.0  # meters per second squared, max deceleration while braking

    UPDATE_PERIOD = 24 * 60 * 60 # Large enough to avoid drifts.

    def __init__(self, owner: Player) -> None:
        self.owner: Player = owner
        self.maintenance: float = 1.0
        self.energy: int = 1e12 # 1 TWh - prolly too much but let us see.
        self.scanner: Scanner = Scanner(self)
        self.laser: Laser = Laser(self)
        self.cargo_hold: CargoHold = CargoHold(self)
        self.notification: Notification = Notification()
        self.last_update_at: Optional[datetime] = None
        self.next_update_at: Optional[datetime] = None
        self.update(gem.current_environment.date_time)

    @staticmethod
    def load(owner: Player, src: dict) -> Ship:
        result = Ship(owner)
        if 'last_update_at' in src:
            result.last_update_at = datetime.strptime(src['last_update_at'], '%Y-%m-%d %H:%M:%S')
        if 'maintenance' in src:
            result.maintenance = src['maintenance']
        if 'energy' in src:
            result.energy = src['energy']
        result.cargo_hold = CargoHold.load(result, src['cargo_hold'])
        result.update(gem.current_environment.date_time)
        return result

    def serialize(self) -> dict:
        return {
            'last_update_at' : self.last_update_at.strftime('%Y-%m-%d %H:%M:%S'),
            'maintenance' : self.maintenance,
            'energy' : self.energy,
            'cargo_hold': self.cargo_hold.serialize()
        }

    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        if self.last_update_at is None:
            self.last_update_at = game_date_time
            self.next_update_at = game_date_time + timedelta(seconds=Ship.UPDATE_PERIOD)
            update_queue.add(self)
            return
        
        days = (game_date_time - self.last_update_at).total_seconds() / (24 * 60 * 60)

        self.maintenance -=  0.001 * days
        self.energy -=  1e+5 * days
        self.cargo_hold.air -= days
        self.cargo_hold.water -= days
        self.cargo_hold.food -= days

        # Here... warnings and even game over, later.

        self.last_update_at = game_date_time
        self.next_update_at = game_date_time + timedelta(seconds=Ship.UPDATE_PERIOD)
        update_queue.add(self)

    def set_mine_pressed(self) -> None:
        '''React to the "place mine" button.'''
        # Cancel is no mine.
        if self.cargo_hold.mines <= 0:
            self.notification.set("No mines available.")
            return
        if not self.owner.is_bound:
            self.notification.set("Mines can only be placed on a world.")
            return

        # Check if rocks nearby.
        player_lon: float = self.owner.position.x
        player_lat: float = self.owner.position.z
        player_yaw: float = self.owner.yaw
        from Galaxies.km2 import Km2
        relevant_km2s: List[Km2] = list()
        import game_environment as gem
        world = gem.current_environment.nearest_world
        for km2 in world.km2s:
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
                if math.hypot(rock.longitude - player_lon, rock.latitude - player_lat) >= 100:
                    continue
                delta_x = rock.longitude - player_lon
                delta_z = rock.latitude - player_lat
                bearing = math.degrees(math.atan2(delta_x, delta_z))
                angle_diff = abs(player_yaw - bearing)
                angle_diff = min(angle_diff, 360 - angle_diff)
                if angle_diff > 45:
                    continue
                hitting_a_rock = True
                break        
            if hitting_a_rock:
                break
        if hitting_a_rock:
            self.notification.set("There are rocks there, we cannot place a mine.")
            return

        # Cancel if no ore field.
        front_distance = 50
        radians = math.radians(player_yaw)
        front_lon = player_lon + front_distance * math.sin(radians)
        front_lat = player_lat + front_distance * math.cos(radians)
        targeted_field: OreField = None
        closest_distance = float('inf')
        for km2 in relevant_km2s:
            for field in km2.ore_fields:
                distance_to_field = math.hypot(field.longitude - front_lon, field.latitude - front_lat)
                if distance_to_field < field.radius and distance_to_field < closest_distance:
                    targeted_field = field
                    closest_distance = distance_to_field
        if targeted_field is None:
            self.notification.set("No ore field here.")
            return

        new_mine = OreMine(targeted_field, front_lon, front_lat, player_yaw)
        targeted_field.mines.append(new_mine)
        self.cargo_hold.mines -= 1