"""The ship's orientation and how it turns."""

from __future__ import annotations
import math
from typing import TYPE_CHECKING, Tuple

from common.vector3 import Vector3

if TYPE_CHECKING:
    from .ship import Ship


class Attitude:
    """The ship's right, up and forward axes, in the active frame (surface when bound, stellar when unbound).

    The axes are the source of truth; yaw, pitch and roll are derived from them or applied to them. Use these names
    consistently, do not introduce synonyms:
    - Yaw: rotation about the up axis (Numpad 4 left, 6 right). `yaw` is the heading in degrees clockwise from
      north, derived from the forward axis; `yaw_rate` is the rate in degrees per second.
    - Pitch: rotation about the right axis (Numpad 2 nose up, 8 nose down; only while unbound). `pitch_rate` is the
      rate; the angle above the local horizon is `Navigation.pitch_angle`.
    - Roll: rotation about the forward axis (E right, Q left; only while unbound). `roll_rate` is the rate; the angle
      relative to the local horizon is `Navigation.roll_angle`.

    Acceleration, braking and speed limit are the same on every axis: Ship.ANGULAR_ACC, ANGULAR_BRAKE and
    MAX_ANGULAR_SPEED. Braking (S) brings all three rates to zero, and costs energy only while it removes a rate.
    """

    def __init__(self, ship: Ship) -> None:
        self.ship: Ship = ship
        self.right: Vector3 = Vector3(1.0, 0.0, 0.0)
        self.up: Vector3 = Vector3(0.0, 1.0, 0.0)
        self.forward: Vector3 = Vector3(0.0, 0.0, 1.0)
        self.yaw_rate: float = 0.0
        self.pitch_rate: float = 0.0
        self.roll_rate: float = 0.0

    @property
    def yaw(self) -> float:
        """Heading in degrees clockwise from north, from the ship's forward axis."""
        return math.degrees(math.atan2(self.forward[0], self.forward[2])) % 360

    # region Turning
    def update_yaw(self, delta_time: float, counterclockwise: int, clockwise: int, braking: bool = False) -> Attitude:
        if delta_time == 0.0:
            return self
        self.yaw_rate, angle = self._turn(self.yaw_rate, clockwise - counterclockwise, counterclockwise + clockwise != 0,
                                          delta_time, braking)
        self.forward, self.right = Vector3.rotate_pair(self.forward, self.right, angle)
        return self

    def update_pitch(self, delta_time: float, nose_up: int, nose_down: int, braking: bool = False) -> Attitude:
        if self.ship.is_bound or delta_time == 0.0:
            return self
        self.pitch_rate, angle = self._turn(self.pitch_rate, nose_up - nose_down, nose_up + nose_down != 0,
                                            delta_time, braking)
        self.forward, self.up = Vector3.rotate_pair(self.forward, self.up, angle)
        return self

    def update_roll(self, delta_time: float, roll_right: int, roll_left: int, braking: bool = False) -> Attitude:
        if self.ship.is_bound or delta_time == 0.0:
            return self
        self.roll_rate, angle = self._turn(self.roll_rate, roll_left - roll_right, roll_right + roll_left != 0,
                                           delta_time, braking)
        self.right, self.up = Vector3.rotate_pair(self.right, self.up, angle)
        return self

    def _turn(self, rate: float, direction: int, key_held: bool, delta_time: float, braking: bool) -> Tuple[float, float]:
        """One axis over `delta_time`: the new rate, accelerated in `direction` or braked, within MAX_ANGULAR_SPEED, and the
        angle turned, in radians. Costs energy: the thrusters 5e4 per second while a key is held, the brake 1e5 per second
        only for the time it took to remove the rate (so nothing when there is no rate to brake)."""
        if braking:
            decel = min(self.ship.ANGULAR_BRAKE * delta_time, abs(rate))
            rate -= math.copysign(decel, rate)
            self.ship.energy -= 1e5 * decel / self.ship.ANGULAR_BRAKE
        else:
            rate += direction * self.ship.ANGULAR_ACC * delta_time
        rate = max(-self.ship.MAX_ANGULAR_SPEED, min(self.ship.MAX_ANGULAR_SPEED, rate))
        self.ship.energy -= delta_time * (5e4 if (not braking and key_held) else 0)
        return rate, math.radians(rate * delta_time)
    # endregion

    # region Camera

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
    # endregion

    # region Persistence
    def serialize(self) -> dict:
        return {
            'right': list(self.right),
            'up': list(self.up),
            'forward': list(self.forward),
            'yaw_rate': self.yaw_rate,
            'pitch_rate': self.pitch_rate,
            'roll_rate': self.roll_rate,
        }

    @staticmethod
    def deserialize(ship: Ship, src: dict) -> Attitude:
        result = Attitude(ship)
        result.right = Vector3(*src['right'])
        result.up = Vector3(*src['up'])
        result.forward = Vector3(*src['forward'])
        result.yaw_rate = src['yaw_rate']
        result.pitch_rate = src['pitch_rate']
        result.roll_rate = src['roll_rate']
        return result
    # endregion
