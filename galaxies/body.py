"""A body of a stellar system: the star, the portal base, a world or an asteroid. What navigation needs from any of
them."""

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
    def gravitational_parameter(self) -> float:
        """G times the body's mass, in m^3/s^2: the pull on a ship inside its fixed zone (Navigation._move_unbound).
        Zero for a body that does not pull: the star does not pull yet, and neither does the portal base."""
        return 0.0

    @property
    def stellar_system(self) -> StellarSystem:
        raise NotImplementedError
