"""The star of a stellar system, as a body ships can navigate to."""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

from common.vector3 import Vector3
from galaxies.body import Body

if TYPE_CHECKING:
    from galaxies.stellar_system import StellarSystem


class Star(Body):
    """The star: the origin of the stellar frame, at rest. Its name, radius, colour and mass are the stellar system's
    (the system is generated from them). It has no surface: nothing binds to it."""

    is_world = False

    def __init__(self, system: StellarSystem) -> None:
        self._system: StellarSystem = system
        self.name: str = system.name
        self.radius: float = system.radius
        self.color = system.color
        self.mass: float = system.mass

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @property
    def stellar_system(self) -> StellarSystem:
        return self._system
