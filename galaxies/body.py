"""A body of a stellar system: the star or a world. What navigation needs from any of them."""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

from common.vector3 import Vector3

if TYPE_CHECKING:
    from galaxies.stellar_system import StellarSystem


class Body:
    """A spherical body of a stellar system, in the star-centred stellar frame. Every world is one, and so is the star.
    Only a world has a surface the ship can bind to (`is_world`); the star is never bound to."""

    is_world: bool = False
    name: str
    radius: float

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        """The position of the body's centre in the stellar frame, in meters."""
        raise NotImplementedError

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        """The velocity of the body in the stellar frame, in meters per second."""
        raise NotImplementedError

    @property
    def stellar_system(self) -> StellarSystem:
        raise NotImplementedError
