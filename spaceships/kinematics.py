"""The ship's position and linear velocity: three components each, in the frame the ship is in (surface while bound)."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from common.vector3 import Vector3

if TYPE_CHECKING:
    from galaxies.km2 import Km2


class _Components:
    x: float
    y: float
    z: float

    def as_vector(self) -> Vector3:
        return Vector3(self.x, self.y, self.z)

    def set_vector(self, values: Tuple[float, float, float]) -> None:
        self.x, self.y, self.z = values

    def add_vector(self, vector: Vector3) -> None:
        self.x += vector.x
        self.y += vector.y
        self.z += vector.z

    def serialize(self) -> dict:
        return {'x': self.x, 'y': self.y, 'z': self.z}

    @classmethod
    def deserialize(cls, src: dict) -> _Components:
        return cls(x=src['x'], y=src['y'], z=src['z'])


@dataclass
class Position(_Components):
    km2: Optional[Km2] = None  # the Km2 the ship is over while bound; not saved, found again on load
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Velocity(_Components):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
