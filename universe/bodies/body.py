"""A body of a stellar system: the star, the portal base, a world or an asteroid. What navigation needs from any of
them, and the pilot's choice to hide one from the knowledge base: a hidden body has no label and cannot be targeted,
but is still there and drawn. Hidden is saved as an alteration of the body's own, and not hidden is the default."""

from __future__ import annotations
import math
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
    hidden: bool = False  # set by the knowledge base (see set_hidden)

    @property
    def is_shown(self) -> bool:
        """Whether the body gets a label and can be targeted: it is not hidden."""
        return not self.hidden

    def set_hidden(self, hidden: bool) -> None:
        """Hides or shows the body, and marks what it belongs to as altered (hidden is kept with the object)."""
        self.hidden = hidden
        self.set_altered()  # each kind of body has its own (a settlement, a world, a star)

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

    def pull_at(self, distance: float) -> float:
        """m/s^2, the pull at `distance` metres from the centre: a point mass's. A body a ship can enter (a giant) has
        its own inside."""
        return self.gravitational_parameter / distance ** 2

    def dynamical_time(self, distance: float) -> float:
        """Seconds of a circular orbit at `distance` metres from the centre: the time in which the pull changes the
        ship's motion. It bounds the frame's time step (`Navigation.coasting_time_limit`)."""
        return math.tau * math.sqrt(distance ** 3 / self.gravitational_parameter)

    @property
    def stellar_system(self) -> StellarSystem:
        raise NotImplementedError

    def has_settlements(self) -> bool:
        """Whether a ship can dock at this body, or at a settlement on it: what the long distance advice reserves
        supplies and energy for."""
        return False
