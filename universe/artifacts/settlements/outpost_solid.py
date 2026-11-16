"""What a ship cannot fly through at an outpost: its building and, from size 3, the annex behind it. Each is a solid box
standing on the ground and turned by the outpost's orientation, with the door of the building on its local +z (see
graphics/outposts.py). Its frame is the surface frame of the planet (x east, y up, z north) with the origin at the
outpost's place on the ground, which is the frame of a bound ship, so the ship's position and axes are used as they
are (Navigation._collide_with_outposts)."""

from __future__ import annotations
import math
from typing import Sequence

from galaxies.solid import Solid, Vec, box_distance, hull_radius

# A box of the structure: width (local x), height, depth (local z) and where its centre is along local z, in m.
Part = tuple[float, float, float, float]


class OutpostSolid(Solid):
    """The boxes of an outpost's structure, turned by its orientation (degrees, clockwise from north). Its `parts` are
    also what the scanner's beam is tested against."""

    def __init__(self, parts: Sequence[Part], orientation: float) -> None:
        self.parts: tuple[Part, ...] = tuple(parts)
        angle = math.radians(orientation)
        self._cos: float = math.cos(angle)
        self._sin: float = math.sin(angle)
        self._reach: float = max(math.sqrt((width / 2.0) ** 2 + height ** 2 + (abs(centre_z) + depth / 2.0) ** 2)
                                 for width, height, depth, centre_z in self.parts)

    def reach(self, half_sizes: Vec) -> float:
        """m from the outpost's place on the ground, beyond which the structure cannot touch a hull of these half
        sizes."""
        return self._reach + hull_radius(half_sizes)

    def distance(self, x: float, y: float, z: float) -> float:
        """The signed distance from the point to the structure (negative inside), in the surface frame."""
        local_x = x * self._cos - z * self._sin  # the inverse of the rotation the graphics draw the building with
        local_z = x * self._sin + z * self._cos
        return min(box_distance(local_x, y, local_z, 0.0, height / 2.0, centre_z, width / 2.0, height / 2.0,
                                depth / 2.0)
                   for width, height, depth, centre_z in self.parts)
