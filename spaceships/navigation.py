"""How the ship moves relative to the body it is near (a world or the star): binding to a world's surface, thrust and
braking, directions."""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Tuple
import logging
import math

from common.vector3 import Vector3, rotate_2d
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.body import Body
    from galaxies.world import World
    from .ship import Ship

logger = logging.getLogger(__name__)


class Navigation:
    """Position and velocity updates and everything measured against the fixed body (`GameEnvironment.fixed_body`:
    a world or the star, or None outside every fixed zone).

    The fixed zone is the sphere of FIXED_ZONE_RADIUS_MULTIPLE radii around a body's centre. The fixed body is the
    nearest body whose fixed zone holds the ship (see `GameEnvironment.refresh_fixed_body`). Being fixed is what makes
    the ship's coordinates and braking relative to that body: while unbound, the position is always the star's frame,
    and braking is relative to the fixed body only inside its fixed zone (the star is at rest, so near it the two are
    the same). Outside every fixed zone, the body the instruments show is `GameEnvironment.targeted_body` instead.
    Braking is by three independent engines, one per ship axis, bound or not (see `_brake`).

    Bind, unbind and braking thresholds are distances from the body's centre in radii (1.0 = surface). The bound
    altitude bar spans 0 to (UNBIND_RADIUS_MULTIPLE - 1.0) × radius altitude; the unbound meter spans 1.0 to
    FIXED_ZONE_RADIUS_MULTIPLE radii from the centre. Only a world can be bound to: the star is never bound to (the
    ship is not expected to get that near), however close the ship is to it.

    `_bind_to` and `_unbind_from` are deliberately asymmetric: `_bind_to` snaps the ship level (yaw only; pitch and
    roll are discarded), because a ship always starts level on a surface. `_unbind_from` keeps the full attitude,
    round-tripping the three axes through `World.surface_vector_to_stellar`, so free flight keeps whatever attitude
    the ship had while bound. Do not "fix" this to be symmetric.
    """

    BIND_RADIUS_MULTIPLE = 1.1  # bind at or inside this distance from the world's centre, in radii
    UNBIND_RADIUS_MULTIPLE = 1.2  # unbind beyond this distance from the world's centre, in radii
    FIXED_ZONE_RADIUS_MULTIPLE = 10  # the fixed zone: inside this distance from a body's centre, in radii
    COLLISION_BRAKE_FRACTION = 1.0 / 3.0  # share of BRAKE_ACC assumed available when judging a collision

    def __init__(self, ship: Ship) -> None:
        self.ship: Ship = ship

    # region Angles and directions
    def _up_reference(self, body: Body, current_datetime: datetime) -> Vector3:
        return -self.direction_down(body, current_datetime)

    def pitch_angle(self, body: Body, current_datetime: datetime) -> float:
        """Nose-up angle in degrees above the local horizon."""
        up_reference = self._up_reference(body, current_datetime)
        return math.degrees(math.asin(max(-1.0, min(1.0, self.ship.attitude.forward.dot(up_reference)))))

    def roll_angle(self, body: Body, current_datetime: datetime) -> float:
        """Right-wing-down angle in degrees relative to the local horizon."""
        up_reference = self._up_reference(body, current_datetime)
        attitude = self.ship.attitude
        return math.degrees(math.atan2(-attitude.right.dot(up_reference), attitude.up.dot(up_reference)))

    def direction_down(self, body: Body, current_datetime: datetime) -> Vector3:
        """Unit vector from the ship towards the body's surface, in the active frame."""
        if self.ship.is_bound:
            return Vector3(0.0, -1.0, 0.0)
        centre = body.calculate_stellar_position(current_datetime)
        return (centre - self.ship.position.as_vector()).normalized()

    def direction_to_star(self, body: Body, current_datetime: datetime) -> Vector3:
        if self.ship.is_bound:
            return body.calculate_star_position(self.ship, current_datetime)  # bound: the body is a world
        return -self.ship.position.as_vector()

    def direction_to_body(self, target: Body, current_datetime: datetime) -> Vector3:
        return self.direction_to_point(target.calculate_stellar_position(current_datetime), current_datetime)

    def direction_to_point(self, point: Vector3, current_datetime: datetime) -> Vector3:
        """Vector from the ship to a stellar-frame point, in the active frame: surface east/up/north while bound."""
        if not self.ship.is_bound:
            return point - self.ship.position.as_vector()
        world = gem.current_environment.fixed_world
        basis = world.surface_basis(self.ship.position.x, self.ship.position.z, current_datetime)
        ship_position = self._stellar_position_from_surface(world, world.calculate_stellar_position(current_datetime), basis)
        relative = point - ship_position
        relative = Vector3(relative.x, -relative.y, relative.z)  # the surface basis has Y opposite to the orbital motion
        east_hat, up_hat, north_hat = basis
        return Vector3(relative.dot(east_hat), relative.dot(up_hat), relative.dot(north_hat))

    def sky_rotation(self, current_datetime: datetime) -> Tuple[Vector3, Vector3, Vector3]:
        """Where the stellar frame's x, y and z axes point in the active frame: what turns a direction to something so far away
        that the ship's position does not matter (the sky behind everything) into the active frame. Unbound it is the same
        frame, and the axes are their own; bound, they go through the surface basis, as in `direction_to_point`, so the sky
        turns with the world's spin."""
        if not self.ship.is_bound:
            return Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)
        world = gem.current_environment.fixed_world
        east_hat, up_hat, north_hat = world.surface_basis(self.ship.position.x, self.ship.position.z, current_datetime)
        # The surface basis has Y opposite to the orbital motion (see direction_to_point).
        flipped_x, flipped_y, flipped_z = Vector3(1.0, 0.0, 0.0), Vector3(0.0, -1.0, 0.0), Vector3(0.0, 0.0, 1.0)
        return (
            Vector3(flipped_x.dot(east_hat), flipped_x.dot(up_hat), flipped_x.dot(north_hat)),
            Vector3(flipped_y.dot(east_hat), flipped_y.dot(up_hat), flipped_y.dot(north_hat)),
            Vector3(flipped_z.dot(east_hat), flipped_z.dot(up_hat), flipped_z.dot(north_hat)),
        )

    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """The ship's position in the stellar frame, whether bound or not."""
        if not self.ship.is_bound:
            return self.ship.position.as_vector()
        world = gem.current_environment.fixed_world
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
            environment.refresh_fixed_body(ship.position.as_vector())
        body = environment.fixed_body  # None outside every fixed zone: then there is nothing to bind to
        if ship.is_bound and ship.position.y + body.radius > Navigation.UNBIND_RADIUS_MULTIPLE * body.radius:
            self._unbind_from(body)
        elif (not ship.is_bound and body is not None and body.is_world  # the star is never bound to
                and self.distance_to_body_centre(body) <= Navigation.BIND_RADIUS_MULTIPLE * body.radius):
            self._bind_to(body)

        if ship.is_bound:
            world = environment.fixed_world
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
            self._brake(delta_time)
        elif ship.is_bound:
            world_accel_x, world_accel_z = rotate_2d(longitude_accel_input, latitude_accel_input, math.radians(attitude.yaw))
            accel = Vector3(
                world_accel_x * ship.RIGHT_LEFT_ACC,
                altitude_accel_input * ship.UP_DOWN_ACC,
                world_accel_z * ship.FORWARD_BACKWARD_ACC,
            )
            ship.velocity.add_vector(accel * delta_time)
            self.ship.energy -= 5e4 * sum(accel) * delta_time
        else:
            accel = (
                attitude.right * (longitude_accel_input * ship.RIGHT_LEFT_ACC)
                + attitude.forward * (latitude_accel_input * ship.FORWARD_BACKWARD_ACC)
                + attitude.up * (altitude_accel_input * ship.UP_DOWN_ACC)
            )
            ship.velocity.add_vector(accel * delta_time)
            self.ship.energy -= 5e4 * sum(accel) * delta_time

    def _brake(self, delta_time: float) -> None:
        """Brakes against the velocity of the reference frame (`velocity_reference_frame`) with three independent engines,
        one on each of the ship's axes, the ones the thrust keys use: right, up and forward (while bound, right and forward
        are horizontal, turned by the yaw). Each engine takes up to BRAKE_ACC off its own component, whatever the others do:
        a small component stops as fast as a large one, and the ship is at rest relative to the frame when the slowest
        engine is done. Each engine's change of speed costs 5e4 energy per m/s."""
        ship = self.ship
        reference = self.velocity_reference_frame()
        relative = ship.velocity.as_vector() - reference
        if ship.is_bound:
            yaw = math.radians(ship.attitude.yaw)
            right_x, right_z = rotate_2d(1.0, 0.0, yaw)
            forward_x, forward_z = rotate_2d(0.0, 1.0, yaw)
            axes = (Vector3(right_x, 0.0, right_z), Vector3(0.0, 1.0, 0.0), Vector3(forward_x, 0.0, forward_z))
        else:
            axes = (ship.attitude.right, ship.attitude.up, ship.attitude.forward)

        braked = relative
        for axis in axes:
            component = relative.dot(axis)
            decel = min(ship.BRAKE_ACC * delta_time, abs(component))
            braked = braked - axis * math.copysign(decel, component)
            ship.energy -= 5e4 * decel
        ship.velocity.set_vector(reference + braked)

    def _update_position(self, delta_time: float) -> None:
        ship = self.ship
        ship.position.add_vector(ship.velocity.as_vector() * delta_time)
        if not ship.is_bound:
            return

        half_turn = math.pi * gem.current_environment.fixed_world.radius  # half the equator
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

    def _bind_to(self, world: World) -> Navigation:
        # Intentionally yaw-only: binding snaps the ship level, unlike _unbind_from, which keeps the attitude.
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

    def _unbind_from(self, world: World) -> Navigation:
        # Intentionally keeps the full attitude: unlike _bind_to, which snaps the ship level.
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
    def distance_to_body_centre(self, body: Body) -> float:
        return math.dist(self.ship.position.as_vector(), body.calculate_stellar_position(gem.current_environment.date_time))

    def altitude_above_surface(self, body: Body) -> float:
        if self.ship.is_bound:
            return self.ship.position.y
        return self.distance_to_body_centre(body) - body.radius

    def in_fixed_zone(self, body: Body) -> bool:
        return not self.ship.is_bound and self.distance_to_body_centre(body) < Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius

    def velocity_reference_frame(self) -> Vector3:
        """The velocity that braking (S) and the prograde/retrograde markers are measured against: the fixed body's
        inside its fixed zone, otherwise the star's (zero)."""
        body = gem.current_environment.fixed_body
        if body is None or not self.in_fixed_zone(body):
            return Vector3(0.0, 0.0, 0.0)
        return body.calculate_stellar_velocity(gem.current_environment.date_time)

    def _relative_to_body(self, body: Body) -> Tuple[Vector3, Vector3]:
        current_datetime = gem.current_environment.date_time
        return (
            self.ship.position.as_vector() - body.calculate_stellar_position(current_datetime),
            self.ship.velocity.as_vector() - body.calculate_stellar_velocity(current_datetime),
        )

    def approach_speed(self, body: Body) -> float:
        """Rate at which the distance to the body's centre shrinks, in m/s: positive approaching. Sideways motion
        does not count. Meaningful while unbound."""
        relative_position, relative_velocity = self._relative_to_body(body)
        distance = relative_position.length()
        if distance == 0.0:
            return 0.0
        return -relative_position.dot(relative_velocity) / distance

    def drift_speed(self, body: Body) -> float:
        """Speed relative to the body across the line to its centre, in m/s: what is left of the relative speed once the
        approach is taken out. Meaningful while unbound."""
        _, relative_velocity = self._relative_to_body(body)
        approach = self.approach_speed(body)
        return math.sqrt(max(0.0, relative_velocity.dot(relative_velocity) - approach * approach))

    def collision_warning(self, body: Body) -> bool:
        """True if the ship, on its straight line relative to the body, would reach the surface even braking
        with only COLLISION_BRAKE_FRACTION of BRAKE_ACC. Sideways dodging is not considered."""
        if self.ship.is_bound:
            return False
        relative_position, relative_velocity = self._relative_to_body(body)
        speed = relative_velocity.length()
        if speed == 0.0:
            return False
        direction = relative_velocity * (1.0 / speed)
        along = relative_position.dot(direction)  # negative while approaching
        beyond_surface = relative_position.dot(relative_position) - body.radius ** 2
        if beyond_surface <= 0.0:
            return True
        discriminant = along * along - beyond_surface
        if along >= 0.0 or discriminant < 0.0:
            return False  # moving away, or the line misses the world
        entry_distance = -along - math.sqrt(discriminant)
        stopping_distance = speed ** 2 / (2.0 * self.ship.BRAKE_ACC * Navigation.COLLISION_BRAKE_FRACTION)
        return entry_distance <= stopping_distance

    def altitude_warning(self) -> bool:
        """True while bound and falling so fast that the ground comes before a stop, braking with only
        COLLISION_BRAKE_FRACTION of BRAKE_ACC (the same judgement as collision_warning, on the vertical)."""
        if not self.ship.is_bound or self.ship.velocity.y >= 0.0:
            return False
        stopping_distance = self.ship.velocity.y ** 2 / (2.0 * self.ship.BRAKE_ACC * Navigation.COLLISION_BRAKE_FRACTION)
        return self.ship.position.y <= stopping_distance
    # endregion
