from __future__ import annotations
import math
from typing import NamedTuple, Tuple


class Vector3(NamedTuple):
    x: float
    y: float
    z: float

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other[0], self.y + other[1], self.z + other[2])

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other[0], self.y - other[1], self.z - other[2])

    def __neg__(self) -> Vector3:
        return Vector3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar: float) -> Vector3:
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def dot(self, other: Vector3) -> float:
        return self.x * other[0] + self.y * other[1] + self.z * other[2]

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> Vector3:
        return self * (1.0 / self.length())

    @staticmethod
    def rotate_pair(a: Vector3, b: Vector3, angle: float) -> Tuple[Vector3, Vector3]:
        """Rotate the (a, b) axis pair by angle radians in their shared plane:
        a' = cos*a + sin*b, b' = cos*b - sin*a. Used by Player._yaw/_pitch/_roll
        (forward/right, forward/up, right/up pairs) and by Player.bind_to
        (reconstructing forward/right from a yaw angle)."""
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return a * cos_a + b * sin_a, b * cos_a - a * sin_a


def rotate_2d(a: float, b: float, angle: float) -> Tuple[float, float]:
    """Same rotation as Vector3.rotate_pair, for a lone scalar pair rather than
    two 3-vectors. Used by Player.update_coordinates' bound branch to rotate
    ship-relative thrust input into world (x, z) axes."""
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return cos_a * a + sin_a * b, cos_a * b - sin_a * a
