"""What a ship cannot fly through in a portal base: the ring, the hub, the spokes, the thrusters and the hangar, whose
docking place is hollow and closed at its back by the door. The base is described by a signed distance (negative inside
a solid) in its own frame (see graphics/portal_base_shape.py, whose dimensions these are, scaled by the ring's radius
over `REFERENCE_RADIUS`). How a hull is kept out of a solid is in galaxies/solid.py."""

from __future__ import annotations
import math

from galaxies.solid import Solid, Vec, box_distance, hull_radius

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


class PortalBaseSolid(Solid):
    """The solid parts of the portal base of this outer ring radius (m)."""

    def __init__(self, radius: float) -> None:
        self.radius: float = radius
        self._a: float = radius / REFERENCE_RADIUS

    def reach(self, half_sizes: Vec) -> float:
        """m from the ring's centre, beyond which nothing of the base is solid for a hull of these half sizes."""
        return 1.05 * self.radius + hull_radius(half_sizes)

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
        spokes = min(box_distance(ax, ay, z, spoke_centre, 0.0, 0.0, spoke_half, size, size),
                     box_distance(ay, ax, z, spoke_centre, 0.0, 0.0, spoke_half, size, size))
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
        cavity = box_distance(x, y, z, 0.0, 0.0, (open_end + back) / 2.0, MOUTH_WIDTH * a / 2.0, MOUTH_HEIGHT * a / 2.0,
                              (back - open_end) / 2.0)
        return max(prism, -cavity)


def _extruded(section: float, z: float, centre: float, half: float) -> float:
    """The distance to a prism along z whose section has the signed distance `section` at the point."""
    along = abs(z - centre) - half
    return math.hypot(max(section, 0.0), max(along, 0.0)) + min(max(section, along), 0.0)
