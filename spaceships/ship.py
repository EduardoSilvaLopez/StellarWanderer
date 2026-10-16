from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional
import math

from common.dialogs.messages import Message, show_message
from galaxies.ore_fields import OreField
from galaxies.ore_mine import OreMine
import game_environment as gem
from .laser import Laser
from .cargo_hold import CargoHold
from .scanner import Scanner
from .notification import Notification
from .kinematics import Position, Velocity
from .attitude import Attitude
from .navigation import Navigation
from common.updating import Updatable, update_queue
if TYPE_CHECKING:
    from galaxies.people.player import Player

class Ship(Updatable):
    """The ship: where it is and how it moves (position, velocity, attitude, navigation), its systems (scanner,
    laser, cargo hold) and its flight limits.

    `is_bound` tells whether it is bound to a world's surface (position and velocity then in the surface frame: x
    east, y up, z north) or free in the star's frame.

    HEIGHT is the eye height above the ground while bound (4 m): the altitude never goes below it, and the spawn
    height and the descent limit use it too. Rotation acceleration, braking and speed limit (ANGULAR_ACC,
    ANGULAR_BRAKE, MAX_ANGULAR_SPEED) are the same on every axis.
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

    ENERGY_MAX = 1e12 #Wh, that is, 1TWh . Daily european consumption is ~ 42GWh (0.042 TWh)

    def __init__(self, owner: Player) -> None:
        self.owner: Player = owner
        self.is_bound: bool = False
        self.position: Position = Position()
        self.velocity: Velocity = Velocity()
        self.attitude: Attitude = Attitude(self)
        self.navigation: Navigation = Navigation(self)
        self.maintenance: float = 1.0
        self.energy_max: float = Ship.ENERGY_MAX  # 1 TWh - prolly too much but let us see. Full: a new ship starts full.
        self.energy: float = Ship.ENERGY_MAX
        self.scanner: Scanner = Scanner(self)
        self.laser: Laser = Laser(self)
        self.cargo_hold: CargoHold = CargoHold(self)
        self.notification: Notification = Notification()
        self.last_update_at: Optional[datetime] = None
        self.next_update_at: Optional[datetime] = None
        self.update(gem.current_environment.date_time)

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Ship:
        """Place the ship, bound, in the first place found on the nearest world."""
        self.is_bound = True
        environment.nearest_world.update_surroundings(10, 0, 0, gem.GameEnvironment.EPOCH)
        central_km2 = next(km2 for km2 in environment.nearest_world.km2s if km2.longitude == 0 and km2.latitude == 0)
        self.position.km2 = central_km2
        self.position.x = central_km2.longitude + 500
        self.position.y = Ship.HEIGHT
        self.position.z = central_km2.latitude + 500
        return self

    @staticmethod
    def load(owner: Player, src: dict) -> Ship:
        result = Ship(owner)
        result.is_bound = src['is_bound']
        result.position = Position.deserialize(src['position'])
        result.velocity = Velocity.deserialize(src['velocity'])
        result.attitude = Attitude.load(result, src['attitude'])
        if result.is_bound:
            result.position.km2 = gem.current_environment.nearest_world.get_km2_at(result.position.x, result.position.z)
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
            'is_bound': self.is_bound,
            'position': self.position.serialize(),
            'velocity': self.velocity.serialize(),
            'attitude': self.attitude.serialize(),
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

        self.reduce_resources(days)

        self.last_update_at = game_date_time
        self.next_update_at = game_date_time + timedelta(seconds=Ship.UPDATE_PERIOD)
        update_queue.add(self)

    def reduce_resources(self, days: float) -> Ship:

        old_maintenance: float = self.maintenance
        old_energy: float =  self.energy
        old_air: float = self.cargo_hold.air
        old_water: float = self.cargo_hold.water
        old_food: float = self.cargo_hold.food
        self.maintenance -=  0.005 * days
        self.energy -=  1e5 * days
        self.cargo_hold.air -= days
        self.cargo_hold.water -= days
        self.cargo_hold.food -= days

        # Maintenance thresholds:
        if self.maintenance <= 0.1 < old_maintenance:
            self.notification.set('CRITICAL: Ship needs urgently maintenance. Go to outpost.')
        elif self.energy <= 0.01 * Ship.ENERGY_MAX < old_energy:
            self.notification.set('CRITICAL: Ship needs urgently more energy. Stop using laser. Go to outpost.')
        elif self.cargo_hold.air <= CargoHold.WARNING_DAYS['air'] < old_air:
            self.notification.set('WARNING: Ship needs air refill. Remain near an outpost.')
        elif self.cargo_hold.air <= 2.0 < old_air:
            self.notification.set('CRITICAL: Ship needs air refill. Go immediately to an outpost.')
        elif self.cargo_hold.water <= CargoHold.WARNING_DAYS['water'] < old_water:
            self.notification.set('CRITICAL: Ship needs water refill. Go immediately to an outpost.')
        elif self.cargo_hold.food <= CargoHold.WARNING_DAYS['food'] < old_food:
            self.notification.set('CRITICAL: You need food refill. Go immediately to an outpost.')

        if self.maintenance <= 0.0:
            self.owner.game_over('Your ship falls appart due to lack of maintenance. Your death is horrible but swift.')
        elif self.energy <= 0.0:
            self.owner.game_over('Your ship becomes a silent frozen box. Your death is slow but calm at the end.')
        elif self.cargo_hold.air <= 0.0:
            self.owner.game_over('You die of CO2 intoxication. A somehow funny death but you are anyway dead.')
        elif self.cargo_hold.water <= -2.0: # Dying of thirst after 2 days without water.
            self.owner.game_over('You die of dehydration. A truly horrible death.')
        elif self.cargo_hold.food <= -14.0: # Starvation at 14 days without food.
            self.owner.game_over('You die of hunger. A slow and horrible death.')

        return self

    def set_mine_pressed(self) -> None:
        '''React to the "place mine" button.'''
        # Cancel is no mine.
        if self.cargo_hold.mines <= 0:
            self.notification.set("No mines available.")
            return
        if not self.is_bound:
            self.notification.set("Mines can only be placed on a world.")
            return

        # Check if rocks nearby.
        player_lon: float = self.position.x
        player_lat: float = self.position.z
        player_yaw: float = self.attitude.yaw
        from galaxies.km2 import Km2
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