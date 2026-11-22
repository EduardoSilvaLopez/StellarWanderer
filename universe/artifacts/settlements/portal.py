"""A Portal of a stellar system: a ring of intense white light, next to the portal base that protects it.

All Portals are the same size, because mankind has not learned to change the design. The radius is a number of Planck
lengths, and that number is the ratio of the electric force to the gravitational force between two protons (it does not
depend on their distance): RADIUS = 19.97 m. The band is thin: its thickness is the fine-structure constant times the
radius.

A system has one Portal for each system it is linked to: the system that settled it, and each one it settled itself (see
`StellarSystem._place_settlements`). The Portals hang beyond the base (further from the star), at `BEYOND_BASE` along
the star's z axis and `OFFSET_FROM_AXIS` away from it, as the corners of a regular polygon round the axis: the first
one's direction is drawn from the seed (so it is always the same in a system), and the others follow at equal angles,
two opposite each other, three 120 degrees apart, and so on. Each ring lies in a plane that contains the z direction: a
ship arriving from the stars along the axis sees it edge-on, and has to decelerate and turn to face it. The ring's
normal is the horizontal direction from the axis to the Portal.

The two ends of a link do not share their attitude: each end is placed as its own base and star ask, as if both stars
were on one axis.

The Portal is a body (`Body`): it can be targeted, and is labelled at the centre of the ring with the system it leads
to. Nothing is fixed to it and it is not solid. What the base does about a ship that approaches it is in
PortalDefence.
"""

from __future__ import annotations
import math
import random
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import numpy as np

from common.vector3 import Vector3
from universe.bodies.body import Body
from universe.structure import seeds
from universe.structure.fixed_stars import Cell

if TYPE_CHECKING:
    from universe.artifacts.settlements.portal_base import PortalBase
    from universe.structure.galaxy import Galaxy
    from universe.structure.stellar_system import StellarSystem

# Physical constants, SI (CODATA 2018).
SPEED_OF_LIGHT = 299792458.0  # m/s
REDUCED_PLANCK = 1.054571817e-34  # J s
GRAVITATIONAL_CONSTANT = 6.67430e-11  # m^3 kg^-1 s^-2
PROTON_MASS = 1.67262192369e-27  # kg
ELEMENTARY_CHARGE = 1.602176634e-19  # C
VACUUM_PERMITTIVITY = 8.8541878128e-12  # F/m

FINE_STRUCTURE = ELEMENTARY_CHARGE ** 2 / (4.0 * math.pi * VACUUM_PERMITTIVITY * REDUCED_PLANCK * SPEED_OF_LIGHT)
PLANCK_LENGTH = math.sqrt(REDUCED_PLANCK * GRAVITATIONAL_CONSTANT / SPEED_OF_LIGHT ** 3)  # m
# The electric force over the gravitational force between two protons, whatever their distance.
PROTON_FORCE_RATIO = ELEMENTARY_CHARGE ** 2 / (4.0 * math.pi * VACUUM_PERMITTIVITY * GRAVITATIONAL_CONSTANT
                                                * PROTON_MASS ** 2)


class Portal(Body):
    """One Portal of a stellar system. It is a body the pilot can target, as the base is, to fly to it: the label of the
    ring's centre reads "System <the one it leads to>". It is not solid (a ship goes through it), and the ship is never
    fixed to it."""

    is_world = False
    is_solid = False
    can_be_fixed_to = False
    RADIUS = PROTON_FORCE_RATIO * PLANCK_LENGTH  # m: the ring's radius, 19.97 m, the same for every Portal
    BAND_THICKNESS = FINE_STRUCTURE * RADIUS  # m: about 14.6 cm
    OFFSET_FROM_AXIS = 1000.0  # m, from the star's z axis: far enough for its light not to disturb the base
    BEYOND_BASE = 1000.0  # m, further from the star than the base

    def __init__(self, base: PortalBase, index: int, count: int, destination: Cell) -> None:
        """The `index`-th of the `count` Portals of the base, linked to the system of the star in cell `destination`."""
        self.base: PortalBase = base
        self.index: int = index
        self.destination: Cell = destination
        self.radius: float = self.RADIUS
        self._other_end: Optional[Portal] = None  # found the first time it is asked for (see other_end)
        self.seed: int = seeds.derive(base.seed, 'portal')
        # The direction round the axis: the first Portal's is drawn from the seed (the same in a system whenever it is
        # made again), and the others are the corners of the regular polygon from it.
        self.azimuth: float = (random.Random(self.seed).uniform(0.0, math.tau) + math.tau * index / count) % math.tau
        out = Vector3(math.cos(self.azimuth), math.sin(self.azimuth), 0.0)
        self.centre: Vector3 = Vector3(out.x * self.OFFSET_FROM_AXIS, out.y * self.OFFSET_FROM_AXIS,
                                       base.height + self.BEYOND_BASE)
        self.normal: Vector3 = out  # horizontal, from the axis to the Portal: the ring's face looks along it
        self.tangent: Vector3 = Vector3(-out.y, out.x, 0.0)  # in the ring's plane, with the z direction
        # What PortalDefence remembers (not saved): the last warning given, where they start again, the last check
        self.warning_stage: int = 0
        self.stage_distance: float = 0.0  # m: where the last warning was given
        self.rearm_distance: float = 0.0  # m: the warnings start again when the ship is farther than this
        self.checked_at: Optional[datetime] = None

    @property
    def name(self) -> str:
        """What the pilot reads on the ring: the system it leads to (the star's name is known without making it)."""
        star = self.base.stellar_system.parent_galaxy.stars.star_at(self.destination)
        return f"System {star.name}" if star is not None else "System"

    @property
    def stellar_system(self) -> StellarSystem:
        return self.base.stellar_system

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        return self.centre

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    def ring_points(self, count: int) -> np.ndarray:
        """`count` points on the ring's centre line, in the stellar frame (m): (count, 3)."""
        angle = np.linspace(0.0, math.tau, count, endpoint=False)
        centre = np.array(tuple(self.centre))
        tangent = np.array(tuple(self.tangent))
        axis = np.array([0.0, 0.0, 1.0])
        return centre + self.RADIUS * (np.cos(angle)[:, None] * axis + np.sin(angle)[:, None] * tangent)

    def other_end(self, galaxy: Galaxy, generate: bool = True) -> Optional[Portal]:
        """The Portal at the other end of the link, in the system it leads to (which is made if it was not yet, unless
        `generate` is False: making a system takes a noticeable time, which the pilot must not feel in a frame that
        has other things to do). None if there is no such Portal, or if it is not made and may not be."""
        if self._other_end is None:
            key = ' '.join(str(coordinate) for coordinate in self.destination)
            system = galaxy.system_of_key(key) if generate else galaxy.existing_system_of_key(key)
            here = self.base.stellar_system.star.cell
            if system is not None:
                self._other_end = next((portal for portal in system.portals if portal.destination == here), None)
        return self._other_end

    def crossing(self, start: Vector3, end: Vector3) -> Optional[float]:
        """The fraction of a straight move from the stellar-frame `start` to `end` at which it goes through the opening
        of the ring, from either side; None if it stays on one side or passes outside the ring. A ship that goes
        through always crosses: the Portal is open to everyone, and only the base's defence (PortalDefence) may stop it."""
        before = (start - self.centre).dot(self.normal)
        after = (end - self.centre).dot(self.normal)
        if (before <= 0.0) == (after <= 0.0):
            return None
        fraction = before / (before - after)
        point = start + (end - start) * fraction
        return fraction if (point - self.centre).length() <= self.RADIUS else None

    def carry(self, other: Portal, vector: Vector3) -> Vector3:
        """A displacement or a direction in the stellar frame at this Portal, as it is at the `other` end of the link:
        turned about the base axis (the z axis, in both systems) by the difference of the two Portals' directions. Each
        end is placed as its own base and star ask, as if both stars were on one axis, so this is all the link turns."""
        turn = other.azimuth - self.azimuth
        cosine, sine = math.cos(turn), math.sin(turn)
        return Vector3(vector.x * cosine - vector.y * sine, vector.x * sine + vector.y * cosine, vector.z)

    def arrival_time(self, position: Vector3, velocity: Vector3, radius: float) -> Optional[float]:
        """The seconds until a ship at the stellar-frame `position`, moving in a straight line at `velocity`, is within
        `radius` of the Portal's centre: 0 for a ship that is already inside and is not moving away, None for one that
        never gets there."""
        relative = position - self.centre
        along = relative.dot(velocity)
        if relative.dot(relative) <= radius * radius:
            return 0.0 if along <= 0.0 else None
        speed_squared = velocity.dot(velocity)
        if speed_squared == 0.0 or along >= 0.0:
            return None
        discriminant = along * along - speed_squared * (relative.dot(relative) - radius * radius)
        if discriminant < 0.0:
            return None
        return (-along - math.sqrt(discriminant)) / speed_squared
