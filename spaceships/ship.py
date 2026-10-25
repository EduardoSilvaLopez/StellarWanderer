from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Tuple
import math

import logging
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
from common import audio
from common.updating import Updatable, update_queue
if TYPE_CHECKING:
    from galaxies.people.player import Player
    from galaxies.star import Star

logger = logging.getLogger(__name__)


class Ship(Updatable):
    """The ship: where it is and how it moves (position, velocity, attitude, navigation), its systems (scanner,
    laser, cargo hold) and its flight limits.

    This class is abstract: a configuration (a subclass, see spaceships/ship_configurations) gives the values that
    change with the pilot's standing (ENERGY_MAX, PRECARIOUSNESS, TEMP_SHIELD_REDUCTION), the forward and backward
    acceleration (FORWARD_BACKWARD_ACC), the braking (BRAKE_ACC, never less than the acceleration) and the cargo hold
    class (CARGO_HOLD). The ship is upgraded by replacing it
    with another configuration (see upgrade_to).

    `is_bound` tells whether it is bound to a world's surface (position and velocity then in the surface frame: x
    east, y up, z north) or free in the star's frame.

    HEIGHT is the eye height above the ground while bound (4 m): the altitude never goes below it, and the spawn
    height and the descent limit use it too. Rotation acceleration, braking and speed limit (ANGULAR_ACC,
    ANGULAR_BRAKE, MAX_ANGULAR_SPEED) are the same on every axis.
    """

    class HeatShield(Enum):
        HeatShieldNone = 0
        HeatShieldOne = 1
        HeatShieldTwo = 2

    HEIGHT = 4  # meters, up to the camera

    UP_DOWN_ACC = 5.0  # m/s^2
    RIGHT_LEFT_ACC = 10  # m/s^2
    ANGULAR_ACC = 10.0  # degrees per second squared
    ANGULAR_BRAKE = 30.0  # degrees per second squared
    MAX_ANGULAR_SPEED = 45.0  # degrees per second
    MINE_FRONT_DISTANCE = 50  # metres ahead of the ship where a new mine is placed

    UPDATE_PERIOD = 60 * 60

    TEMP_MIN = -50
    TEMP_DEFAULT = 25
    TEMP_MAX = 50
    MAINTENANCE_WARNING = 0.1  # the fraction left at which the maintenance warning comes (and its bar line is drawn)

    # Set by each configuration, never here.
    ENERGY_MAX: ClassVar[float]  # Wh, where 1e9 is 1 GWh . Daily european consumption is ~ 42GWh (0.042 TWh)
    PRECARIOUSNESS: ClassVar[float]  # The maximum. Better ships will decrease this.
    TEMP_SHIELD_REDUCTION: ClassVar[float]  # Maximum external temperature allowed, used for TEMP_MAX inside the ship.
    FORWARD_BACKWARD_ACC: ClassVar[float]  # meters per second squared
    BRAKE_ACC: ClassVar[float]  # m/s^2, max deceleration of each of the three axes while braking (Navigation._brake)
    CARGO_HOLD: ClassVar[type[CargoHold]]
    NAME: ClassVar[str]  # the kind of ship, as the pilot knows it (ShipSpecificationsDialog)

    # Every configuration, by qualified name.
    by_name: ClassVar[dict[str, type[Ship]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        Ship.by_name[cls.__qualname__] = cls
        if cls.BRAKE_ACC < cls.FORWARD_BACKWARD_ACC:
            raise TypeError(f"{cls.__qualname__}: BRAKE_ACC cannot be less than FORWARD_BACKWARD_ACC.")

    # region Configuration
    @property
    def energy_max(self) -> float:
        return self.ENERGY_MAX

    @property
    def precariousness(self) -> float:
        return self.PRECARIOUSNESS

    @property
    def temp_shield_reduction(self) -> float:
        return self.TEMP_SHIELD_REDUCTION
    # endregion

    # region Life
    def __init__(self, owner: Player) -> None:
        self.owner: Player = owner
        self.is_bound: bool = False
        self.position: Position = Position()
        self.velocity: Velocity = Velocity()
        self.attitude: Attitude = Attitude(self)
        self.navigation: Navigation = Navigation(self)
        self.maintenance: float = 1.0
        self.energy: float = self.energy_max
        self.temperature: float = Ship.TEMP_DEFAULT
        self.scanner: Scanner = Scanner(self)
        self.laser: Laser = Laser(self)
        self.heat_shield: Ship.HeatShield = self.HeatShield.HeatShieldNone
        self.has_scoop = False
        self.has_solar_panels = False
        self.cargo_hold: CargoHold = self.CARGO_HOLD(self)
        self.notification: Notification = Notification()
        self.is_docked: bool = False  # the pilot is inside an outpost: nothing is consumed (see dock). Not saved
        self.last_update_at: Optional[datetime] = None
        self.next_update_at: Optional[datetime] = None
        self.update(gem.current_environment.date_time)

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Ship:
        """Place the ship, bound, in the first place found on the fixed world."""
        self.is_bound = True
        environment.fixed_world.update_surroundings(10, 0, 0, gem.GameEnvironment.EPOCH)
        central_km2 = next(km2 for km2 in environment.fixed_world.km2s if km2.longitude == 0 and km2.latitude == 0)
        self.position.km2 = central_km2
        self.position.x = central_km2.longitude + 500
        self.position.y = Ship.HEIGHT
        self.position.z = central_km2.latitude + 500
        return self
    # endregion

    # region Updating
    def get_next_update(self) -> datetime:
        return self.next_update_at

    def update(self, game_date_time: datetime) -> None:
        """Every UPDATE_PERIOD, the ship lives through the time passed since the last update (see _live_through). The
        first call only starts the clock."""
        next_update_at = game_date_time + timedelta(seconds=Ship.UPDATE_PERIOD)
        if self.last_update_at is not None:
            self._live_through((game_date_time - self.last_update_at).total_seconds() / (24 * 60 * 60))
            next_update_at = next_update_at.replace(minute=0).replace(second=0)  # Better for debugging.
        self.last_update_at = game_date_time
        self.next_update_at = next_update_at

        if self in update_queue:
            logger.error("Ship still in the queue.")
        else:
            update_queue.add(self)

    def dock(self) -> Ship:
        """The pilot goes into an outpost: the time that has passed until now is lived through, and from now on nothing
        is consumed (maintenance, energy, air, water, food) until `undock`."""
        self._settle()
        self.is_docked = True
        return self

    def undock(self) -> Ship:
        """The pilot leaves the outpost: the time spent inside is lived through without consuming anything, and
        everything is consumed again from now on."""
        self._settle()
        self.is_docked = False
        return self

    def _settle(self) -> Ship:
        """Lives through the time since the last update, so that a change of state starts at this very moment."""
        now = gem.current_environment.date_time
        self._live_through((now - self.last_update_at).total_seconds() / (24 * 60 * 60))
        self.last_update_at = now
        return self

    def death_radius(self, star: Star) -> float:
        """The distance from the star at which the ship reaches TEMP_MAX, with its heat shield: a level L lets through
        5**-L of the light, so the death flux is reached 5**L times farther out, scaled from the default radius."""
        death_flux = star.HEAT_FLUX + (star.DEATH_FLUX - star.HEAT_FLUX) * 5 ** self.heat_shield.value
        return star.default_death_radius * math.sqrt(star.DEATH_FLUX / death_flux)

    def _live_through(self, days: float) -> Ship:
        """`days` pass: maintenance, energy, air, water and food are consumed (unless the ship is docked), the
        temperature moves, the pilot is warned when a level is crossed, and dies when one runs out."""
        old_maintenance: float = self.maintenance
        old_energy: float = self.energy
        old_temperature: float = self.temperature
        old_air: float = self.cargo_hold.air
        old_water: float = self.cargo_hold.water
        old_food: float = self.cargo_hold.food
        if not self.is_docked:  # nothing is consumed inside an outpost
            self.maintenance -= 0.01 * self.precariousness * days
            self.energy -= 1e5 * days
            self.cargo_hold.air -= days
            self.cargo_hold.water -= days
            self.cargo_hold.food -= days

        if self.is_bound:
            hours = days * 24 # Duh
            temp_diff: float = (Ship.TEMP_DEFAULT - self.temperature) * (1 - 0.9**hours)
            self.temperature += temp_diff # Stabilizing.
        else:
            star = gem.current_environment.nearest_system.star
            dist: float = self.navigation.distance_to_body_centre(star)
            heat_radius = star.default_heat_radius
            if dist < heat_radius:
                death_radius = self.death_radius(star)
                fall = Ship.TEMP_DEFAULT * (dist - death_radius) / (heat_radius - death_radius)
                self.temperature = Ship.TEMP_MAX - fall

        # Maintenance thresholds:
        if self.maintenance <= Ship.MAINTENANCE_WARNING < old_maintenance:
            self.notification.set('CRITICAL: Ship needs urgently maintenance. Go to outpost.')
        elif self.energy <= 0.01 * self.energy_max < old_energy:
            self.notification.set('CRITICAL: Ship needs urgently more energy. Stop using laser. Go to outpost.')
        elif old_temperature <= 35 < self.temperature:
            self.notification.set("WARNING: It's getting hot in here. You wanna take your clothes off.")
        elif old_temperature <= 45 < self.temperature:
            self.notification.set("CRITICAL: The controls burn when you touch them. Leave this place.")
        elif self.temperature <= -10 < old_temperature:
            self.notification.set("WARNING: Chilling. Watch the temperature drop. Get a blanket.")
        elif self.temperature <= -35 < old_temperature:
            self.notification.set("CRITICAL: Freezing. Leave this place or take measures *now*.")
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
        elif self.temperature <= self.TEMP_MIN:
            self.owner.game_over('You freeze inside your ship. How this could happen, nobody knows.')
        elif self.temperature > self.TEMP_MAX:
            self.owner.game_over('You die of a heat stroke inside your ship. Better than burning alive or dying of' \
            ' the massive radioactivity around here, at least.')
        elif self.cargo_hold.air <= 0.0:
            self.owner.game_over('You die of CO2 intoxication. A somehow funny death but you are anyway dead.')
        elif self.cargo_hold.water <= -2.0:  # Dying of thirst after 2 days without water.
            self.owner.game_over('You die of dehydration. A truly horrible death.')
        elif self.cargo_hold.food <= -14.0:  # Starvation at 14 days without food.
            self.owner.game_over('You die of hunger. A slow and horrible death.')

        return self
    # endregion

    # region Upgrades
    def upgrade_to(self, configuration: type[Ship]) -> Ship:
        """Replaces this ship with one of `configuration`, which takes over where it is, its systems (rebound to it),
        its cargo and its turn in the update queue. What the configuration changes is refilled to its new maximum;
        the rest is kept. Sets the owner's ship to the new one and returns it."""
        upgraded = configuration(self.owner)  # queues itself, and starts its clock
        update_queue.remove(self)
        upgraded.is_bound = self.is_bound
        upgraded.position = self.position
        upgraded.velocity = self.velocity
        upgraded.maintenance = self.maintenance
        upgraded.energy = self.energy if upgraded.energy_max == self.energy_max else upgraded.energy_max
        upgraded.temperature = self.temperature
        upgraded.heat_shield = self.heat_shield
        upgraded.has_scoop = self.has_scoop
        upgraded.has_solar_panels = self.has_solar_panels
        upgraded.notification = self.notification
        upgraded.last_update_at = self.last_update_at
        upgraded.next_update_at = self.next_update_at
        upgraded.cargo_hold.take_stock_from(self.cargo_hold)
        upgraded.attitude = self.attitude
        upgraded.navigation = self.navigation
        upgraded.scanner = self.scanner
        upgraded.laser = self.laser
        for system in (upgraded.attitude, upgraded.navigation, upgraded.scanner, upgraded.laser):
            system.ship = upgraded
        self.owner.ship = upgraded
        return upgraded

    def change_cargo_hold(self, configuration: type[CargoHold]) -> Ship:
        """Gives the ship a cargo hold of `configuration` in place of its own, keeping the stock."""
        self.cargo_hold = configuration(self).take_stock_from(self.cargo_hold)
        return self
    # endregion

    # region Mines
    def place_mine(self) -> None:
        '''React to the "place mine" button: a mine on the ore field MINE_FRONT_DISTANCE metres ahead, unless something
        forbids it (the pilot is told what).'''
        if self.cargo_hold.mines <= 0:
            self.notification.set("No mines available.", 'mine_refused')
            return
        if not self.is_bound:
            self.notification.set("Mines can only be placed on a world.", 'mine_refused')
            return
        if self._mine_too_near():
            self.notification.set("Mines cannot be placed so near each other.", 'mine_refused')
            return
        if self._rock_in_front():
            self.notification.set("There are rocks there, we cannot place a mine.", 'mine_refused')
            return
        front_lon, front_lat = self._mine_spot()
        targeted_field = self._ore_field_at(front_lon, front_lat)
        if targeted_field is None:
            self.notification.set("No ore field here.", 'mine_refused')
            return

        new_mine = OreMine(targeted_field, front_lon, front_lat, self.attitude.yaw)
        targeted_field.mines.append(new_mine)
        self.cargo_hold.mines -= 1
        audio.play('mine_placed')

    def _mine_spot(self) -> Tuple[float, float]:
        '''Where a mine placed now would stand:
        MINE_FRONT_DISTANCE metres ahead of the ship, on the ground, along its yaw.'''
        radians = math.radians(self.attitude.yaw)
        return (
            self.position.x + Ship.MINE_FRONT_DISTANCE * math.sin(radians),
            self.position.z + Ship.MINE_FRONT_DISTANCE * math.cos(radians),
        )

    def _mine_too_near(self) -> bool:
        '''True if an ore mine already placed stands within OreMine.MINE_MIN_DISTANCE of the spot where a new one
        would go (see _mine_spot).

        Only the loaded Km2s are searched. Every mine within that distance lies in the loaded area around the ship, so
        none is missed, and this needs no search of the whole world.'''
        spot_lon, spot_lat = self._mine_spot()
        spacing = OreMine.MINE_MIN_DISTANCE * OreMine.MINE_RADIUS
        for km2 in gem.current_environment.fixed_world.km2s:
            for ore_field in km2.ore_fields:
                for mine in ore_field.mines:
                    if math.hypot(mine.longitude - spot_lon, mine.latitude - spot_lat) < spacing:
                        return True
        return False

    def _rock_in_front(self) -> bool:
        '''True if a rock stands less than 100 m away, within 45 degrees of the ship's yaw.'''
        for km2 in gem.current_environment.fixed_world.km2s:
            for rock in km2.rocks:
                delta_x = rock.longitude - self.position.x
                delta_z = rock.latitude - self.position.z
                if math.hypot(delta_x, delta_z) >= 100:
                    continue
                bearing = math.degrees(math.atan2(delta_x, delta_z))
                angle_diff = abs(self.attitude.yaw - bearing)
                if min(angle_diff, 360 - angle_diff) <= 45:
                    return True
        return False

    def _ore_field_at(self, longitude: float, latitude: float) -> Optional[OreField]:
        '''The ore field that holds the point, the one with the nearest centre if several do; None if none does.'''
        targeted_field: Optional[OreField] = None
        closest_distance = float('inf')
        for km2 in gem.current_environment.fixed_world.km2s:
            for field in km2.ore_fields:
                distance_to_field = math.hypot(field.longitude - longitude, field.latitude - latitude)
                if distance_to_field < field.radius and distance_to_field < closest_distance:
                    targeted_field = field
                    closest_distance = distance_to_field
        return targeted_field
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {
            'configuration': type(self).__qualname__,
            'is_bound': self.is_bound,
            'position': self.position.serialize(),
            'velocity': self.velocity.serialize(),
            'attitude': self.attitude.serialize(),
            'last_update_at': self.last_update_at.strftime('%Y-%m-%d %H:%M:%S'),
            'maintenance': self.maintenance,
            'energy': self.energy,
            'temperature': self.temperature,
            'heat_shield': self.heat_shield.value,
            'has_scoop': self.has_scoop,
            'has_solar_panels': self.has_solar_panels,
            'cargo_hold': self.cargo_hold.serialize()
        }

    @staticmethod
    def deserialize(owner: Player, src: dict) -> Ship:
        result = Ship.by_name[src['configuration']](owner)
        result.is_bound = src['is_bound']
        result.position = Position.deserialize(src['position'])
        result.velocity = Velocity.deserialize(src['velocity'])
        result.attitude = Attitude.deserialize(result, src['attitude'])
        if result.is_bound:
            result.position.km2 = gem.current_environment.fixed_world.get_km2_at(result.position.x, result.position.z)
        result.last_update_at = datetime.strptime(src['last_update_at'], '%Y-%m-%d %H:%M:%S')
        result.maintenance = src['maintenance']
        result.energy = src['energy']
        result.temperature = src['temperature']
        result.heat_shield = Ship.HeatShield(src['heat_shield'])
        result.has_scoop = src['has_scoop']
        result.has_solar_panels = src['has_solar_panels']
        result.cargo_hold = CargoHold.deserialize(result, src['cargo_hold'])
        return result
    # endregion
