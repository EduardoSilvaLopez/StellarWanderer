"""What a ship cannot fly through in a portal base: the ring, the hub, the spokes, the thrusters and the hangar, whose
docking place is hollow and closed at its back by the door. The base is described by a signed distance (negative inside
a solid) in its own frame (see graphics/portal_base_shape.py, whose dimensions these are, scaled by the ring's radius
over `REFERENCE_RADIUS`). The ship is its hull box, of the WIDTH, HEIGHT and DEPTH its configuration gives, round the
camera (which is at the middle of the hull, as the legs are retracted in space), turned by its attitude: its surface is
checked at points spread over it (`_hull_samples`).

As with the ground of a world (Navigation._update_position), the speed toward the nearest surface is forced down so that
the hull comes to rest against it: each point of it may close in at most as many m/s as the metres left, and the hull is
never left inside. The speed along the surface is kept. Nothing is damaged."""

from __future__ import annotations
import functools
import math
from typing import Optional

REFERENCE_RADIUS = 100.0  # m, the outer radius of the ring that the dimensions below are for

RING_THICKNESS = 10.0
RING_WIDTH = 15.0
HUB_RADIUS = 9.0
HUB_LENGTH = 8.0
SPOKE_SIZE = 2.5
HANGAR_WIDTH = 12.0
HANGAR_HEIGHT = 10.0
HANGAR_CHAMFER = 1.0
MOUTH_DEPTH = 48.0  # from the ring's centre to the mouth
MOUTH_WIDTH = 10.0
MOUTH_HEIGHT = 8.0
DOCKING_DEPTH = 19.0
THRUSTER_RADIUS = 3.0 * 1.25  # at its flared exit
THRUSTER_LENGTH = 10.0

GRADIENT_STEP = 1e-4  # m, for the normal of the surface: small, so that it is never the mean of two walls in a corner
SAMPLE_STEP = 2.0  # m, about the spacing of the points of the hull's surface that are checked against the solids
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
    pass between two of them, and the thinnest parts of the base (its spokes) are wider."""
    counts = [max(1, round(half / SAMPLE_STEP)) for half in half_sizes]
    steps = [half / count for half, count in zip(half_sizes, counts)]
    samples = []
    for i in range(-counts[0], counts[0] + 1):
        for j in range(-counts[1], counts[1] + 1):
            for k in range(-counts[2], counts[2] + 1):
                if abs(i) == counts[0] or abs(j) == counts[1] or abs(k) == counts[2]:
                    samples.append((i * steps[0], j * steps[1], k * steps[2]))
    return tuple(samples)


class PortalBaseSolid:
    """The solid parts of the portal base of this outer ring radius (m)."""

    def __init__(self, radius: float) -> None:
        self.radius: float = radius
        self._a: float = radius / REFERENCE_RADIUS

    def reach(self, half_sizes: Vec) -> float:
        """m from the ring's centre, beyond which nothing of the base is solid for a hull of these half sizes."""
        return 1.05 * self.radius + hull_radius(half_sizes)

    def resolve(self, position: Vec, velocity: Vec, right: Vec, up: Vec, forward: Vec, half_sizes: Vec
                ) -> Optional[tuple[Vec, Vec]]:
        """The camera's position and the velocity (in the base's frame) once the hull cannot go through anything, or
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

    def distance(self, x: float, y: float, z: float) -> float:
        """The signed distance from the point to the nearest solid (negative inside), in the base's frame: z along the
        ring's axis, the star toward -z."""
        a = self._a
        radius = self.radius
        inner = radius - RING_THICKNESS * a
        hub_half = HUB_LENGTH * a / 2.0
        ring_distance = math.hypot(x, y)
        ax, ay = abs(x), abs(y)

        ring = _extruded(max(ring_distance - radius, inner - ring_distance), z, 0.0, RING_WIDTH * a / 2.0)
        hub = _extruded(ring_distance - HUB_RADIUS * a, z, 0.0, hub_half)
        spoke_start, spoke_end = HUB_RADIUS * a - 0.5, inner + 0.5
        spoke_centre, spoke_half = (spoke_start + spoke_end) / 2.0, (spoke_end - spoke_start) / 2.0
        size = SPOKE_SIZE * a / 2.0
        spokes = min(_box(ax, ay, z, spoke_centre, 0.0, 0.0, spoke_half, size, size),
                     _box(ay, ax, z, spoke_centre, 0.0, 0.0, spoke_half, size, size))
        thruster_centre = (radius - RING_THICKNESS * a / 2.0) * math.sqrt(0.5)
        thrusters = _extruded(math.hypot(ax - thruster_centre, ay - thruster_centre) - THRUSTER_RADIUS * a, z,
                              -RING_WIDTH * a / 2.0 - THRUSTER_LENGTH * a / 2.0, THRUSTER_LENGTH * a / 2.0)
        return min(ring, hub, spokes, thrusters, self._hangar(x, y, z))

    def _hangar(self, x: float, y: float, z: float) -> float:
        """The hangar: an octagonal prism with the docking place cut out of it, open at the mouth."""
        a = self._a
        half_w, half_h = HANGAR_WIDTH * a / 2.0, HANGAR_HEIGHT * a / 2.0
        mouth_z = -MOUTH_DEPTH * a
        hub_front = -HUB_LENGTH * a / 2.0
        ax, ay = abs(x), abs(y)
        section = max(ax - half_w, ay - half_h, (ax + ay - (half_w + half_h - HANGAR_CHAMFER * a)) * math.sqrt(0.5))
        prism = _extruded(section, z, (mouth_z + hub_front) / 2.0, (hub_front - mouth_z) / 2.0)
        open_end = mouth_z - 2.0 * self.radius  # the cavity goes on far out of the mouth, so that it has no lid there
        back = mouth_z + DOCKING_DEPTH * a
        cavity = _box(x, y, z, 0.0, 0.0, (open_end + back) / 2.0, MOUTH_WIDTH * a / 2.0, MOUTH_HEIGHT * a / 2.0,
                      (back - open_end) / 2.0)
        return max(prism, -cavity)


def _turned(sample: Vec, right: Vec, up: Vec, forward: Vec) -> Vec:
    """A point of the hull, given in its own axes, in the frame of the base (the ship's axes are in that frame)."""
    return tuple(sample[0] * right[k] + sample[1] * up[k] + sample[2] * forward[k] for k in range(3))


def _extruded(section: float, z: float, centre: float, half: float) -> float:
    """The distance to a prism along z whose section has the signed distance `section` at the point."""
    along = abs(z - centre) - half
    return math.hypot(max(section, 0.0), max(along, 0.0)) + min(max(section, along), 0.0)


def _box(x: float, y: float, z: float, cx: float, cy: float, cz: float, hx: float, hy: float, hz: float) -> float:
    """The signed distance to a box of half sizes (hx, hy, hz) round (cx, cy, cz)."""
    qx, qy, qz = abs(x - cx) - hx, abs(y - cy) - hy, abs(z - cz) - hz
    return math.sqrt(max(qx, 0.0) ** 2 + max(qy, 0.0) ** 2 + max(qz, 0.0) ** 2) + min(max(qx, qy, qz), 0.0)
