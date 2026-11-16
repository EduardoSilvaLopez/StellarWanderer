"""The Portal of a stellar system: a ring of intense white light, next to the portal base that protects it.

All Portals are the same size, because mankind has not learned to change the design. The radius is a number of Planck
lengths, and that number is the ratio of the electric force to the gravitational force between two protons (it does not
depend on their distance): RADIUS = 19.97 m. The band is thin: its thickness is the fine-structure constant times the
radius.

It hangs beyond the base (further from the star), at `BEYOND_BASE` along the star's z axis and `OFFSET_FROM_AXIS` away
from it, in a direction round the axis that is drawn from the seed (so it is always the same in a system). Its ring lies
in a plane that contains the z direction: a ship arriving from the stars along the axis sees it edge-on, and has to
decelerate and turn to face it. The ring's normal is the horizontal direction from the axis to the Portal.

The Portal is not targeted: the base is. What the base does about a ship that approaches it is in PortalDefence.
"""

from __future__ import annotations
import math
import random
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import numpy as np

from common.vector3 import Vector3
from galaxies import seeds

if TYPE_CHECKING:
    from galaxies.portals.portal_base import PortalBase

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


class Portal:
    """The Portal of a stellar system."""

    RADIUS = PROTON_FORCE_RATIO * PLANCK_LENGTH  # m: the ring's radius, 19.97 m, the same for every Portal
    BAND_THICKNESS = FINE_STRUCTURE * RADIUS  # m: about 14.6 cm
    OFFSET_FROM_AXIS = 1000.0  # m, from the star's z axis: far enough for its light not to disturb the base
    BEYOND_BASE = 1000.0  # m, further from the star than the base

    def __init__(self, base: PortalBase) -> None:
        self.base: PortalBase = base
        self.seed: int = seeds.derive(base.seed, 'portal')
        # The direction round the axis, drawn from the seed: the same in a system whenever it is made again.
        self.azimuth: float = random.Random(self.seed).uniform(0.0, math.tau)
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

    def ring_points(self, count: int) -> np.ndarray:
        """`count` points on the ring's centre line, in the stellar frame (m): (count, 3)."""
        angle = np.linspace(0.0, math.tau, count, endpoint=False)
        centre = np.array(tuple(self.centre))
        tangent = np.array(tuple(self.tangent))
        axis = np.array([0.0, 0.0, 1.0])
        return centre + self.RADIUS * (np.cos(angle)[:, None] * axis + np.sin(angle)[:, None] * tangent)

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
