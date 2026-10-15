"""How the ship moves relative to the world it is at: binding to a surface, thrust and braking, directions."""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Tuple
import logging
import math

from vector3 import Vector3, rotate_2d
import game_environment as gem

if TYPE_CHECKING:
    from Galaxies.world import World
    from .ship import Ship

logger = logging.getLogger(__name__)


class Navigation:
    """Position and velocity updates and everything measured against the nearest world.

    Braking (S) decelerates linear velocity on all three axes. While unbound it is relative to the star, except
    inside the braking zone (BRAKING_RADIUS_MULTIPLE world radii from the nearest world's centre), where it is
    relative to that world.

    Bind, unbind and braking thresholds are distances from the world's centre in radii (1.0 = surface). The bound
    altitude bar spans 0 to (UNBIND_RADIUS_MULTIPLE - 1.0) × radius altitude; the unbound meter spans 1.0 to
    BRAKING_RADIUS_MULTIPLE radii from the centre.

    `bind_to` and `unbind_from` are deliberately asymmetric: `bind_to` snaps the ship level (yaw only; pitch and
    roll are discarded), because a ship always starts level on a surface. `unbind_from` keeps the full attitude,
    round-tripping the three axes through `World.surface_vector_to_stellar`, so free flight keeps whatever attitude
    the ship had while bound. Do not "fix" this to be symmetric.
    """

    BIND_RADIUS_MULTIPLE = 1.1           # bind at or inside this distance from the world's centre, in radii
    UNBIND_RADIUS_MULTIPLE = 1.2         # unbind beyond this distance from the world's centre, in radii
    BRAKING_RADIUS_MULTIPLE = 10         # braking/markers use the world's velocity inside this distance, in radii
    COLLISION_BRAKE_FRACTION = 0.5       # share of BRAKE_ACC assumed available when judging a collision

    def __init__(self, ship: Ship) -> None:
        self.ship: Ship = ship

    # region Angles and directions
    def _up_reference(self, world: World, current_datetime: datetime) -> Vector3:
        return -self.direction_down(world, current_datetime)

    def pitch_angle(self, world: World, current_datetime: datetime) -> float:
        """Nose-up angle in degrees above the local horizon."""
        up_reference = self._up_reference(world, current_datetime)
        return math.degrees(math.asin(max(-1.0, min(1.0, self.ship.attitude.forward.dot(up_reference)))))

    def roll_angle(self, world: World, current_datetime: datetime) -> float:
        """Right-wing-down angle in degrees relative to the local horizon."""
        up_reference = self._up_reference(world, current_datetime)
        attitude = self.ship.attitude
        return math.degrees(math.atan2(-attitude.right.dot(up_reference), attitude.up.dot(up_reference)))

    def direction_down(self, world: World, current_datetime: datetime) -> Vector3:
        """Unit vector from the ship towards the planet's surface, in the active frame."""
        if self.ship.is_bound:
            return Vector3(0.0, -1.0, 0.0)
        centre = world.calculate_stellar_position(current_datetime)
        return (centre - self.ship.position.as_vector()).normalized()

    def direction_to_star(self, world: World, current_datetime: datetime) -> Vector3:
        if self.ship.is_bound:
            return world.calculate_star_position(self.ship, current_datetime)
        return -self.ship.position.as_vector()

    def direction_to_world(self, target: World, current_datetime: datetime) -> Vector3:
        return self.direction_to_point(target.calculate_stellar_position(current_datetime), current_datetime)

    def direction_to_point(self, point: Vector3, current_datetime: datetime) -> Vector3:
        """Vector from the ship to a stellar-frame point, in the active frame: surface east/up/north while bound."""
        if not self.ship.is_bound:
            return point - self.ship.position.as_vector()
        world = gem.current_environment.nearest_world
        basis = world.surface_basis(self.ship.position.x, self.ship.position.z, current_datetime)
        ship_position = self._stellar_position_from_surface(world, world.calculate_stellar_position(current_datetime), basis)
        relative = point - ship_position
        relative = Vector3(relative.x, -relative.y, relative.z)  # the surface basis has Y opposite to the orbital motion
        east_hat, up_hat, north_hat = basis
        return Vector3(relative.dot(east_hat), relative.dot(up_hat), relative.dot(north_hat))

    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """The ship's position in the stellar frame, whether bound or not."""
        if not self.ship.is_bound:
            return self.ship.position.as_vector()
        world = gem.current_environment.nearest_world
        basis = world.surface_basis(self.ship.position.x, self.ship.position.z, current_datetime)
        return self._stellar_position_from_surface(world, world.calculate_stellar_position(current_datetime), basis)
    # endregion

    # region Movement
    def update_position_and_velocity(
            self,
            delta_time: float,
            longitude_accel_input: float,
            altitude_accel_input: float,
            latitude_accel_input: float,
            braking: bool = False
            ) -> Navigation:
        ship = self.ship
        self._update_velocity(delta_time, longitude_accel_input, altitude_accel_input, latitude_accel_input, braking)
        self._update_position(delta_time)

        environment = gem.current_environment
        if not ship.is_bound:
            environment.refresh_nearest_world(ship.position.as_vector())
        world = environment.nearest_world
        if ship.is_bound and ship.position.y + world.radius > Navigation.UNBIND_RADIUS_MULTIPLE * world.radius:
            self.unbind_from(world)
        elif not ship.is_bound and self.distance_to_world_centre(world) <= Navigation.BIND_RADIUS_MULTIPLE * world.radius:
            self.bind_to(world)

        if ship.is_bound:
            km2 = world.get_km2_at(ship.position.x, ship.position.z)
            if km2 is None or km2 != ship.position.km2:
                world.update_surroundings(ship.position.y, ship.position.x, ship.position.z, environment.date_time)
                km2 = world.get_km2_at(ship.position.x, ship.position.z)
            ship.position.km2 = km2
        return self

    def _update_velocity(self, delta_time: float, longitude_accel_input: float, altitude_accel_input: float, latitude_accel_input: float, braking: bool) -> None:
        ship = self.ship
        attitude = ship.attitude
        if braking:
            reference = self.velocity_reference_frame()
            relative = ship.velocity.as_vector() - reference
            speed = relative.length()
            if speed > 0:
                decel = min(ship.BRAKE_ACC * delta_time, speed)
                ship.velocity.set_vector(reference + relative * ((speed - decel) / speed))
        elif ship.is_bound:
            world_accel_x, world_accel_z = rotate_2d(longitude_accel_input, latitude_accel_input, math.radians(attitude.yaw))
            accel = Vector3(
                world_accel_x * ship.RIGHT_LEFT_ACC,
                altitude_accel_input * ship.UP_DOWN_ACC,
                world_accel_z * ship.FORWARD_BACKWARD_ACC,
            )
            ship.velocity.add_vector(accel * delta_time)
        else:
            accel = (
                attitude.right * (longitude_accel_input * ship.RIGHT_LEFT_ACC)
                + attitude.forward * (latitude_accel_input * ship.FORWARD_BACKWARD_ACC)
                + attitude.up * (altitude_accel_input * ship.UP_DOWN_ACC)
            )
            ship.velocity.add_vector(accel * delta_time)

    def _update_position(self, delta_time: float) -> None:
        ship = self.ship
        ship.position.add_vector(ship.velocity.as_vector() * delta_time)
        if not ship.is_bound:
            return

        half_turn = math.pi * gem.current_environment.nearest_world.radius  # half the equator
        if ship.position.x < -half_turn:  # crossing the anti-meridian
            ship.position.x += half_turn * 2
        elif ship.position.x > half_turn:
            ship.position.x -= half_turn * 2
        ship.position.y = max(ship.HEIGHT, ship.position.y)
        ship.position.z = max(-half_turn / 2, min(half_turn / 2, ship.position.z))  # between the poles
        ship.velocity.y = max(-(ship.position.y - ship.HEIGHT), ship.velocity.y)  # no descent faster than the altitude left
    # endregion

    # region Binding to a world
    @staticmethod
    def _log_vectors(title: str, rows: Dict[str, Tuple[float, float, float]]) -> None:
        logger.info(f"{title}:")
        logger.info(f"{'':>16}|        X        |        Y        |        Z")
        for label, vector in rows.items():
            logger.info(f"{label:>16}|  {vector[0]}  |  {vector[1]}  |  {vector[2]}")

    def bind_to(self, world: World) -> Navigation:
        # Intentionally yaw-only: binding snaps the ship level, unlike unbind_from, which keeps the attitude.
        logger.info(f"Arriving to {world.name}.")

        ship = self.ship
        attitude = ship.attitude
        current_datetime = gem.current_environment.date_time
        stellar_pos = ship.position.as_vector()
        stellar_vel = ship.velocity.as_vector()
        local_pos = world.stellar_to_surface_position(stellar_pos, current_datetime)
        longitude, altitude, latitude = local_pos
        basis = world.surface_basis(longitude, latitude, current_datetime)
        surface_vel = world.stellar_to_surface_velocity_with_basis(stellar_vel, altitude, latitude, current_datetime, basis)

        ship.position.set_vector(local_pos)
        ship.velocity.set_vector(surface_vel)
        forward_surface = world.stellar_vector_to_surface_with_basis(attitude.forward, basis)
        yaw = math.atan2(forward_surface[0], forward_surface[2])
        attitude.forward, attitude.right = Vector3.rotate_pair(Vector3(0.0, 0.0, 1.0), Vector3(1.0, 0.0, 0.0), yaw)
        attitude.up = Vector3(0.0, 1.0, 0.0)
        attitude.yaw_rate = 0.0
        attitude.pitch_rate = 0.0
        attitude.roll_rate = 0.0

        self._log_vectors("Positions", {
            "World (stellar)": world.calculate_stellar_position(current_datetime),
            "Ship (stellar)": stellar_pos,
            "Ship (local)": local_pos,
        })
        self._log_vectors("Velocities", {
            "World (stellar)": world.calculate_stellar_velocity(current_datetime),
            "Ship (stellar)": stellar_vel,
            "Ship (local)": surface_vel,
        })

        ship.notification.set(f"Arriving to {world.name}, {ship.owner.get_title()} Pilot.")
        ship.is_bound = True
        return self

    def unbind_from(self, world: World) -> Navigation:
        # Intentionally keeps the full attitude: unlike bind_to, which snaps the ship level.
        logger.info(f"Leaving {world.name}.")

        ship = self.ship
        attitude = ship.attitude
        current_datetime = gem.current_environment.date_time
        basis = world.surface_basis(ship.position.x, ship.position.z, current_datetime)

        world_pos = world.calculate_stellar_position(current_datetime)
        world_vel = world.calculate_stellar_velocity(current_datetime)
        ship_pos = self._stellar_position_from_surface(world, world_pos, basis)
        ship_vel = self._stellar_velocity_from_surface(world, world_vel, basis)
        self._log_vectors("Positions", {"World (stellar)": world_pos, "Ship (stellar)": ship_pos})
        self._log_vectors("Velocities", {"World (stellar)": world_vel, "Ship (stellar)": ship_vel})

        attitude.right, attitude.up, attitude.forward = (
            world.surface_vector_to_stellar_with_basis(axis, basis)
            for axis in (attitude.right, attitude.up, attitude.forward)
        )
        ship.position.set_vector(ship_pos)
        ship.velocity.set_vector(ship_vel)

        ship.notification.set(f"Leaving {world.name}, {ship.owner.get_title()} Pilot.")
        ship.is_bound = False
        return self

    def _stellar_position_from_surface(self, world: World, world_pos: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        _, up_hat, _ = basis
        offset = up_hat * (world.radius + self.ship.position.y)
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated here.
        return Vector3(world_pos.x + offset.x, world_pos.y - offset.y, world_pos.z + offset.z)

    def _stellar_velocity_from_surface(self, world: World, world_vel: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        east_hat, up_hat, north_hat = basis
        position = self.ship.position
        velocity = self.ship.velocity
        spin_speed = world.spin_speed_at(position.y, position.z)

        # Star-centred basis: Y is opposite to the orbital motion, so world_vel's Y is negated first.
        world_vel_basis = Vector3(world_vel.x, -world_vel.y, world_vel.z)
        total = world_vel_basis + east_hat * (spin_speed + velocity.x) + up_hat * velocity.y + north_hat * velocity.z
        return Vector3(total.x, -total.y, total.z)
    # endregion

    # region Distances, braking and collision
    def distance_to_world_centre(self, world: World) -> float:
        return math.dist(self.ship.position.as_vector(), world.calculate_stellar_position(gem.current_environment.date_time))

    def altitude_above_surface(self, world: World) -> float:
        if self.ship.is_bound:
            return self.ship.position.y
        return self.distance_to_world_centre(world) - world.radius

    def in_braking_zone(self, world: World) -> bool:
        return not self.ship.is_bound and self.distance_to_world_centre(world) < Navigation.BRAKING_RADIUS_MULTIPLE * world.radius

    def velocity_reference_frame(self) -> Vector3:
        """The velocity that braking (S) and the prograde/retrograde markers are measured against: the nearest
        world's inside the braking zone, otherwise the star's (zero)."""
        world = gem.current_environment.nearest_world
        if not self.in_braking_zone(world):
            return Vector3(0.0, 0.0, 0.0)
        return world.calculate_stellar_velocity(gem.current_environment.date_time)

    def _relative_to_world(self, world: World) -> Tuple[Vector3, Vector3]:
        current_datetime = gem.current_environment.date_time
        return (
            self.ship.position.as_vector() - world.calculate_stellar_position(current_datetime),
            self.ship.velocity.as_vector() - world.calculate_stellar_velocity(current_datetime),
        )

    def approach_speed(self, world: World) -> float:
        """Rate at which the distance to the world's centre shrinks, in m/s: positive approaching. Sideways motion
        does not count. Meaningful while unbound."""
        relative_position, relative_velocity = self._relative_to_world(world)
        distance = relative_position.length()
        if distance == 0.0:
            return 0.0
        return -relative_position.dot(relative_velocity) / distance

    def collision_warning(self, world: World) -> bool:
        """True if the ship, on its straight line relative to the world, would reach the surface even braking
        with only COLLISION_BRAKE_FRACTION of BRAKE_ACC. Sideways dodging is not considered."""
        if self.ship.is_bound:
            return False
        relative_position, relative_velocity = self._relative_to_world(world)
        speed = relative_velocity.length()
        if speed == 0.0:
            return False
        direction = relative_velocity * (1.0 / speed)
        along = relative_position.dot(direction)  # negative while approaching
        beyond_surface = relative_position.dot(relative_position) - world.radius ** 2
        if beyond_surface <= 0.0:
            return True
        discriminant = along * along - beyond_surface
        if along >= 0.0 or discriminant < 0.0:
            return False  # moving away, or the line misses the world
        entry_distance = -along - math.sqrt(discriminant)
        stopping_distance = speed ** 2 / (2.0 * self.ship.BRAKE_ACC * Navigation.COLLISION_BRAKE_FRACTION)
        return entry_distance <= stopping_distance
    # endregion
