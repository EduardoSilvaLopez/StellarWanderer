"""How the ship moves relative to the body it is near (a world or the star): binding to a world's surface, thrust and
braking, directions."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, Tuple
import logging
import math

from common.dialogs.messages import Message, show_message
from common.frame_watch import frame_watch
from common.vector3 import Vector3, rotate_2d
from galaxies import kepler
from galaxies.rocky_world import RockyWorld
from galaxies.world import World
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.body import Body
    from .ship import Ship

logger = logging.getLogger(__name__)


class CoastState(NamedTuple):
    """Where an unbound ship in a body's fixed zone was at the end of its last frame, relative to that body, with the
    ship's stellar position and velocity then: what the next frame propagates from (see Navigation._move_unbound)."""
    body: Body
    date_time: datetime
    relative_position: Vector3
    relative_velocity: Vector3
    position: Vector3
    velocity: Vector3


class Navigation:
    """Position and velocity updates and everything measured against the fixed body (`GameEnvironment.fixed_body`:
    a world or the star, or None outside every fixed zone).

    The fixed zone is the sphere of FIXED_ZONE_RADIUS_MULTIPLE radii around a body's centre. The fixed body is the
    nearest body whose fixed zone holds the ship (see `GameEnvironment.refresh_fixed_body`). Being fixed is what makes
    the ship's coordinates relative to that body: while unbound, the position is always the star's frame. Braking is
    relative to the fixed body inside its fixed zone and, outside every fixed zone, to the body the instruments show,
    `GameEnvironment.targeted_body`: braking to rest with respect to the target is how a trip ends (see
    `velocity_reference_frame`).
    Braking is by three independent engines, one per ship axis, bound or not (see `_brake`).
    Bound, the world's surface gravity pulls the ship down and the flight assist holds it up (see `_apply_gravity`).
    Unbound inside the fixed zone of a body that pulls, the ship falls along the body's Kepler orbit (see
    `_move_unbound`), the pilot is told to compensate its gravity on entering the zone and that it is over on leaving
    (`_announce_compensation`), and the time scale is limited there (`coasting_time_limit`).

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
    BRAKED = 1e-3  # m/s or degrees/s: at or under this, there is nothing left for the brake to do
    # of energy (Wh) for each m/s the ship's speed changes by, thrusting or braking (not turning)
    ENERGY_PER_SPEED = 5e4
    # m: a ship that moves farther than this in a frame outruns the rocks
    ROCKS_TRAVEL_LIMIT = RockyWorld.SURROUNDINGS_RADIUS
    # share of the orbital period, at the ship's distance, that one frame may cover while falling in a fixed zone
    COASTING_STEP_SHARE = 0.01

    def __init__(self, ship: Ship) -> None:
        self.ship: Ship = ship
        # Bound and moving along the surface more than ROCKS_TRAVEL_LIMIT in the last frame: nothing seen in a frame is
        # seen in the next, so the rocks are neither generated (the Km2s around the ship are left as they are, and the
        # ship's own may be missing) nor drawn (see OpenGLGui.draw) until the ship slows down.
        self.outruns_rocks: bool = False
        # Unbound in a pulling fixed zone: the state at the end of the last frame (None elsewhere).
        self.coasting: Optional[CoastState] = None
        # The body whose gravity the pilot was told to compensate, to stay fixed to it (None when none).
        self.compensating: Optional[Body] = None

    # region Angles and directions
    def pitch_angle(self, body: Body, current_datetime: datetime) -> float:
        """Nose-up angle in degrees above the local horizon."""
        up_reference = -self.direction_down(body, current_datetime)
        return math.degrees(math.asin(max(-1.0, min(1.0, self.ship.attitude.forward.dot(up_reference)))))

    def roll_angle(self, body: Body, current_datetime: datetime) -> float:
        """Right-wing-down angle in degrees relative to the local horizon."""
        up_reference = -self.direction_down(body, current_datetime)
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
            if not isinstance(body, World):
                raise Exception("Body is not a world.")  # bound: the body is a world
            return body.star_offset_from_ship(self.ship, current_datetime)
        return -self.ship.position.as_vector()

    def direction_to_body(self, target: Body, current_datetime: datetime) -> Vector3:
        return self.direction_to_point(target.calculate_stellar_position(current_datetime), current_datetime)

    def direction_to_point(self, point: Vector3, current_datetime: datetime) -> Vector3:
        """Vector from the ship to a stellar-frame point, in the active frame: surface east/up/north while bound."""
        if not self.ship.is_bound:
            return point - self.ship.position.as_vector()
        world = gem.current_environment.fixed_world
        if world is None:
            raise Exception("Fixed world is none.")
        relative = point - self.stellar_position(current_datetime)
        # the surface basis has Y opposite to the orbital motion
        relative = Vector3(relative.x, -relative.y, relative.z)
        east_hat, up_hat, north_hat = world.surface_basis(self.ship.position.x, self.ship.position.z, current_datetime)
        return Vector3(relative.dot(east_hat), relative.dot(up_hat), relative.dot(north_hat))

    def sky_rotation(self, current_datetime: datetime) -> Tuple[Vector3, Vector3, Vector3]:
        """Where the stellar frame's x, y and z axes point in the active frame: what turns a direction to something so
        far away that the ship's position does not matter (the sky behind everything) into the active frame. Unbound it
        is the same frame, and the axes are their own; bound, they go through the surface basis, as in
        `direction_to_point`, so the sky turns with the world's spin."""
        if not self.ship.is_bound:
            return Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)
        world = gem.current_environment.fixed_world
        if world is None:
            raise Exception("Fixed world is none.")
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
        if world is None:
            raise Exception("Fixed world is none.")
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
        self.outruns_rocks = ship.is_bound and math.hypot(ship.velocity.x, ship.velocity.z) * delta_time > \
            Navigation.ROCKS_TRAVEL_LIMIT

        environment = gem.current_environment
        if not ship.is_bound:
            with frame_watch.timed('refresh fixed body'):
                environment.refresh_fixed_body(ship.position.as_vector())
        body = environment.fixed_body  # None outside every fixed zone: then there is nothing to bind to
        if ship.is_bound:
            if not isinstance(body, World):
                raise Exception("Fixed body is not a world.")
            if ship.position.y + body.radius > Navigation.UNBIND_RADIUS_MULTIPLE * body.radius:
                self._unbind_from(body)
        elif (isinstance(body, World)  # the star is never bound to
                and self.distance_to_body_centre(body) <= Navigation.BIND_RADIUS_MULTIPLE * body.radius):
            self._bind_to(body)
        self._announce_compensation()

        if ship.is_bound:
            world = environment.fixed_world
            if world is None:
                raise Exception("Fixed world is none.")
            km2 = world.get_km2_at(ship.position.x, ship.position.z)
            if not ship.position.y > RockyWorld.SURROUNDINGS_RADIUS and not self.outruns_rocks \
                    and (km2 is None or km2 != ship.position.km2):
                with frame_watch.timed('update surroundings'):
                    world.update_surroundings(
                        ship.position.y, ship.position.x, ship.position.z, environment.date_time)
                km2 = world.get_km2_at(ship.position.x, ship.position.z)
            ship.position.km2 = km2
        return self

    def _update_velocity(self, delta_time: float, longitude_accel_input: float, altitude_accel_input: float,
                         latitude_accel_input: float, braking: bool) -> None:
        ship = self.ship
        attitude = ship.attitude
        if braking:
            self._brake(delta_time)
            self._apply_gravity(delta_time, 0.0)
            return
        if ship.is_bound:
            # each axis is scaled before the turn by the yaw, so that forward keeps its own acceleration
            world_accel_x, world_accel_z = rotate_2d(longitude_accel_input * ship.RIGHT_LEFT_ACC,
                                                     latitude_accel_input * ship.FORWARD_BACKWARD_ACC,
                                                     math.radians(attitude.yaw))
            accel = Vector3(
                world_accel_x,
                altitude_accel_input * ship.UP_DOWN_ACC,
                world_accel_z,
            )
        else:
            accel = (
                attitude.right * (longitude_accel_input * ship.RIGHT_LEFT_ACC)
                + attitude.forward * (latitude_accel_input * ship.FORWARD_BACKWARD_ACC)
                + attitude.up * (altitude_accel_input * ship.UP_DOWN_ACC)
            )
        reference = self.velocity_reference_frame()
        speed_before = (ship.velocity.as_vector() - reference).length()
        ship.velocity.add_vector(accel * delta_time)
        speed_after = (ship.velocity.as_vector() - reference).length()
        ship.energy -= Navigation.ENERGY_PER_SPEED * abs(speed_after - speed_before)
        self._apply_gravity(delta_time, altitude_accel_input)

    def gravity(self) -> float:
        """m/s^2 that pulls the ship down: the surface gravity of the world it is bound to, the same at any altitude
        (the bound geometry is flat). Zero unbound: out there the pull acts on the orbit (see `_move_unbound`)."""
        world = gem.current_environment.fixed_world
        if not self.ship.is_bound or world is None:
            return 0.0
        return world.gravitational_parameter / world.radius ** 2

    def is_hovering(self) -> bool:
        """True while bound above the ground in a gravity: the flight assist is holding the ship up, which costs energy
        whether it moves or not."""
        return self.gravity() > 0.0 and self.ship.position.y > self.ship.HEIGHT + Navigation.BRAKED

    def _apply_gravity(self, delta_time: float, altitude_accel_input: float) -> None:
        """Pulls the bound ship down by the gravity. The flight assist, always on, holds it up while no climb or descent
        is asked: it cancels the pull with the engines (all of it up to UP_DOWN_ACC, the engines' whole power; a world
        pulling harder cannot be hovered over), at ENERGY_PER_SPEED per m/s of pull cancelled, so hovering costs energy
        for as long as it lasts. With a vertical key held UP_DOWN_ACC is all the push there is, and the pull is not
        cancelled: climbing nets UP_DOWN_ACC - gravity, descending UP_DOWN_ACC + gravity. On the ground, with no climb
        asked, the ground holds the ship up."""
        ship = self.ship
        gravity = self.gravity()
        if gravity == 0.0 or (ship.position.y <= ship.HEIGHT + Navigation.BRAKED and altitude_accel_input <= 0.0):
            return
        cancelled = min(gravity, ship.UP_DOWN_ACC) if altitude_accel_input == 0.0 else 0.0
        ship.velocity.y -= (gravity - cancelled) * delta_time
        ship.energy -= Navigation.ENERGY_PER_SPEED * cancelled * delta_time

    def is_landed(self) -> bool:
        """True when the ship rests on the surface of its world: bound, at the ground (the lowest altitude the ship can
        have, Ship.HEIGHT), and at rest in the surface frame, which an outpost is fixed in too."""
        ship = self.ship
        return (ship.is_bound and ship.position.y <= ship.HEIGHT + Navigation.BRAKED
                and ship.velocity.as_vector().length() <= Navigation.BRAKED)

    def has_motion_to_brake(self) -> bool:
        """True while the brake has something to do: speed relative to the frame it brakes against, or a rotation."""
        relative = self.ship.velocity.as_vector() - self.velocity_reference_frame()
        attitude = self.ship.attitude
        rates = (attitude.yaw_rate, attitude.pitch_rate, attitude.roll_rate)
        return relative.length() > Navigation.BRAKED or any(abs(rate) > Navigation.BRAKED for rate in rates)

    def _brake(self, delta_time: float) -> None:
        """Brakes against the velocity of the reference frame (`velocity_reference_frame`) with three independent
        engines, one on each of the ship's axes, the ones the thrust keys use: right, up and forward (while bound, right
        and forward are horizontal, turned by the yaw). Each engine takes up to BRAKE_ACC off its own component,
        whatever the others do: a small component stops as fast as a large one, and the ship is at rest relative to the
        frame when the slowest engine is done. The energy is ENERGY_PER_SPEED per m/s that the speed relative to the
        frame drops by, whichever engines do it."""
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
        ship.energy -= Navigation.ENERGY_PER_SPEED * abs(relative.length() - braked.length())
        ship.velocity.set_vector(reference + braked)

    def _update_position(self, delta_time: float) -> None:
        ship = self.ship
        if not ship.is_bound:
            self._move_unbound(delta_time)
            self._collide_with_portal_base()
            return
        ship.position.add_vector(ship.velocity.as_vector() * delta_time)

        world = gem.current_environment.fixed_world
        if world is None:
            raise Exception("Fixed world is none.")
        half_turn = math.pi * world.radius  # half the equator
        if ship.position.x < -half_turn:  # crossing the anti-meridian
            ship.position.x += half_turn * 2
        elif ship.position.x > half_turn:
            ship.position.x -= half_turn * 2
        ship.position.y = max(ship.HEIGHT, ship.position.y)
        ship.position.z = max(-half_turn / 2, min(half_turn / 2, ship.position.z))  # between the poles
        # no descent faster than the altitude left
        ship.velocity.y = max(-(ship.position.y - ship.HEIGHT), ship.velocity.y)

    def _announce_compensation(self) -> None:
        """Tells the pilot when staying fixed to a body that pulls means compensating its gravity: on entering its fixed
        zone, and on leaving it. Bound, the flight assist does it and nothing is said."""
        ship = self.ship
        body = gem.current_environment.fixed_body
        pulling = body if not ship.is_bound and body is not None and body.gravitational_parameter > 0.0 else None
        if pulling is self.compensating:
            return
        if self.compensating is not None and not ship.is_bound:
            ship.notification.set(f"{self.compensating.name}'s gravity neglegible. Stopped compensating.")
        if pulling is not None:
            ship.notification.set(
                f"Compensating {pulling.name}'s gravity.")
            self._warn_if_inescapable(pulling)
        self.compensating = pulling

    def combined_thrust(self) -> float:
        """m/s^2, the most the engines give at once: the three axes together, the way the thrust keys combine."""
        ship = self.ship
        return math.sqrt(ship.FORWARD_BACKWARD_ACC ** 2 + ship.UP_DOWN_ACC ** 2 + ship.RIGHT_LEFT_ACC ** 2)

    def _warn_if_inescapable(self, body: Body) -> None:
        """On fixing to a body whose surface pull is more than the engines give at once: a dialog that must be OK-ed
        says the ship cannot climb away from it, given while it can still turn back. The pull at the surface is the
        strongest the ship will meet there, so no climb from it can succeed."""
        ship = self.ship
        surface_pull = body.gravitational_parameter / body.radius ** 2
        thrust = self.combined_thrust()
        if surface_pull <= thrust:
            return
        player = ship.owner
        player.time_scale = player.TIME_SCALE_MIN
        show_message(Message(
            title=f"DANGER: NO ESCAPE FROM {body.name.upper()}",
            text=f"The surface pull of {body.name} is {surface_pull:.2f} m/s², more than the engines can overcome: at "
                 f"most {thrust:.2f} m/s², with all axes at once. The ship cannot climb away from it.\n\n"
                 f"Turn back now, {player.get_title()}.",
            open_sound='alert',
        ))

    def _move_unbound(self, delta_time: float) -> None:
        """Moves the unbound ship over the frame. Inside the fixed zone of a body that pulls, the path is the body's
        Kepler orbit, exact for any step (`kepler.propagate`), and the frame's thrust is a kick at its start: the change
        of velocity that `_update_velocity` made since the last frame. The state is kept relative to the body, as it
        was at the end of the last frame, so that a frame does not ask for the body's position at an earlier date. The
        first frame in such a zone, or one where something else moved the ship (binding, the portal base), starts from
        where the ship was at the start of the frame, the body's place at that date. Elsewhere the ship moves in a
        straight line, as there is no pull."""
        ship = self.ship
        environment = gem.current_environment
        body = environment.fixed_body
        if body is None or body.gravitational_parameter == 0.0:
            self.coasting = None
            ship.position.add_vector(ship.velocity.as_vector() * delta_time)
            return

        now = environment.date_time
        mu = body.gravitational_parameter
        previous = self.coasting
        if previous is not None and previous.body is body and previous.position == ship.position.as_vector():
            kick = ship.velocity.as_vector() - previous.velocity
            seconds = (now - previous.date_time).total_seconds()
            relative_position, relative_velocity = kepler.propagate(
                mu, previous.relative_position, previous.relative_velocity + kick, seconds)
        else:
            start = now - timedelta(seconds=delta_time)
            relative_position, relative_velocity = kepler.propagate(
                mu, ship.position.as_vector() - body.calculate_stellar_position(start),
                ship.velocity.as_vector() - body.calculate_stellar_velocity(start), delta_time)
        centre = body.calculate_stellar_position(now)
        centre_velocity = body.calculate_stellar_velocity(now)
        ship.position.set_vector(centre + relative_position)
        ship.velocity.set_vector(centre_velocity + relative_velocity)
        self.coasting = CoastState(body, now, relative_position, relative_velocity,
                                   ship.position.as_vector(), ship.velocity.as_vector())

    def _collide_with_portal_base(self) -> None:
        """Unbound, near the portal base: the ship's hull comes to rest against what is solid in it (see
        PortalBaseSolid). The base is at rest in the stellar frame, so the ship's velocity is also relative to it."""
        ship = self.ship
        if ship.is_docked:
            return
        environment = gem.current_environment
        base = environment.nearest_system.portal_base
        centre = base.calculate_stellar_position(environment.date_time)
        offset = ship.position.as_vector() - centre
        half_sizes = (ship.WIDTH / 2.0, ship.HEIGHT / 2.0, ship.DEPTH / 2.0)  # right, up, forward: the hull's halves
        if offset.length() > base.solid.reach(half_sizes):
            return
        velocity = ship.velocity.as_vector()
        attitude = ship.attitude
        resolved = base.solid.resolve((offset.x, offset.y, offset.z), (velocity.x, velocity.y, velocity.z),
                                      attitude.right, attitude.up, attitude.forward, half_sizes)
        if resolved is not None:
            (x, y, z), velocity_after = resolved
            ship.position.set_vector((centre.x + x, centre.y + y, centre.z + z))
            ship.velocity.set_vector(velocity_after)
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
        surface_vel = world.stellar_to_surface_velocity(stellar_vel, altitude, latitude, current_datetime, basis)

        ship.position.set_vector(local_pos)
        ship.velocity.set_vector(surface_vel)
        forward_surface = world.stellar_vector_to_surface(attitude.forward, basis)
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

        ship.notification.set(f"Arriving to {world.name}, Pilot {ship.owner.surname}.", 'bind')
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
            world.surface_vector_to_stellar(axis, basis)
            for axis in (attitude.right, attitude.up, attitude.forward)
        )
        ship.position.set_vector(ship_pos)
        ship.velocity.set_vector(ship_vel)

        ship.notification.set(f"Leaving {world.name}, Pilot {ship.owner.surname}.", 'unbind')
        ship.is_bound = False
        return self

    def _stellar_position_from_surface(self, world: World, world_pos: Vector3,
                                       basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        _, up_hat, _ = basis
        offset = up_hat * (world.radius + self.ship.position.y)
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated here.
        return Vector3(world_pos.x + offset.x, world_pos.y - offset.y, world_pos.z + offset.z)

    def _stellar_velocity_from_surface(self, world: World, world_vel: Vector3,
                                       basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
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
        return math.dist(self.ship.position.as_vector(),
                         body.calculate_stellar_position(gem.current_environment.date_time))

    def altitude_above_surface(self, body: Body) -> float:
        if self.ship.is_bound:
            return self.ship.position.y
        return self.distance_to_body_centre(body) - body.radius

    def in_fixed_zone(self, body: Body) -> bool:
        return (not self.ship.is_bound
                and self.distance_to_body_centre(body) < Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius)

    def velocity_reference_frame(self) -> Vector3:
        """The velocity that braking (S) and the prograde/retrograde markers are measured against: the fixed body's
        inside its fixed zone, else, while unbound, the targeted body's (the long distance advice brakes against it),
        else zero."""
        environment = gem.current_environment
        body = environment.fixed_body
        if body is None or not self.in_fixed_zone(body):
            body = None if self.ship.is_bound else environment.targeted_body
        if body is None:
            return Vector3(0.0, 0.0, 0.0)
        return body.calculate_stellar_velocity(environment.date_time)

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

    def coasting_time_limit(self) -> float:
        """Game seconds one frame may cover while the unbound ship is in the fixed zone of a body that pulls: a share of
        the period of a circular orbit at its distance, so that a fall does not skip over the bind shell. Infinite
        otherwise."""
        body = gem.current_environment.fixed_body
        if self.ship.is_bound or body is None or body.gravitational_parameter == 0.0:
            return math.inf
        distance = self.distance_to_body_centre(body)
        return Navigation.COASTING_STEP_SHARE * math.tau * math.sqrt(distance ** 3 / body.gravitational_parameter)

    def collision_warning(self, body: Body) -> bool:
        """True if the ship, on its straight line relative to the body, would reach the surface even braking
        with only COLLISION_BRAKE_FRACTION of BRAKE_ACC. Sideways dodging is not considered. Inside a fixed zone that
        pulls the path curves, so this is then only a guide."""
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
        COLLISION_BRAKE_FRACTION of BRAKE_ACC (the same judgement as collision_warning, on the vertical), less the pull
        the flight assist cannot cancel (what the gravity is over UP_DOWN_ACC)."""
        if not self.ship.is_bound or self.ship.velocity.y >= 0.0:
            return False
        ship = self.ship
        decel = ship.BRAKE_ACC * Navigation.COLLISION_BRAKE_FRACTION - max(0.0, self.gravity() - ship.UP_DOWN_ACC)
        if decel <= 0.0:
            return True  # the engines cannot stop this fall
        return ship.position.y <= ship.velocity.y ** 2 / (2.0 * decel)
    # endregion
