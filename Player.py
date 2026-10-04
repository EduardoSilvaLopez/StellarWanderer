from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from cmath import pi
import math
import logging

from Galaxies.World import Vector3; logger = logging.getLogger(__name__)
from Galaxies.Km2 import Km2
from Spaceships.Ship import Ship
import GameEnvironment as gem
if TYPE_CHECKING:
    from Galaxies.World import World

class Player:
    # Time compression, in ship-seconds per real second. Keypad +/- steps by 10x.
    TIME_SCALE_MIN = 1
    TIME_SCALE_MAX = 1_000_000
    TIME_SCALE_STEP = 10

    def __init__(self) -> None:
        self.time_scale: int = 1  # Default time scale
        self.orientation: float = 0.0  # Degrees clockwise from north

        self.ship: Ship = Ship(self)
        self.ship.laser.firing = False  # Laser firing (SPACE held)

        self.position = type('Position', (object,), {})()  # Create a simple object to hold position attributes
        self.is_bound: bool = False
        self.position.km2 = None
        self.position.x = 0
        self.position.y = 0
        self.position.z = 0
        self.velocity = type('Velocity', (object,), {})()  # Create a simple object to hold velocity attributes
        self.velocity.x = 0.0
        self.velocity.y = 0.0
        self.velocity.z = 0.0
        self.velocity.angular = 0.0

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Player:
        from Galaxies.World import World
        ''' Spawn the player in the given environment, just using the first place we find.'''
        self.is_bound = True
        environment.nearest_world.update_surroundings(10, 0, 0, gem.GameEnvironment.EPOCH)
        central_km2 = next(km2 for km2 in environment.nearest_world.km2s if km2.longitude == 0 and km2.latitude == 0)
        self.position.km2 = central_km2
        self.position.x = self.position.km2.longitude + 500
        self.position.y = 10
        self.position.z = self.position.km2.latitude + 500
        return self

    def position_in_km2(self, km2: Km2, x: int, y: int, z: int) -> Player:
        ''' Set the player in a specific Km2 and coordinates.'''
        self.position.km2 = km2
        self.position.x = x
        self.position.y = y
        self.position.z = z
        return self

    def serialize(self) -> dict:
        world = gem.current_environment.nearest_world
        return {
            'time_scale': self.time_scale,
            'orientation': self.orientation,
            'stellar_system.x': world.parent_orbit.parent_stellar_system.x,
            'stellar_system.y': world.parent_orbit.parent_stellar_system.y,
            'stellar_system.z': world.parent_orbit.parent_stellar_system.z,
            'orbit.number': world.parent_orbit.number,
            'world.initial_degrees_in_orbit': world.initial_degrees_in_orbit,
            'is_bound': self.is_bound,
            'position.x': self.position.x,
            'position.y': self.position.y,
            'position.z': self.position.z,
            'velocity.x': self.velocity.x,
            'velocity.y': self.velocity.y,
            'velocity.z': self.velocity.z,
            'velocity.angular': self.velocity.angular,
            'ship': self.ship.serialize()        
        }

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Player:
        result = Player()
        result.time_scale = loaded_attributes['time_scale']
        result.orientation = loaded_attributes.get('orientation', 0.0)
        result.position.x = loaded_attributes['position.x']
        result.position.y = loaded_attributes['position.y']
        result.position.z = loaded_attributes['position.z']
        result.velocity.x = loaded_attributes['velocity.x']
        result.velocity.y = loaded_attributes['velocity.y']
        result.velocity.z = loaded_attributes['velocity.z']
        result.velocity.angular = loaded_attributes['velocity.angular']
        result.is_bound = loaded_attributes['is_bound']

        if result.is_bound:
            result.position.km2 = gem.current_environment.nearest_world\
                .get_km2_at(result.position.x, result.position.z)

        result.ship = Ship.load(result, loaded_attributes['ship'])
        return result


    def increase_time_scale(self) -> Player:
        self.time_scale = min(self.time_scale * self.TIME_SCALE_STEP, self.TIME_SCALE_MAX)
        return self

    def decrease_time_scale(self) -> Player:
        self.time_scale = max(self.time_scale // self.TIME_SCALE_STEP, self.TIME_SCALE_MIN)
        return self

    def update_angular_velocity(self, delta_time: float, counterclockwise: int, clockwise: int, braking: bool = False) -> Player:
        """Rotate the ship with inertia: Q/E set angular acceleration, not angular speed.

        Angular speed (deg/s) is stored in self.velocity.angular and capped at
        ship.MAX_ANGULAR_SPEED. Braking overrides Q/E and decelerates angular
        speed toward zero at ship.ANGULAR_ACC, never overshooting.
        """
        if braking:
            speed = abs(self.velocity.angular)
            if speed > 0:
                decel = min(self.ship.ANGULAR_ACC * delta_time, speed)
                self.velocity.angular -= math.copysign(decel, self.velocity.angular)
        else:
            direction = clockwise - counterclockwise
            self.velocity.angular += direction * self.ship.ANGULAR_ACC * delta_time

        self.velocity.angular = max(-self.ship.MAX_ANGULAR_SPEED, min(self.ship.MAX_ANGULAR_SPEED, self.velocity.angular))
        self.orientation = (self.orientation + self.velocity.angular * delta_time) % 360
        return self

    def update_position_and_velocity(
            self,
            delta_time: float,
            longitude_accel_input: float,
            altitude_accel_input: float,
            latitude_accel_input: float,
            braking: bool = False
            ) -> Player:
        self.update_coordinates(delta_time, longitude_accel_input, altitude_accel_input, latitude_accel_input, braking)
        world = gem.current_environment.nearest_world
        if self.is_bound and self.position.y > world.radius: # Local coordinates
            self.unbind_to(world)
        # elif not self.is_bound and (self.position.x**2 + self.position.y**2 + self.position.z**2) < (1.5*world.radius)**2:
        elif not self.is_bound and self.position.y <= 0.5 * world.radius: # TEMPORARY - until stellar coordinates implemented.
            self.bind_to(world)

        if not self.is_bound:
            return self
        
        new_km2 = gem.current_environment.nearest_world.get_km2_at(self.position.x, self.position.z)
        if new_km2 is None or new_km2 != self.position.km2:
            gem.current_environment.nearest_world.update_surroundings(
                self.position.y,
                self.position.x,
                self.position.z,
                gem.current_environment.date_time
                )
        self.position.km2 = gem.current_environment.nearest_world.get_km2_at(self.position.x, self.position.z)
        return self

    def update_coordinates(self, delta_time: float, longitude_accel_input: float, altitude_accel_input: float, latitude_accel_input: float, braking: bool = False) -> Player:
        """
        Update the player's velocity and position based on ship-relative controls.

        All movement is inertial: thrust keys set acceleration, not velocity
        directly. Holding a key keeps speeding the ship up along that direction;
        releasing it leaves the ship drifting at whatever velocity it has
        accumulated in self.velocity (m/s), with no drag.

        Braking (S) overrides all thrust keys: instead of acceleration, it
        applies up to ship.BRAKE_ACC m/s^2 opposing the current velocity in
        all three axes (horizontal + vertical), never overshooting past zero.

        Args:
            delta_time: Time elapsed in game seconds
            longitude_accel_input: Ship-relative right thrust (1 right, -1 left, 0 none)
            altitude_accel_input: Vertical thrust (1 up, -1 down, 0 none)
            latitude_accel_input: Ship-relative forward thrust (1 forward, -1 backward, 0 none)
            braking: If True, ignore all accel inputs and decelerate all axes to zero instead
        """
        if braking:
            speed = math.hypot(self.velocity.x, self.velocity.y, self.velocity.z)
            if speed > 0:
                decel = min(self.ship.BRAKE_ACC * delta_time, speed)
                scale = (speed - decel) / speed
                self.velocity.x *= scale
                self.velocity.y *= scale
                self.velocity.z *= scale
        else:
            orientation = math.radians(self.orientation)
            sin_orientation = math.sin(orientation)
            cos_orientation = math.cos(orientation)
            local_right = longitude_accel_input
            local_forward = latitude_accel_input
            world_accel_x = local_right * cos_orientation + local_forward * sin_orientation
            world_accel_z = -local_right * sin_orientation + local_forward * cos_orientation

            self.velocity.x += world_accel_x * self.ship.RIGHT_LEFT_ACC * delta_time
            self.velocity.y += altitude_accel_input * self.ship.UP_DOWN_ACC * delta_time
            self.velocity.z += world_accel_z * self.ship.FORWARD_BACKWARD_ACC * delta_time

        # Update longitude, east to west of viceversa crossing the anti-meridian.
        self.position.x += self.velocity.x * delta_time
        radius = gem.current_environment.nearest_world.radius
        if self.position.x < -pi * radius:
            self.position.x += pi * radius * 2
        elif self.position.x > pi * radius:
            self.position.x -= pi * radius * 2

        # Update altitude, there is a MIN
        self.position.y += self.velocity.y * delta_time
        self.position.y = max(self.ship.HEIGHT, self.position.y)

        # Update latitude, clamping between the north and south poles.
        self.position.z += self.velocity.z * delta_time
        self.position.z = max(
            -pi * radius / 2,
            min(pi * radius / 2, self.position.z)
        )

        # Constrain vertical velocity: can't descend faster than current altitude
        # (prevents ship from accelerating into ground arbitrarily fast).
        self.velocity.y = max(-(self.position.y - self.ship.HEIGHT), self.velocity.y)
        return self

    def bind_to(self, world: World) -> Player:
        logger.info(f"Arriving to {world.name}.")

        world_pos: tuple = world.calculate_stellar_position(gem.current_environment.date_time)
        player_pos: tuple = self.calculate_stellar_position(world, world_pos)
        logger.info(f"Stellar positions:")
        logger.info(f"             |        X        |        Y        |        Z")
        logger.info(f"        World|  {world_pos[0]}  |  {world_pos[1]}  |  {world_pos[2]}")
        logger.info(f"       Player|  {player_pos[0]}  |  {player_pos[1]}  |  {player_pos[2]}")

        self.is_bound = True
        return self

    def unbind_to(self, world: World) -> Player:
        logger.info(f"Leaving {world.name}.")

        world_pos: Vector3 = world.calculate_stellar_position(gem.current_environment.date_time)
        player_pos: Vector3 = self.calculate_stellar_position(world, world_pos)
        logger.info(f"Stellar positions:")
        logger.info(f"             |        X        |        Y        |        Z")
        logger.info(f"        World|  {world_pos[0]}  |  {world_pos[1]}  |  {world_pos[2]}")
        logger.info(f"       Player|  {player_pos[0]}  |  {player_pos[1]}  |  {player_pos[2]}")

        world_vel: Vector3 = world.calculate_stellar_velocity(gem.current_environment.date_time)
        player_vel: Vector3 = self.calculate_stellar_velocity(world, world_vel)
        logger.info(f"Stellar velocities:")
        logger.info(f"             |        X        |        Y        |        Z")
        logger.info(f"        World|  {world_vel[0]}  |  {world_vel[1]}  |  {world_vel[2]}")
        logger.info(f"       Player|  {player_vel[0]}  |  {player_vel[1]}  |  {player_vel[2]}")

        self.is_bound = False
        return self

    def calculate_stellar_position(self, world: World, world_pos: Vector3) -> Vector3:
        _, up_hat, _ = world.surface_basis(self, gem.current_environment.date_time)
        distance_from_centre = world.radius + self.position.y
        offset_x, offset_y, offset_z = (component * distance_from_centre for component in up_hat)
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated here.
        return (world_pos[0] + offset_x, world_pos[1] - offset_y, world_pos[2] + offset_z)

    def calculate_stellar_velocity(self, world: World, world_vel: Vector3) -> Vector3:
        east_hat, up_hat, north_hat = world.surface_basis(self, gem.current_environment.date_time)
        latitude_angle = self.position.z / world.radius
        spin_speed = math.tau / world.rotation_period * (world.radius + self.position.y) * math.cos(latitude_angle)
        logger.info(f"DEBUG-VEL pos=({self.position.x}, {self.position.y}, {self.position.z}) vel=({self.velocity.x}, {self.velocity.y}, {self.velocity.z}) "
                    f"radius={world.radius} rotation_period={world.rotation_period} latitude_angle={latitude_angle} spin_speed={spin_speed} "
                    f"east_hat={east_hat} up_hat={up_hat} north_hat={north_hat} is_bound={self.is_bound}")

        # Star-centred basis: Y is opposite to the orbital motion, so world_vel's Y is negated first.
        world_vel_basis = (world_vel[0], -world_vel[1], world_vel[2])
        total = [
            world_vel_basis[i]
            + (spin_speed + self.velocity.x) * east_hat[i]
            + self.velocity.y * up_hat[i]
            + self.velocity.z * north_hat[i]
            for i in range(3)
        ]
        return (total[0], -total[1], total[2])

current_player: Player = None