"""The ORBIT assist: an autopilot that takes an unbound ship, fixed to a body that pulls, into an orbit about that
body, and the orbit it leaves the ship in. From the press of ORBIT the engines stop compensating the pull (see
`Navigation.compensates_pull`): the ship falls freely, which is what an orbit is. The ORBIT button shows pressed
meanwhile (see OrbitButton). The pilot may turn and look around, which does not change the path, and S only stops the
turns; a translation key (W, X, A, D) or ORBIT pressed again leaves the orbit, and the engines compensate the pull
again.

Until the ship is in an orbit, each frame steers its velocity relative to the body towards the velocity of a circular
orbit at the radius it is at, with the right, up and forward engines together, whatever the attitude, each up to its
own acceleration. The thrust is proportional to the velocity error, so the error closes within a few seconds, or two
frames when the time scale is high. Aiming at the radius it is at, rather than the start radius, keeps the orbit from
drifting while it settles.

The ship is in an orbit once its path is closed, above the bind shell and inside the fixed zone, for
ESTABLISHED_FRAMES frames in a row: the thrust stops, and the orbit costs nothing. The assist gives up, with a
notification saying why, when no orbit is reached within REACH_PERIOD_SHARE of a period or the energy runs out first,
and the orbit ends when the ship leaves the fixed zone or lands.
"""

from __future__ import annotations
import math
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from common.vector3 import Vector3
from galaxies.kepler import apsides
from galaxies.world import World
import game_environment as gem
from spaceships.navigation import Navigation

if TYPE_CHECKING:
    from galaxies.body import Body
    from .ship import Ship

Thrust = Tuple[float, float, float]  # shares of the right, up and forward engines, -1 to 1
NO_THRUST: Thrust = (0.0, 0.0, 0.0)


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return Vector3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


class OrbitAssist:
    """One orbit, from the press of ORBIT until the ship leaves it. It lives on the ship's navigation
    (`Navigation.orbit`) meanwhile."""

    REACH_PERIOD_SHARE = 1.0 / 6.0  # of the period of the target orbit: the ship must be in an orbit by then
    ESTABLISHED_FRAMES = 3  # frames in a row in an orbit before the thrust stops, to let the controller settle
    MIN_TIME_CONSTANT = 5.0  # s: the thrust closes the speed error within this, or two frames when that is longer
    DEAD_BAND = 0.005  # the velocity error, as a share of the circular speed, below which it does not thrust
    LANDING_MARGIN = 2.0  # the energy to orbit and land must be this many times the minimum to land
    EPSILON = 1e-9

    def __init__(self, ship: Ship, body: Body, radius: float, started: datetime) -> None:
        self.ship: Ship = ship
        self.body: Body = body
        self.radius: float = radius  # m, from the body's centre: the target orbit's radius, the start radius
        self.started: datetime = started
        self.period: float = math.tau * math.sqrt(radius ** 3 / body.gravitational_parameter)
        self.orbit_frames: int = 0  # frames in a row in an orbit
        self.established: bool = False  # in an orbit: the thrust has stopped, and the ship coasts

    @staticmethod
    def begin(ship: Ship) -> Optional[str]:
        """Starts the assist if the ship can: None when it did, else the reason it cannot (for the notification). The
        checks are the ones that cannot be left to the orbit: the path must not land the ship first, the energy must
        cover an orbit and a landing with a margin, and the engine must be able to stop a fall, if the ship falls."""
        environment = gem.current_environment
        body = environment.fixed_body
        if ship.is_bound or not isinstance(body, World) or body.gravitational_parameter == 0.0:
            return "not fixed to a body that pulls"
        if ship.navigation.is_inside(body):
            return "the ship is inside the planet"
        mu = body.gravitational_parameter
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        radius = r_vec.length()
        periapsis, _, _ = apsides(mu, r_vec, v_vec)
        if periapsis < Navigation.BIND_RADIUS_MULTIPLE * body.radius:
            return "the ship would land before it could orbit. Thrust sideways to raise the lowest point"
        circular_speed = math.sqrt(mu / radius)
        target_velocity = OrbitAssist._target_velocity(r_vec, v_vec, mu, radius)
        landing = circular_speed * (1.0 - math.sqrt(2.0 * body.radius / (body.radius + radius)))
        # the energy of the change of velocity to the orbit, and of the landing, for the ship's mass
        required = ship.energy_per_delta_v(ship.mass) * ((target_velocity - v_vec).length() + landing)
        if ship.energy < OrbitAssist.LANDING_MARGIN * required:
            return "not enough energy to orbit and land"
        radial_speed = v_vec.dot(r_vec) / radius
        if radial_speed < 0.0 and ship.navigation.pull() > ship.FORWARD_BACKWARD_ACC:
            return "the pull is more than the engines can stop the fall"
        if ship.navigation.travel is not None:
            ship.navigation.travel.end(None)  # the autopilot flies in straight lines, the orbit falls
        ship.navigation.orbit = OrbitAssist(ship, body, radius, environment.date_time)
        ship.notification.set("Starting to orbit.")
        return None

    def step(self, delta_time: float) -> Thrust:
        """One frame: the thrust to apply. It may end the orbit instead, with a notification (then there is none)."""
        ship = self.ship
        environment = gem.current_environment
        body = environment.fixed_body
        if ship.is_bound:
            self.end(f"Orbit cancelled: landed on {body.name}." if body is not None else None)
            return NO_THRUST
        if body is None or body is not self.body:
            self.end("Orbit cancelled: the ship left the fixed zone.")
            return NO_THRUST
        if ship.navigation.is_inside(body):
            self.end("Orbit cancelled: the ship is inside the planet.")
            return NO_THRUST
        if self.established:
            return NO_THRUST
        mu = body.gravitational_parameter
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        radius = r_vec.length()
        in_orbit = OrbitAssist._is_orbit(body, r_vec, v_vec)
        elapsed = (environment.date_time - self.started).total_seconds()
        if ship.energy <= 0.0:
            self.end("Orbit cancelled: out of energy.")
            return NO_THRUST
        if not in_orbit and elapsed > OrbitAssist.REACH_PERIOD_SHARE * self.period:
            self.end("Orbit cancelled: no orbit in time.")
            return NO_THRUST
        if in_orbit:
            self.orbit_frames += 1
            if self.orbit_frames >= OrbitAssist.ESTABLISHED_FRAMES:
                self.established = True
                ship.notification.set("Orbit established.")
                return NO_THRUST
        else:
            self.orbit_frames = 0

        error = self._target_velocity(r_vec, v_vec, mu, radius) - v_vec
        if error.length() < OrbitAssist.DEAD_BAND * math.sqrt(mu / radius):
            return NO_THRUST
        time_constant = max(OrbitAssist.MIN_TIME_CONSTANT, 2.0 * delta_time)
        command = error * (1.0 / time_constant)
        attitude = ship.attitude
        engines = ((attitude.right, ship.RIGHT_LEFT_ACC), (attitude.up, ship.UP_DOWN_ACC),
                   (attitude.forward, ship.FORWARD_BACKWARD_ACC))
        right, up, forward = (max(-1.0, min(1.0, command.dot(axis) / acceleration)) for axis, acceleration in engines)
        return right, up, forward

    @staticmethod
    def resume(ship: Ship) -> None:
        """On loading a game: a ship whose path is an orbit about the world it is fixed to is in orbit. Nothing about
        the orbit is saved: it is worked out again, as the fixed body is."""
        environment = gem.current_environment
        body = environment.fixed_body
        if ship.is_bound or not isinstance(body, World) or body.gravitational_parameter == 0.0 \
                or ship.navigation.is_inside(body):
            return
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        if OrbitAssist._is_orbit(body, r_vec, v_vec):
            orbit = OrbitAssist(ship, body, r_vec.length(), environment.date_time)
            orbit.established = True
            ship.navigation.orbit = orbit

    @staticmethod
    def press(ship: Ship) -> None:
        """The ORBIT button: leaves the orbit, or starts one, with a notification saying why it cannot."""
        if ship.navigation.orbit is not None:
            ship.navigation.orbit.leave()
            return
        reason = OrbitAssist.begin(ship)
        if reason is not None:
            ship.notification.set(f"Orbit not started: {reason}.", bad=True)

    def leave(self) -> None:
        """The pilot leaves the orbit, or gives up reaching one: ORBIT pressed again, or a translation key."""
        self.end("Orbit left: compensating the pull again." if self.established else "Orbit cancelled by the pilot.")

    def end(self, message: Optional[str]) -> None:
        """Releases the ship: the engines compensate the pull again. `message` is the notification, or None for none
        (the bind notice says it landed)."""
        self.ship.navigation.orbit = None
        if message is not None:
            self.ship.notification.set(message)

    @staticmethod
    def _is_orbit(body: Body, r_vec: Vector3, v_vec: Vector3) -> bool:
        """Whether the path from the position and velocity relative to the body is an orbit: closed, above the bind
        shell and inside the fixed zone."""
        periapsis, apoapsis, energy = apsides(body.gravitational_parameter, r_vec, v_vec)
        return (energy < 0.0 and periapsis >= Navigation.BIND_RADIUS_MULTIPLE * body.radius
                and apoapsis <= Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius)

    @staticmethod
    def _target_velocity(r_vec: Vector3, v_vec: Vector3, mu: float, radius: float) -> Vector3:
        """The velocity, relative to the body, of a circular orbit of `radius` at the ship's place, in its direction of
        travel (any direction when it has none sideways)."""
        radial = r_vec * (1.0 / r_vec.length())
        tangent = v_vec - radial * v_vec.dot(radial)
        if tangent.length() <= OrbitAssist.EPSILON:
            tangent = _cross(radial, Vector3(0.0, 0.0, 1.0))
            if tangent.length() <= OrbitAssist.EPSILON:
                tangent = _cross(radial, Vector3(1.0, 0.0, 0.0))
        return tangent.normalized() * math.sqrt(mu / radius)
