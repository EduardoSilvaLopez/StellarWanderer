"""What a ship cannot fly through, shared by the solids of the portal base and of the outposts. A solid gives the
signed distance to its surface (negative inside), in its own frame. The ship is its hull box, of the half sizes
given, turned by its attitude: its surface is checked at points spread over it (`_hull_samples`).

The ship is pushed out of a solid along its normal, and its speed toward the solid is forced down so that the hull
comes to rest against it: each point of it may close in at most as many m/s as the metres left, and the hull is never
left inside. The speed along the surface is kept. Nothing is damaged. The motion of a frame is swept, in steps of
SWEEP_STEP, so that a wall is not passed through in one frame (Navigation._collide_with_portal_base and
Navigation._collide_with_outposts).
"""

from __future__ import annotations
import functools
import math
from abc import ABC, abstractmethod
from typing import Optional

GRADIENT_STEP = 1e-4  # m, for the normal of the surface: small, so that it is never the mean of two walls in a corner
SAMPLE_STEP = 2.0  # m, about the spacing of the points of the hull's surface that are checked against the solids
SWEEP_STEP = 0.5  # m, the most the hull moves between two checks: less than the thinnest wall (the hangar's, 1 m)
SKEW = (0.0031, 0.0047, 0.0059)  # m, a direction that is parallel to no wall, to tell the two sides of a corner
ITERATIONS = 3  # a corner needs the ship pushed out of more than one surface
Vec = tuple[float, float, float]


def hull_radius(half_sizes: Vec) -> float:
    """m, from the camera to a corner of a hull box of these half sizes (right, up, forward)."""
    return math.sqrt(sum(half * half for half in half_sizes))


@functools.lru_cache(maxsize=None)
def _hull_samples(half_sizes: Vec) -> tuple[Vec, ...]:
    """Points on the surface of a hull box of these half sizes, in its own axes (right, up, forward), spread at most
    SAMPLE_STEP apart, so that each face is covered and its edges are points. A solid at least one spacing thick cannot
    pass between two of them."""
    counts = [max(1, round(half / SAMPLE_STEP)) for half in half_sizes]
    steps = [half / count for half, count in zip(half_sizes, counts)]
    samples = []
    for i in range(-counts[0], counts[0] + 1):
        for j in range(-counts[1], counts[1] + 1):
            for k in range(-counts[2], counts[2] + 1):
                if abs(i) == counts[0] or abs(j) == counts[1] or abs(k) == counts[2]:
                    samples.append((i * steps[0], j * steps[1], k * steps[2]))
    return tuple(samples)


def _turned(sample: Vec, right: Vec, up: Vec, forward: Vec) -> Vec:
    """A point of the hull, given in its own axes, in the frame of the solid (the ship's axes are in that frame)."""
    return tuple(sample[0] * right[k] + sample[1] * up[k] + sample[2] * forward[k] for k in range(3))


def box_distance(x: float, y: float, z: float, cx: float, cy: float, cz: float,
                 hx: float, hy: float, hz: float) -> float:
    """The signed distance to a box of half sizes (hx, hy, hz) round (cx, cy, cz)."""
    qx, qy, qz = abs(x - cx) - hx, abs(y - cy) - hy, abs(z - cz) - hz
    return math.sqrt(max(qx, 0.0) ** 2 + max(qy, 0.0) ** 2 + max(qz, 0.0) ** 2) + min(max(qx, qy, qz), 0.0)


class Solid(ABC):
    """A solid in its own frame. `distance` is its signed distance, and `reach` the distance from the frame's origin
    beyond which it cannot touch a hull of these half sizes."""

    @abstractmethod
    def distance(self, x: float, y: float, z: float) -> float:
        """The signed distance from the point to the nearest surface (negative inside), in the solid's frame."""

    @abstractmethod
    def reach(self, half_sizes: Vec) -> float:
        """m from the frame's origin, beyond which the solid cannot touch a hull of these half sizes."""

    def resolve(self, position: Vec, velocity: Vec, right: Vec, up: Vec, forward: Vec, half_sizes: Vec
                ) -> Optional[tuple[Vec, Vec]]:
        """The camera's position and the velocity (in the solid's frame) once the hull cannot go through anything, or
        None if they stay as they are. `right`, `up` and `forward` are the ship's axes, in the same frame, and
        `half_sizes` the half of its hull's width, height and depth."""
        x, y, z = position
        vx, vy, vz = velocity
        if self.distance(x, y, z) - hull_radius(half_sizes) > math.sqrt(vx * vx + vy * vy + vz * vz):
            return None  # the hull cannot close in faster than the metres left
        offsets = [_turned(sample, right, up, forward) for sample in _hull_samples(half_sizes)]
        clearances = self._clearances(x, y, z, offsets)
        for _ in range(ITERATIONS):
            inside = [index for index, clearance in enumerate(clearances) if clearance < 0.0]
            if not inside:
                break
            for index in inside:  # pushed out of each point that is in a solid, along its normal
                ox, oy, oz = offsets[index]
                clearance = self.distance(x + ox, y + oy, z + oz)
                if clearance < 0.0:
                    nx, ny, nz = self._normal(x + ox + SKEW[0], y + oy + SKEW[1], z + oz + SKEW[2])
                    x, y, z = x - clearance * nx, y - clearance * ny, z - clearance * nz
            clearances = self._clearances(x, y, z, offsets)
        normals: dict[int, Vec] = {}  # the position is fixed from here on: each normal is taken once
        for _ in range(2):
            for index, (ox, oy, oz) in enumerate(offsets):
                clearance = clearances[index]
                if clearance > math.sqrt(vx * vx + vy * vy + vz * vz):
                    continue  # this point cannot reach the solid in a frame at this speed
                if index not in normals:
                    normals[index] = self._normal(x + ox + SKEW[0], y + oy + SKEW[1], z + oz + SKEW[2])
                nx, ny, nz = normals[index]
                closing = vx * nx + vy * ny + vz * nz
                floor = -max(clearance, 0.0)
                if closing < floor:
                    vx, vy, vz = vx + (floor - closing) * nx, vy + (floor - closing) * ny, vz + (floor - closing) * nz
        if (x, y, z) == tuple(position) and (vx, vy, vz) == tuple(velocity):
            return None
        return (x, y, z), (vx, vy, vz)

    def touches(self, position: Vec, right: Vec, up: Vec, forward: Vec, half_sizes: Vec) -> bool:
        """Whether the hull, with the camera at `position` (in the solid's frame) and the ship's axes, has a point
        inside the solid. `resolve` takes the hull out of it, and also slows it before a surface it has not reached."""
        x, y, z = position
        return any(self.distance(x + ox, y + oy, z + oz) < 0.0
                   for ox, oy, oz in (_turned(sample, right, up, forward) for sample in _hull_samples(half_sizes)))

    def _clearances(self, x: float, y: float, z: float, offsets: list[Vec]) -> list[float]:
        """The signed distance from each point of the hull, the camera at (x, y, z) and the points at `offsets`."""
        return [self.distance(x + ox, y + oy, z + oz) for ox, oy, oz in offsets]

    def _normal(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        step = GRADIENT_STEP
        gx = self.distance(x + step, y, z) - self.distance(x - step, y, z)
        gy = self.distance(x, y + step, z) - self.distance(x, y - step, z)
        gz = self.distance(x, y, z + step) - self.distance(x, y, z - step)
        length = math.sqrt(gx * gx + gy * gy + gz * gz) or 1.0
        return gx / length, gy / length, gz / length
