"""The ship's orientation and how it turns."""

from __future__ import annotations
import math
from typing import TYPE_CHECKING

from vector3 import Vector3

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
    MAX_ANGULAR_SPEED. Braking (S) brings all three rates to zero.
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

    def _updated_rate(self, rate: float, direction: int, delta_time: float, braking: bool) -> float:
        if braking:
            rate -= math.copysign(min(self.ship.ANGULAR_BRAKE * delta_time, abs(rate)), rate)
        else:
            rate += direction * self.ship.ANGULAR_ACC * delta_time
        return max(-self.ship.MAX_ANGULAR_SPEED, min(self.ship.MAX_ANGULAR_SPEED, rate))

    def update_yaw(self, delta_time: float, counterclockwise: int, clockwise: int, braking: bool = False) -> Attitude:
        self.yaw_rate = self._updated_rate(self.yaw_rate, clockwise - counterclockwise, delta_time, braking)
        angle = math.radians(self.yaw_rate * delta_time)
        self.forward, self.right = Vector3.rotate_pair(self.forward, self.right, angle)
        # self.ship.energy -= delta_time * 1e6
        return self

    def update_pitch(self, delta_time: float, nose_up: int, nose_down: int, braking: bool = False) -> Attitude:
        if self.ship.is_bound:
            return self
        self.pitch_rate = self._updated_rate(self.pitch_rate, nose_up - nose_down, delta_time, braking)
        angle = math.radians(self.pitch_rate * delta_time)
        self.forward, self.up = Vector3.rotate_pair(self.forward, self.up, angle)
        return self

    def update_roll(self, delta_time: float, roll_right: int, roll_left: int, braking: bool = False) -> Attitude:
        if self.ship.is_bound:
            return self
        self.roll_rate = self._updated_rate(self.roll_rate, roll_left - roll_right, delta_time, braking)
        angle = math.radians(self.roll_rate * delta_time)
        self.right, self.up = Vector3.rotate_pair(self.right, self.up, angle)
        return self

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
    def load(ship: Ship, src: dict) -> Attitude:
        result = Attitude(ship)
        result.right = Vector3(*src['right'])
        result.up = Vector3(*src['up'])
        result.forward = Vector3(*src['forward'])
        result.yaw_rate = src['yaw_rate']
        result.pitch_rate = src['pitch_rate']
        result.roll_rate = src['roll_rate']
        return result
