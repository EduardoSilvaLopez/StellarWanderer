"""The ORBIT assist: an autopilot that takes an unbound ship, fixed to a body that pulls, into an orbit about that
body. While it runs it has the controls: the keys do nothing, and the ORBIT button shows pressed (see
ResourceBars).

Each frame it steers the ship's velocity relative to the body towards the velocity of a circular orbit at the radius the
ship is at. The forward engine does it: the nose turns (at the ship's angular speed, and costing energy as the turning
keys do) to the direction of the thrust needed, and the thrust is proportional to the velocity error, so the error
closes within a few seconds, or two frames when the time scale is high. Thrust along the velocity costs energy as any
thrust does; the pull is left to the orbit, which costs nothing. Aiming at the radius it is at, rather than the start
radius, keeps the orbit from drifting while it settles.

It releases the ship once it is in any orbit: a closed path above the bind shell and inside the fixed zone, for
ESTABLISHED_FRAMES frames in a row. It gives up, with a notification saying why, when no orbit is reached within
REACH_PERIOD_SHARE of a period, when the energy runs out, when the ship leaves the fixed zone, or when it lands. The
pilot gives up by pressing the button again.
"""

from __future__ import annotations
import math
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from common.vector3 import Vector3
from galaxies.kepler import apsides
import game_environment as gem
from spaceships.navigation import Navigation

if TYPE_CHECKING:
    from galaxies.body import Body
    from .ship import Ship


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return Vector3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


class OrbitAssist:
    """The autopilot of one attempt to orbit. It lives on the ship's navigation (`Navigation.orbit`) while it runs."""

    REACH_PERIOD_SHARE = 1.0 / 6.0  # of the period of the target orbit: the ship must be in an orbit by then
    ESTABLISHED_FRAMES = 3  # frames in a row in an orbit before release, to let the controller settle
    MIN_TIME_CONSTANT = 5.0  # s: the thrust closes the speed error within this, or two frames when that is longer
    DEAD_BAND = 0.005  # the velocity error, as a share of the circular speed, below which it neither turns nor thrusts
    ALIGN_TOLERANCE = math.radians(2.0)  # the nose must be this close to the thrust's direction for the engine to fire
    TURN_ENERGY_PER_SECOND = 5e4  # Wh, the cost of a turn at the full angular speed (as a key held: Attitude._turn)
    LANDING_MARGIN = 2.0  # the energy to orbit and land must be this many times the minimum to land
    EPSILON = 1e-9

    def __init__(self, ship: Ship, body: Body, radius: float, started: datetime) -> None:
        self.ship: Ship = ship
        self.body: Body = body
        self.radius: float = radius  # m, from the body's centre: the target orbit's radius, the start radius
        self.started: datetime = started
        self.period: float = math.tau * math.sqrt(radius ** 3 / body.gravitational_parameter)
        self.orbit_frames: int = 0  # frames in a row in an orbit

    @staticmethod
    def begin(ship: Ship) -> Optional[str]:
        """Starts the assist if the ship can: None when it did, else the reason it cannot (for the notification). The
        checks are the ones that cannot be left to the orbit: the path must not land the ship first, the energy must
        cover an orbit and a landing with a margin, and the engine must be able to stop a fall, if the ship falls."""
        environment = gem.current_environment
        body = environment.fixed_body
        if ship.is_bound or body is None or body.gravitational_parameter == 0.0:
            return "not fixed to a body that pulls"
        mu = body.gravitational_parameter
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        radius = r_vec.length()
        periapsis, _, _ = apsides(mu, r_vec, v_vec)
        if periapsis < Navigation.BIND_RADIUS_MULTIPLE * body.radius:
            return "the ship would land before it could orbit. Thrust sideways to raise the lowest point"
        circular_speed = math.sqrt(mu / radius)
        circularise = (OrbitAssist._target_velocity(r_vec, v_vec, mu, radius) - v_vec).length()
        landing = circular_speed * (1.0 - math.sqrt(2.0 * body.radius / (body.radius + radius)))
        required = Navigation.ENERGY_PER_SPEED * (circularise + landing)
        if ship.energy < OrbitAssist.LANDING_MARGIN * required:
            return "not enough energy to orbit and land"
        radial_speed = v_vec.dot(r_vec) / radius
        if radial_speed < 0.0 and ship.navigation.pull() > ship.FORWARD_BACKWARD_ACC:
            return "the pull is more than the engines can stop the fall"
        ship.navigation.orbit = OrbitAssist(ship, body, radius, environment.date_time)
        ship.notification.set("Starting to orbit.")
        return None

    def step(self, delta_time: float) -> float:
        """One frame: the thrust to apply, as a share of the forward engine (0 to 1), after turning the nose. It may end
        the attempt instead, with a notification (then the thrust is 0)."""
        ship = self.ship
        environment = gem.current_environment
        body = environment.fixed_body
        if ship.is_bound:
            return self.end(f"Orbit cancelled: landed on {body.name}." if body is not None else None)
        if body is None or body is not self.body:
            return self.end("Orbit cancelled: the ship left the fixed zone.")
        now = environment.date_time
        mu = body.gravitational_parameter
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        radius = r_vec.length()
        periapsis, apoapsis, energy = apsides(mu, r_vec, v_vec)
        elapsed = (now - self.started).total_seconds()
        zone = Navigation.FIXED_ZONE_RADIUS_MULTIPLE * body.radius
        in_orbit = energy < 0.0 and periapsis >= Navigation.BIND_RADIUS_MULTIPLE * body.radius and apoapsis <= zone
        if ship.energy <= 0.0:
            return self.end("Orbit cancelled: out of energy.")
        if not in_orbit and elapsed > OrbitAssist.REACH_PERIOD_SHARE * self.period:
            return self.end("Orbit cancelled: no orbit in time.")
        if in_orbit:
            self.orbit_frames += 1
            if self.orbit_frames >= OrbitAssist.ESTABLISHED_FRAMES:
                return self.end("Orbit established.")
        else:
            self.orbit_frames = 0

        error = self._target_velocity(r_vec, v_vec, mu, radius) - v_vec
        if error.length() < OrbitAssist.DEAD_BAND * math.sqrt(mu / radius):
            return 0.0  # too small to be worth turning the nose for, and turning costs energy
        time_constant = max(OrbitAssist.MIN_TIME_CONSTANT, 2.0 * delta_time)
        command = error * (1.0 / time_constant)
        magnitude = command.length()
        available = ship.FORWARD_BACKWARD_ACC
        return self._steer(command, min(1.0, magnitude / available), delta_time)

    @staticmethod
    def press(ship: Ship) -> None:
        """The ORBIT button: gives up the attempt that runs, or starts one, with a notification saying why it cannot."""
        if ship.navigation.orbit is not None:
            ship.navigation.orbit.end("Orbit cancelled by the pilot.")
            return
        reason = OrbitAssist.begin(ship)
        if reason is not None:
            ship.notification.set(f"Orbit not started: {reason}.")

    def end(self, message: Optional[str]) -> float:
        """Releases the ship. `message` is the notification, or None for none (the bind notice says it landed)."""
        self.ship.navigation.orbit = None
        if message is not None:
            self.ship.notification.set(message)
        return 0.0

    def _steer(self, command: Vector3, fraction: float, delta_time: float) -> float:
        """Turns the nose towards `command` at the angular speed, and returns the thrust fraction: `fraction` once the
        nose is on the direction within ALIGN_TOLERANCE, else 0."""
        ship = self.ship
        attitude = ship.attitude
        length = command.length()
        if length <= OrbitAssist.EPSILON:
            return 0.0
        nose = command * (1.0 / length)
        angle = math.acos(max(-1.0, min(1.0, attitude.forward.dot(nose))))
        turn = min(angle, math.radians(ship.MAX_ANGULAR_SPEED) * delta_time)
        if turn > 0.0:
            axis = _cross(attitude.forward, nose)
            axis_length = axis.length()
            axis = axis * (1.0 / axis_length) if axis_length > OrbitAssist.EPSILON else attitude.up
            attitude.forward, attitude.right, attitude.up = (
                OrbitAssist._rotate(vector, axis, turn) for vector in (attitude.forward, attitude.right, attitude.up)
            )
            ship.energy -= OrbitAssist.TURN_ENERGY_PER_SECOND * turn / math.radians(ship.MAX_ANGULAR_SPEED)
        return fraction if angle - turn <= OrbitAssist.ALIGN_TOLERANCE else 0.0

    @staticmethod
    def _rotate(vector: Vector3, axis: Vector3, angle: float) -> Vector3:
        """`vector` turned by `angle` (radians) about the unit `axis` (Rodrigues' formula)."""
        cosine, sine = math.cos(angle), math.sin(angle)
        return vector * cosine + _cross(axis, vector) * sine + axis * (axis.dot(vector) * (1.0 - cosine))

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
