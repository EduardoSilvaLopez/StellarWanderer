from __future__ import annotations
import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from cmath import pi
import math
import logging

from Galaxies.Politics import political_entity
from Galaxies.Politics.personal_status import PersonalStatus
from Vector3 import Vector3, rotate_2d
from Galaxies.world import World; logger = logging.getLogger(__name__)
from Galaxies.km2 import Km2
from Spaceships.Ship import Ship
import GameEnvironment as gem
if TYPE_CHECKING:
    from Galaxies.world import World


@dataclass
class Position:
    km2: Optional[Km2] = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_vector(self) -> Vector3:
        return Vector3(self.x, self.y, self.z)


@dataclass
class Velocity:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    def as_vector(self) -> Vector3:
        return Vector3(self.x, self.y, self.z)


class Player:
    # Time compression, in ship-seconds per real second. Keypad +/- steps by 10x.
    TIME_SCALE_MIN = 1
    TIME_SCALE_MAX = 1_000_000
    TIME_SCALE_STEP = 10
    BIND_RADIUS_MULTIPLE = 1.1           # bind at or inside this distance from the world's centre, in radii
    UNBIND_RADIUS_MULTIPLE = 1.2         # unbind beyond this distance from the world's centre, in radii
    BRAKING_RADIUS_MULTIPLE = 10         # braking/markers use the world's velocity inside this distance, in radii

    def __init__(self) -> None:
        self.time_scale: int = 1  # Default time scale
        self.right: Vector3 = Vector3(1.0, 0.0, 0.0)
        self.up: Vector3 = Vector3(0.0, 1.0, 0.0)
        self.forward: Vector3 = Vector3(0.0, 0.0, 1.0)

        self.ship: Ship = Ship(self)
        self.ship.laser.firing = False  # Laser firing (SPACE held)

        self.position: Position = Position()
        self.is_bound: bool = False
        self.velocity: Velocity = Velocity()

        self.political_status: dict = {}

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Player:
        from Galaxies.world import World
        ''' Spawn the player in the given environment, just using the first place we find.'''
        self.is_bound = True
        environment.nearest_world.update_surroundings(10, 0, 0, gem.GameEnvironment.EPOCH)
        central_km2 = next(km2 for km2 in environment.nearest_world.km2s if km2.longitude == 0 and km2.latitude == 0)
        self.position.km2 = central_km2
        self.position.x = self.position.km2.longitude + 500
        self.position.y = 10
        self.position.z = self.position.km2.latitude + 500

        self.political_status = {
            political_entity.THOSE_WHO_SHARE: PersonalStatus()
        }
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
        if world.parent_planet:
            planet_index = world.parent_planet.parent_orbit.planets.index(world.parent_planet)
            moon_index = world.index
        else:
            planet_index = world.parent_orbit.planets.index(world)
            moon_index = None

        those_who_share_status = self.political_status[political_entity.THOSE_WHO_SHARE]
        return {
            'time_scale': self.time_scale,
            'stellar_system.x': world.parent_orbit.parent_stellar_system.x,
            'stellar_system.y': world.parent_orbit.parent_stellar_system.y,
            'stellar_system.z': world.parent_orbit.parent_stellar_system.z,
            'orbit.number': world.parent_orbit.number,
            'planet.index': planet_index,
            'moon.index': moon_index,
            'is_bound': self.is_bound,
            'position.x': self.position.x,
            'position.y': self.position.y,
            'position.z': self.position.z,
            'velocity.x': self.velocity.x,
            'velocity.y': self.velocity.y,
            'velocity.z': self.velocity.z,
            'attitude.right': list(self.right),
            'attitude.up': list(self.up),
            'attitude.forward': list(self.forward),
            'velocity.yaw': self.velocity.yaw,
            'velocity.pitch': self.velocity.pitch,
            'velocity.roll': self.velocity.roll,
            'ship': self.ship.serialize(),
            'political_status': {
                'Those-Who-Share': those_who_share_status.serialize()
            }
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
        result.right = Vector3(*loaded_attributes['attitude.right'])
        result.up = Vector3(*loaded_attributes['attitude.up'])
        result.forward = Vector3(*loaded_attributes['attitude.forward'])
        result.velocity.pitch = loaded_attributes['velocity.pitch']
        result.velocity.roll = loaded_attributes.get('velocity.roll', 0.0)
        result.is_bound = loaded_attributes['is_bound']

        if result.is_bound:
            result.position.km2 = gem.current_environment.nearest_world\
                .get_km2_at(result.position.x, result.position.z)

        result.ship = Ship.load(result, loaded_attributes['ship'])

        result.political_status = {}
        from Galaxies.Politics.personal_status import PersonalStatus
        import Galaxies.Politics.political_entity as pem
        for entity_name, values in loaded_attributes['political_status'].items():
            if entity_name == pem.THOSE_WHO_SHARE.name:
                new_status = PersonalStatus.deserialize(loaded_attributes['political_status'][entity_name])
                result.political_status[political_entity.THOSE_WHO_SHARE] = new_status

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
        self.forward, self.right = Vector3.rotate_pair(self.forward, self.right, angle)

    def _pitch(self, angle: float) -> None:
        self.forward, self.up = Vector3.rotate_pair(self.forward, self.up, angle)

    def _roll(self, angle: float) -> None:
        self.right, self.up = Vector3.rotate_pair(self.right, self.up, angle)

    @property
    def yaw(self) -> float:
        """Heading in degrees clockwise from north, from the ship's forward axis."""
        return math.degrees(math.atan2(self.forward[0], self.forward[2])) % 360

    def _up_reference(self, world: World, current_datetime: datetime) -> Vector3:
        """Local "up" direction (opposite of direction_down); shared by pitch_angle and roll_angle."""
        return -self.direction_down(world, current_datetime)

    def pitch_angle(self, world: World, current_datetime: datetime) -> float:
        """Nose-up angle in degrees above the local horizon."""
        up_reference = self._up_reference(world, current_datetime)
        return math.degrees(math.asin(max(-1.0, min(1.0, self.forward.dot(up_reference)))))

    def roll_angle(self, world: World, current_datetime: datetime) -> float:
        """Right-wing-down angle in degrees relative to the local horizon."""
        up_reference = self._up_reference(world, current_datetime)
        return math.degrees(math.atan2(-self.right.dot(up_reference), self.up.dot(up_reference)))

    def direction_down(self, world: World, current_datetime: datetime) -> Vector3:
        """Unit vector from the ship towards the planet's surface, in the active frame."""
        if self.is_bound:
            return Vector3(0.0, -1.0, 0.0)
        centre = world.calculate_stellar_position(current_datetime)
        return (centre - self.position.as_vector()).normalized()

    def direction_to_star(self, world: World, current_datetime: datetime) -> Vector3:
        if self.is_bound:
            return world.calculate_star_position(self, current_datetime)
        return -self.position.as_vector()

    def direction_to_world(self, target: World, current_datetime: datetime) -> Vector3:
        """Vector from the ship to the centre of `target`, in the active frame (the same
        frame as direction_to_star: surface east/up/north when bound, stellar when unbound)."""
        target_position = target.calculate_stellar_position(current_datetime)
        if not self.is_bound:
            return target_position - self.position.as_vector()
        world = gem.current_environment.nearest_world
        east_hat, up_hat, north_hat = world.surface_basis(self.position.x, self.position.z, current_datetime)
        centre = world.calculate_stellar_position(current_datetime)
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated.
        player_position = Vector3(centre.x, -centre.y, centre.z) + up_hat * (world.radius + self.position.y)
        relative = Vector3(target_position.x, -target_position.y, target_position.z) - player_position
        return Vector3(relative.dot(east_hat), relative.dot(up_hat), relative.dot(north_hat))

    def camera_components(self, vector: Vector3) -> Vector3:
        """Components of a direction along the ship's right, up and forward axes."""
        return Vector3(vector.dot(self.right), vector.dot(self.up), vector.dot(self.forward))

    def camera_matrix(self) -> list:
        """Column-major 4x4 for glMultMatrixf, mapping the ship's axes to OpenGL's eye axes."""
        rows = (self.right, self.up, -self.forward)
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
        if not self.is_bound:
            gem.current_environment.refresh_nearest_world(self.position.as_vector())
        world = gem.current_environment.nearest_world
        if self.is_bound and self.position.y + world.radius > Player.UNBIND_RADIUS_MULTIPLE * world.radius:
            self.unbind_from(world)
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
            reference = self.velocity_reference_frame()
            relative = self.velocity.as_vector() - reference
            speed = relative.length()
            if speed > 0:
                decel = min(self.ship.BRAKE_ACC * delta_time, speed)
                scale = (speed - decel) / speed
                self.velocity.x = reference.x + relative.x * scale
                self.velocity.y = reference.y + relative.y * scale
                self.velocity.z = reference.z + relative.z * scale
        elif self.is_bound:
            yaw = math.radians(self.yaw)
            world_accel_x, world_accel_z = rotate_2d(longitude_accel_input, latitude_accel_input, yaw)

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
        # NOTE: intentionally yaw-only. Binding snaps the ship level, discarding any
        # pitch/roll it had while unbound — a ship always lands/binds level. This is
        # NOT a bug and is asymmetric with unbind_from below by design; see CLAUDE.md
        # "Ship Attitude and Controls".
        logger.info(f"Arriving to {world.name}.")

        current_datetime = gem.current_environment.date_time
        stellar_pos = self.position.as_vector()
        stellar_vel = self.velocity.as_vector()
        longitude, altitude, latitude = world.stellar_to_surface_position(stellar_pos, current_datetime)
        basis = world.surface_basis(longitude, latitude, current_datetime)
        surface_vel = world.stellar_to_surface_velocity_with_basis(stellar_vel, altitude, latitude, current_datetime, basis)

        self.position.x, self.position.y, self.position.z = longitude, altitude, latitude
        self.velocity.x, self.velocity.y, self.velocity.z = surface_vel
        forward_surface = world.stellar_vector_to_surface_with_basis(self.forward, basis)
        yaw = math.atan2(forward_surface[0], forward_surface[2])
        self.forward, self.right = Vector3.rotate_pair(Vector3(0.0, 0.0, 1.0), Vector3(1.0, 0.0, 0.0), yaw)
        self.up = Vector3(0.0, 1.0, 0.0)
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

        self.ship.set_notification(f"Arriving to {world.name}, {self.get_title()} Pilot.")
        self.is_bound = True
        return self

    def _distance_to_world_centre(self, world: World) -> float:
        return math.dist(self.position.as_vector(), world.calculate_stellar_position(gem.current_environment.date_time))

    def velocity_reference_frame(self) -> Vector3:
        """Velocity frame that linear braking (S) and the prograde/retrograde HUD
        markers are both measured against: zero (stellar frame) while bound or
        farther than BRAKING_RADIUS_MULTIPLE world radii from the nearest world's centre;
        otherwise the nearest world's own stellar velocity, so braking/markers are relative to
        that world instead of the star. See CLAUDE.md "Ship Attitude and Controls"."""
        world = gem.current_environment.nearest_world
        if self.is_bound or self._distance_to_world_centre(world) >= Player.BRAKING_RADIUS_MULTIPLE * world.radius:
            return Vector3(0.0, 0.0, 0.0)
        return world.calculate_stellar_velocity(gem.current_environment.date_time)

    def speed_relative_to_world(self, world: World) -> float:
        """Speed relative to the world, in m/s. While bound the velocity is already surface-relative."""
        velocity = self.velocity.as_vector()
        if self.is_bound:
            return velocity.length()
        world_velocity = world.calculate_stellar_velocity(gem.current_environment.date_time)
        return math.dist(velocity, world_velocity)

    def altitude_above_surface(self, world: World) -> float:
        if self.is_bound:
            return self.position.y
        return self._distance_to_world_centre(world) - world.radius

    def unbind_from(self, world: World) -> Player:
        # NOTE: intentionally preserves the full right/up/forward attitude, round-tripping
        # all three axes through World.surface_vector_to_stellar — the counterpart to
        # bind_to's intentional yaw-only snap above. This is NOT a bug; see CLAUDE.md
        # "Ship Attitude and Controls".
        logger.info(f"Leaving {world.name}.")

        current_datetime = gem.current_environment.date_time
        basis = world.surface_basis(self.position.x, self.position.z, current_datetime)

        world_pos = world.calculate_stellar_position(current_datetime)
        player_pos = self.calculate_stellar_position(world, world_pos, basis)
        logger.info(f"Stellar positions:")
        logger.info(f"             |        X        |        Y        |        Z")
        logger.info(f"        World|  {world_pos[0]}  |  {world_pos[1]}  |  {world_pos[2]}")
        logger.info(f"       Player|  {player_pos[0]}  |  {player_pos[1]}  |  {player_pos[2]}")

        world_vel = world.calculate_stellar_velocity(current_datetime)
        player_vel = self.calculate_stellar_velocity(world, world_vel, basis)
        logger.info(f"Stellar velocities:")
        logger.info(f"             |        X        |        Y        |        Z")
        logger.info(f"        World|  {world_vel[0]}  |  {world_vel[1]}  |  {world_vel[2]}")
        logger.info(f"       Player|  {player_vel[0]}  |  {player_vel[1]}  |  {player_vel[2]}")

        self.right, self.up, self.forward = (
            world.surface_vector_to_stellar_with_basis(axis, basis)
            for axis in (self.right, self.up, self.forward)
        )
        self.position.x, self.position.y, self.position.z = player_pos
        self.velocity.x, self.velocity.y, self.velocity.z = player_vel

        self.ship.set_notification(f"Leaving {world.name}, {self.get_title()} Pilot.")
        self.is_bound = False
        return self

    def calculate_stellar_position(self, world: World, world_pos: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        _, up_hat, _ = basis
        offset = up_hat * (world.radius + self.position.y)
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated here.
        return Vector3(world_pos.x + offset.x, world_pos.y - offset.y, world_pos.z + offset.z)

    def calculate_stellar_velocity(self, world: World, world_vel: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        east_hat, up_hat, north_hat = basis
        spin_speed = world.spin_speed_at(self.position.y, self.position.z)

        # Star-centred basis: Y is opposite to the orbital motion, so world_vel's Y is negated first.
        world_vel_basis = Vector3(world_vel.x, -world_vel.y, world_vel.z)
        total = world_vel_basis + east_hat * (spin_speed + self.velocity.x) + up_hat * self.velocity.y + north_hat * self.velocity.z
        return Vector3(total.x, -total.y, total.z)

    def get_title(self) -> str:
        from Galaxies.Politics.political_entity import PoliticalEntity
        entity: PoliticalEntity = gem.current_environment.nearest_system.political_entity
        from Galaxies.Politics.personal_status import PersonalStatus
        status: PersonalStatus = self.political_status[entity]
        return entity.title_for(status.reputation)

current_player: Player = None