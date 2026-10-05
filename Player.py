from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from cmath import pi
import math
import logging

from Galaxies.World import World, Vector3; logger = logging.getLogger(__name__)
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
    BIND_RADIUS_MULTIPLE = 1.5

    def __init__(self) -> None:
        self.time_scale: int = 1  # Default time scale
        self.right: Vector3 = (1.0, 0.0, 0.0)
        self.up: Vector3 = (0.0, 1.0, 0.0)
        self.forward: Vector3 = (0.0, 0.0, 1.0)

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
        self.velocity.yaw = 0.0
        self.velocity.pitch = 0.0
        self.velocity.roll = 0.0

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
            'velocity.yaw': self.velocity.yaw,
            'attitude.right': list(self.right),
            'attitude.up': list(self.up),
            'attitude.forward': list(self.forward),
            'velocity.pitch': self.velocity.pitch,
            'velocity.roll': self.velocity.roll,
            'ship': self.ship.serialize()
        }

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Player:
        result = Player()
        result.time_scale = loaded_attributes['time_scale']
        result.position.x = loaded_attributes['position.x']
        result.position.y = loaded_attributes['position.y']
        result.position.z = loaded_attributes['position.z']
        result.velocity.x = loaded_attributes['velocity.x']
        result.velocity.y = loaded_attributes['velocity.y']
        result.velocity.z = loaded_attributes['velocity.z']
        result.velocity.yaw = loaded_attributes['velocity.yaw']
        result.right = tuple(loaded_attributes['attitude.right'])
        result.up = tuple(loaded_attributes['attitude.up'])
        result.forward = tuple(loaded_attributes['attitude.forward'])
        result.velocity.pitch = loaded_attributes['velocity.pitch']
        result.velocity.roll = loaded_attributes.get('velocity.roll', 0.0)
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

    def update_yaw(self, delta_time: float, counterclockwise: int, clockwise: int, braking: bool = False) -> Player:
        """Yaw the ship with inertia: Q/E set yaw acceleration, not yaw rate.

        Yaw rate (deg/s) is stored in self.velocity.yaw and capped at
        ship.MAX_ANGULAR_SPEED. Braking overrides Q/E and decelerates yaw
        speed toward zero at ship.ANGULAR_ACC, never overshooting.
        """
        if braking:
            speed = abs(self.velocity.yaw)
            if speed > 0:
                decel = min(self.ship.ANGULAR_ACC * delta_time, speed)
                self.velocity.yaw -= math.copysign(decel, self.velocity.yaw)
        else:
            direction = clockwise - counterclockwise
            self.velocity.yaw += direction * self.ship.ANGULAR_ACC * delta_time

        self.velocity.yaw = max(-self.ship.MAX_ANGULAR_SPEED, min(self.ship.MAX_ANGULAR_SPEED, self.velocity.yaw))
        self._yaw(math.radians(self.velocity.yaw * delta_time))
        return self

    def update_pitch(self, delta_time: float, nose_up: int, nose_down: int, braking: bool = False) -> Player:
        """Pitch the ship with inertia, about its right axis, like update_yaw does for yaw."""
        if self.is_bound:
            return self

        if braking:
            speed = abs(self.velocity.pitch)
            if speed > 0:
                decel = min(self.ship.ANGULAR_ACC * delta_time, speed)
                self.velocity.pitch -= math.copysign(decel, self.velocity.pitch)
        else:
            direction = nose_up - nose_down
            self.velocity.pitch += direction * self.ship.ANGULAR_ACC * delta_time

        self.velocity.pitch = max(-self.ship.MAX_ANGULAR_SPEED, min(self.ship.MAX_ANGULAR_SPEED, self.velocity.pitch))
        self._pitch(math.radians(self.velocity.pitch * delta_time))
        return self

    def update_roll(self, delta_time: float, roll_left: int, roll_right: int, braking: bool = False) -> Player:
        """Roll the ship with inertia, about its forward axis."""

        if self.is_bound:
            return self

        if braking:
            speed = abs(self.velocity.roll)
            if speed > 0:
                decel = min(self.ship.ANGULAR_ACC * delta_time, speed)
                self.velocity.roll -= math.copysign(decel, self.velocity.roll)
        else:
            direction = roll_right - roll_left
            self.velocity.roll += direction * self.ship.ANGULAR_ACC * delta_time

        self.velocity.roll = max(-self.ship.MAX_ANGULAR_SPEED, min(self.ship.MAX_ANGULAR_SPEED, self.velocity.roll))
        self._roll(math.radians(self.velocity.roll * delta_time))
        return self

    def _yaw(self, angle: float) -> None:
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        forward, right = self.forward, self.right
        self.forward = tuple(cos_a * f + sin_a * r for f, r in zip(forward, right))
        self.right = tuple(cos_a * r - sin_a * f for r, f in zip(right, forward))

    def _pitch(self, angle: float) -> None:
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        forward, up = self.forward, self.up
        self.forward = tuple(cos_a * f + sin_a * u for f, u in zip(forward, up))
        self.up = tuple(cos_a * u - sin_a * f for u, f in zip(up, forward))

    def _roll(self, angle: float) -> None:
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        right, up = self.right, self.up
        self.right = tuple(cos_a * r + sin_a * u for r, u in zip(right, up))
        self.up = tuple(cos_a * u - sin_a * r for u, r in zip(up, right))

    @property
    def yaw(self) -> float:
        """Heading in degrees clockwise from north, from the ship's forward axis."""
        return math.degrees(math.atan2(self.forward[0], self.forward[2])) % 360

    def pitch_angle(self, world: World, current_datetime: datetime) -> float:
        """Nose-up angle in degrees above the local horizon."""
        up_reference = World._scale(-1.0, self.direction_down(world, current_datetime))
        return math.degrees(math.asin(max(-1.0, min(1.0, World._dot(self.forward, up_reference)))))

    def direction_down(self, world: World, current_datetime: datetime) -> Vector3:
        """Unit vector from the ship towards the planet's surface, in the active frame."""
        if self.is_bound:
            return (0.0, -1.0, 0.0)
        centre = world.calculate_stellar_position(current_datetime)
        offset = (centre[0] - self.position.x, centre[1] - self.position.y, centre[2] - self.position.z)
        length = math.hypot(*offset)
        return (offset[0] / length, offset[1] / length, offset[2] / length)

    def direction_to_star(self, world: World, current_datetime: datetime) -> Vector3:
        if self.is_bound:
            return world.calculate_star_position(self, current_datetime)
        return (-self.position.x, -self.position.y, -self.position.z)

    def camera_components(self, vector: Vector3) -> Vector3:
        """Components of a direction along the ship's right, up and forward axes."""
        return (World._dot(vector, self.right), World._dot(vector, self.up), World._dot(vector, self.forward))

    def camera_matrix(self) -> list:
        """Column-major 4x4 for glMultMatrixf, mapping the ship's axes to OpenGL's eye axes."""
        rows = (self.right, self.up, (-self.forward[0], -self.forward[1], -self.forward[2]))
        return [
            rows[0][0], rows[1][0], rows[2][0], 0.0,
            rows[0][1], rows[1][1], rows[2][1], 0.0,
            rows[0][2], rows[1][2], rows[2][2], 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]

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
        if self.is_bound and self.position.y > world.radius:
            self.unbind_to(world)
        elif not self.is_bound and self._distance_to_world_centre(world) <= Player.BIND_RADIUS_MULTIPLE * world.radius:
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
        elif self.is_bound:
            yaw = math.radians(self.yaw)
            sin_yaw = math.sin(yaw)
            cos_yaw = math.cos(yaw)
            local_right = longitude_accel_input
            local_forward = latitude_accel_input
            world_accel_x = local_right * cos_yaw + local_forward * sin_yaw
            world_accel_z = -local_right * sin_yaw + local_forward * cos_yaw

            self.velocity.x += world_accel_x * self.ship.RIGHT_LEFT_ACC * delta_time
            self.velocity.y += altitude_accel_input * self.ship.UP_DOWN_ACC * delta_time
            self.velocity.z += world_accel_z * self.ship.FORWARD_BACKWARD_ACC * delta_time
        else:
            accel = tuple(
                longitude_accel_input * self.ship.RIGHT_LEFT_ACC * r
                + latitude_accel_input * self.ship.FORWARD_BACKWARD_ACC * f
                + altitude_accel_input * self.ship.UP_DOWN_ACC * u
                for r, f, u in zip(self.right, self.forward, self.up)
            )
            self.velocity.x += accel[0] * delta_time
            self.velocity.y += accel[1] * delta_time
            self.velocity.z += accel[2] * delta_time

        if not self.is_bound:
            self.position.x += self.velocity.x * delta_time
            self.position.y += self.velocity.y * delta_time
            self.position.z += self.velocity.z * delta_time
            return self

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

        current_datetime = gem.current_environment.date_time
        stellar_pos: Vector3 = (self.position.x, self.position.y, self.position.z)
        stellar_vel: Vector3 = (self.velocity.x, self.velocity.y, self.velocity.z)
        longitude, altitude, latitude = world.stellar_to_surface_position(stellar_pos, current_datetime)
        surface_vel = world.stellar_to_surface_velocity(stellar_vel, longitude, altitude, latitude, current_datetime)

        self.position.x, self.position.y, self.position.z = longitude, altitude, latitude
        self.velocity.x, self.velocity.y, self.velocity.z = surface_vel
        forward_surface = world.stellar_vector_to_surface(self.forward, longitude, latitude, current_datetime)
        yaw = math.atan2(forward_surface[0], forward_surface[2])
        self.right = (math.cos(yaw), 0.0, -math.sin(yaw))
        self.up = (0.0, 1.0, 0.0)
        self.forward = (math.sin(yaw), 0.0, math.cos(yaw))
        self.velocity.yaw = 0.0
        self.velocity.pitch = 0.0
        self.velocity.roll = 0.0

        logger.info(f"Positions:")
        logger.info(f"               |        X        |        Y        |        Z")
        logger.info(f"World (stellar)|  {stellar_pos[0]}  |  {stellar_pos[1]}  |  {stellar_pos[2]}")
        logger.info(f" Player (local)|  {longitude}  |  {altitude}  |  {latitude}")

        logger.info(f"Velocities:")
        logger.info(f"             |        X        |        Y        |        Z")
        logger.info(f"        World|  {stellar_pos[0]}  |  {stellar_pos[1]}  |  {stellar_pos[2]}")
        logger.info(f"       Player|  {surface_vel[0]}  |  {surface_vel[1]}  |  {surface_vel[2]}")

        self.is_bound = True
        return self

    def _distance_to_world_centre(self, world: World) -> float:
        return math.dist((self.position.x, self.position.y, self.position.z), world.calculate_stellar_position(gem.current_environment.date_time))

    def altitude_above_surface(self, world: World) -> float:
        if self.is_bound:
            return self.position.y
        return self._distance_to_world_centre(world) - world.radius

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

        current_datetime = gem.current_environment.date_time
        longitude, latitude = self.position.x, self.position.z
        self.right, self.up, self.forward = (
            world.surface_vector_to_stellar(axis, longitude, latitude, current_datetime)
            for axis in (self.right, self.up, self.forward)
        )
        self.position.x, self.position.y, self.position.z = player_pos
        self.velocity.x, self.velocity.y, self.velocity.z = player_vel
        self.is_bound = False
        return self

    def calculate_stellar_position(self, world: World, world_pos: Vector3) -> Vector3:
        _, up_hat, _ = world.surface_basis(self.position.x, self.position.z, gem.current_environment.date_time)
        distance_from_centre = world.radius + self.position.y
        offset_x, offset_y, offset_z = (component * distance_from_centre for component in up_hat)
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated here.
        return (world_pos[0] + offset_x, world_pos[1] - offset_y, world_pos[2] + offset_z)

    def calculate_stellar_velocity(self, world: World, world_vel: Vector3) -> Vector3:
        east_hat, up_hat, north_hat = world.surface_basis(self.position.x, self.position.z, gem.current_environment.date_time)
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