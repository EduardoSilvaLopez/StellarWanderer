"""The shape of a portal base as triangles, in metres, in the base's own frame: z is the axis of the ring (the star
is toward -z), x and y are the width and the height of the hangar.

At a ring radius of 100 m (`REFERENCE_RADIUS`) the parts are, from the outside in:
  * the ring: 10 m thick (radially) and 15 m wide, spinning. The floor is just inside its outer wall.
  * four spokes, 2.5 x 2.5 m, at 0, 90, 180 and 270 degrees, from the hub to the ring (the lifts go along them).
  * the hub: a cylinder of 9 m of radius and 8 m long, spinning, where the spokes meet. Behind the hangar.
  * the hangar: a box of 12 m wide, 10 high and 44 deep, its four long edges cut (an octagon with four short sides
    in the corners), that does not spin. Its rear end is the hub's front end, so it
    sticks out in front of the ring (toward the star). Its mouth, 10 x 8 m, opens on the docking place, 19 m deep
    (the interior is only drawn from the outside, `interior`), and behind it the hangar is closed: the parking of
    other ships, only suggested.
  * four ion thrusters on the ring's face that looks at the star, at 45 degrees between the spokes.
  * inside the docking place (seen from the mouth): the rails of the arms along the ceiling, and a sliding door at
    its back in two leaves, in a frame.
Every dimension grows in proportion to the ring's radius, but the textures keep their size in metres: a bigger base
has more plating and more windows, not bigger ones (the textures are in tools/generate_portal_base_texture.py).

The light is the star's alone and is parallel to the axis, so a face is lit by how much it looks at the star and nothing
changes as the ring spins: the lighting is baked into the colours of the vertices once.

The result is a `BaseModel`: groups of vertices that the renderer (graphics/portal_base_gl.py) draws with their own
texture, those that spin with the ring and those that do not."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

REFERENCE_RADIUS = 100.0  # m, the outer radius of the ring that the dimensions below are for

RING_THICKNESS = 10.0
RING_WIDTH = 15.0
HUB_RADIUS = 9.0
HUB_LENGTH = 8.0
SPOKE_SIZE = 2.5
SPOKE_TILE = 8.0  # m that the spoke texture covers
SIDE_TILE = 32.0  # m that the side texture covers, along the wall (its band is the first 10 m across)
HANGAR_WIDTH = 12.0
HANGAR_HEIGHT = 10.0
HANGAR_DEPTH = 44.0
HANGAR_CHAMFER = 1.0  # m cut off each of the four long edges of the hangar, along each side of the corner
MOUTH_WIDTH = 10.0
MOUTH_HEIGHT = 8.0
DOCKING_DEPTH = 19.0  # the docking place, from the mouth
THRUSTER_RADIUS = 3.0
THRUSTER_LENGTH = 10.0

HULL_TILE = 32.0  # m that the hull texture covers
PLAIN_PLATING = 0.8  # from here to the end of it (v) nothing shines: the frame of the mouth uses that part
INTERIOR_TILE = 16.0  # m that the interior texture covers
RAIL_SIZE = 0.6  # m, square, of the rails of the arms
DOOR_SEAM = 0.3  # m, the half of the gap between the two leaves of the door, at the middle
DOOR_FRAME = 0.6  # m, the width of the frame round the door, and how far it stands out (DOOR_FRAME_DEPTH)
DOOR_FRAME_DEPTH = 0.4
SEGMENTS_PER_TILE = 6  # round a wall, so that its silhouette is round

AMBIENT = 0.26  # of the light on a face that does not look at the star
AMBIENT_REAR = 0.16  # on a face that looks away from it
AMBIENT_INTERIOR = 0.32  # in the docking place, which is dark, with a few lamps
AMBIENT_DOOR = 0.2  # on the doors and the ramp, which are darker than the walls

MARKS_SIZE = (1024, 512)  # the marks sheet; its rectangles (x, y, w, h) match tools/generate_portal_base_texture.py
NUMBERS = [(0, 0, 256, 256), (256, 0, 256, 256), (512, 0, 256, 256), (768, 0, 256, 256)]
STRIPES = (0, 272, 768, 64)
CHEVRON = (784, 272, 224, 224)

# The hangar's own atlas (portal_base_hangar.png, 20 pixels per metre of the faces): the four sides of the box, as
# (x, y, w, h). A side runs from the mouth (u = 0) to the hub (u = 1) and from its top (v = 0) down; the top and
# the bottom run across the width (u) and from the mouth to the hub (v). They must match the generator's layout
# in tools/generate_portal_base_texture.py.
HANGAR_ATLAS = (2048, 1024)
LEFT_SIDE = (0, 0, 880, 200)
RIGHT_SIDE = (0, 208, 880, 200)
TOP = (896, 0, 240, 880)
BOTTOM = (1152, 0, 240, 880)
CHAMFER = (1408, 0, 32, 880)  # a cut corner: across it runs from the side face to the top or bottom one

Vector = tuple[float, float, float]


@dataclass(frozen=True)
class Mesh:
    """Triangles: a position, a texture coordinate and a baked colour for each vertex."""
    positions: np.ndarray  # (n, 3) float32
    uvs: np.ndarray  # (n, 2) float32
    colours: np.ndarray  # (n, 3) uint8


@dataclass(frozen=True)
class BaseModel:
    """A portal base ready to draw. `spinning` and `fixed` are what the ring carries and what the hangar is."""
    radius: float
    scale: float
    spinning_hull: Mesh
    spokes: Mesh
    sides: Mesh  # the two side walls of the ring, with the windows where people stand
    fixed_hull: Mesh  # the frame of the mouth
    hangar: Mesh  # the outer sides of the hangar, with its own atlas
    interior: Mesh
    doors: Mesh  # the ramp and the doors of the docking place: darker, with the interior texture
    spinning_marks: Mesh
    fixed_marks: Mesh
    nozzles: list[Vector]  # where the plume of each thruster begins, in the spinning frame
    bounding_radius: float  # m, of a sphere round the origin that holds the base, without the plumes
    plume_start_z: float  # m, the z of the thrusters' exits


class Builder:
    """Collects the triangles of one group."""

    def __init__(self, sun_colour: tuple[int, int, int], ambient: float = AMBIENT) -> None:
        self._ambient: float = ambient
        self._positions: list[Vector] = []
        self._uvs: list[tuple[float, float]] = []
        self._colours: list[tuple[int, int, int]] = []
        self._sun = np.array(sun_colour, dtype=np.float32) / 255.0

    def shade(self, normal: Vector) -> tuple[int, int, int]:
        """The baked colour of a face with this outward normal: the star's light where it looks at the star (-z)."""
        lit = max(0.0, -normal[2])
        ambient = self._ambient - (self._ambient - AMBIENT_REAR) * max(0.0, normal[2])
        value = ambient + (1.0 - ambient) * lit * self._sun
        return tuple(int(255 * min(1.0, channel)) for channel in value)

    def quad(self, points: list[Vector], uvs: list[tuple[float, float]], normal: Vector) -> None:
        """A quad (corners in order) as two triangles."""
        colour = self.shade(normal)
        for index in (0, 1, 2, 0, 2, 3):
            self._positions.append(points[index])
            self._uvs.append(uvs[index])
            self._colours.append(colour)

    def polygon(self, points: list[Vector], uvs: list[tuple[float, float]], normal: Vector) -> None:
        """A convex polygon (corners in order) as a fan of triangles."""
        colour = self.shade(normal)
        for index in range(1, len(points) - 1):
            for corner in (0, index, index + 1):
                self._positions.append(points[corner])
                self._uvs.append(uvs[corner])
                self._colours.append(colour)

    def build(self) -> Mesh:
        if not self._positions:
            return Mesh(np.zeros((0, 3), np.float32), np.zeros((0, 2), np.float32), np.zeros((0, 3), np.uint8))
        return Mesh(np.array(self._positions, np.float32), np.array(self._uvs, np.float32),
                    np.array(self._colours, np.uint8))


def _add(*terms: tuple[float, Vector]) -> Vector:
    return tuple(sum(factor * vector[axis] for factor, vector in terms) for axis in range(3))


def oriented_box(builder: Builder, axes: tuple[Vector, Vector, Vector], ranges: tuple[tuple[float, float], ...],
                 tile: float, skip: tuple[int, ...] = (), uv_of: Callable | None = None) -> None:
    """A box with a texture of `tile` metres: its sides are the ranges along each of three perpendicular axes. `skip`
    lists the faces not made, as 0 and 1 for the low and high end of the first axis, 2 and 3 of the second, 4 and 5
    of the third. The texture runs along the other two axes of the face, in metres, unless `uv_of(axis, high, a, b)`
    gives the texture coordinates of a corner, where a and b are its coordinates along those two axes."""
    for axis in range(3):
        other_a, other_b = [index for index in range(3) if index != axis]
        for high in (0, 1):
            if 2 * axis + high in skip:
                continue
            fixed = ranges[axis][high]
            (a0, a1), (b0, b1) = ranges[other_a], ranges[other_b]
            corners = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
            points = [_add((fixed, axes[axis]), (a, axes[other_a]), (b, axes[other_b])) for a, b in corners]
            sign = 1.0 if high else -1.0
            normal = tuple(sign * component for component in axes[axis])
            if uv_of is None:
                uvs = [(a / tile, b / tile) for a, b in corners]
            else:
                uvs = [uv_of(axis, high, a, b) for a, b in corners]
            builder.quad(points, uvs, normal)


def wall(builder: Builder, radius: float, z0: float, z1: float, outward: bool, tile: float) -> None:
    """The wall of a cylinder round the z axis, with a whole number of tiles round it."""
    tiles = max(1, round(math.tau * radius / tile))
    segments = SEGMENTS_PER_TILE * tiles
    sign = 1.0 if outward else -1.0
    for index in range(segments):
        angles = [math.tau * index / segments, math.tau * (index + 1) / segments]
        us = [tiles * index / segments, tiles * (index + 1) / segments]
        points, uvs = [], []
        for angle, u in zip(angles, us):
            for z in (z0, z1):
                points.append((radius * math.cos(angle), radius * math.sin(angle), z))
                uvs.append((u, (z - z0) / tile))
        middle = 0.5 * (angles[0] + angles[1])
        builder.quad([points[0], points[2], points[3], points[1]], [uvs[0], uvs[2], uvs[3], uvs[1]],
                     (sign * math.cos(middle), sign * math.sin(middle), 0.0))


def annulus(builder: Builder, z: float, inner: float, outer: float, normal_z: float, tile: float) -> None:
    """A flat ring round the z axis: its texture runs along the angle, and across it from the inner edge."""
    tiles = max(1, round(math.tau * outer / tile))
    segments = SEGMENTS_PER_TILE * tiles
    for index in range(segments):
        angles = [math.tau * index / segments, math.tau * (index + 1) / segments]
        us = [tiles * index / segments, tiles * (index + 1) / segments]
        if normal_z < 0.0:  # seen from the star's side, the angle runs the other way: the text must not be mirrored
            us = [tiles - u for u in us]
        points = [(inner * math.cos(angles[0]), inner * math.sin(angles[0]), z),
                  (outer * math.cos(angles[0]), outer * math.sin(angles[0]), z),
                  (outer * math.cos(angles[1]), outer * math.sin(angles[1]), z),
                  (inner * math.cos(angles[1]), inner * math.sin(angles[1]), z)]
        uvs = [(us[0], 0.0), (us[0], (outer - inner) / tile), (us[1], (outer - inner) / tile), (us[1], 0.0)]
        builder.quad(points, uvs, (0.0, 0.0, normal_z))


def disc(builder: Builder, z: float, radius: float, normal_z: float, tile: float, segments: int = 32) -> None:
    for index in range(segments):
        a0, a1 = math.tau * index / segments, math.tau * (index + 1) / segments
        points = [(0.0, 0.0, z), (radius * math.cos(a0), radius * math.sin(a0), z),
                  (radius * math.cos(a1), radius * math.sin(a1), z), (0.0, 0.0, z)]
        uvs = [(0.0, 0.0), (radius * math.cos(a0) / tile, radius * math.sin(a0) / tile),
               (radius * math.cos(a1) / tile, radius * math.sin(a1) / tile), (0.0, 0.0)]
        builder.quad(points, uvs, (0.0, 0.0, normal_z))


def thruster(builder: Builder, centre: tuple[float, float], z0: float, z1: float, radius: float,
             flare: float) -> None:
    """A thruster: a round housing from the face of the ring (z0) to its exit (z1, farther from the star), widening
    over the last `flare` metres."""
    segments = 20
    flare_start = z1 + flare
    for index in range(segments):
        angles = [math.tau * index / segments, math.tau * (index + 1) / segments]
        middle = 0.5 * (angles[0] + angles[1])
        for z_a, z_b, r_a, r_b in ((z0, flare_start, radius, radius), (flare_start, z1, radius, radius * 1.25)):
            points = [(centre[0] + r * math.cos(angle), centre[1] + r * math.sin(angle), z)
                      for angle in angles for r, z in ((r_a, z_a), (r_b, z_b))]
            uvs = [(radius * angle / HULL_TILE, (z - z0) / HULL_TILE) for angle in angles for z in (z_a, z_b)]
            builder.quad([points[0], points[2], points[3], points[1]], [uvs[0], uvs[2], uvs[3], uvs[1]],
                         (math.cos(middle), math.sin(middle), 0.0))
        rim = [(centre[0] + radius * 1.25 * math.cos(angle), centre[1] + radius * 1.25 * math.sin(angle), z1)
               for angle in angles]
        inner = [(centre[0] + radius * 0.9 * math.cos(angle), centre[1] + radius * 0.9 * math.sin(angle), z1)
                 for angle in angles]
        builder.quad([inner[0], rim[0], rim[1], inner[1]], [(0.0, 0.0)] * 4, (0.0, 0.0, -1.0))


def _atlas_uv(region: tuple[int, int, int, int], u: float, v: float) -> tuple[float, float]:
    """The texture coordinates of the point (u, v) of a region of the hangar atlas, with v = 0 at its top."""
    x, y, w, h = region
    return (x + u * w) / HANGAR_ATLAS[0], (y + v * h) / HANGAR_ATLAS[1]


def marks_rect(region: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    """(u0, v0, u1, v1) of a rectangle of the marks sheet."""
    x, y, w, h = region
    return x / MARKS_SIZE[0], y / MARKS_SIZE[1], (x + w) / MARKS_SIZE[0], (y + h) / MARKS_SIZE[1]


def make_model(radius: float, sun_colour: tuple[int, int, int] = (255, 255, 255)) -> BaseModel:
    """The model of a base of this outer ring radius (m), lit by a star of this colour."""
    a = radius / REFERENCE_RADIUS
    half_width = RING_WIDTH * a / 2.0
    inner_radius = radius - RING_THICKNESS * a
    hub_front = -HUB_LENGTH * a / 2.0
    mouth_z = hub_front - HANGAR_DEPTH * a
    x_axis, y_axis, z_axis = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    hull_tile, inner_tile = HULL_TILE, INTERIOR_TILE

    spinning = Builder(sun_colour)
    wall(spinning, radius, -half_width, half_width, True, hull_tile)
    wall(spinning, inner_radius, -half_width, half_width, False, hull_tile)
    sides = Builder(sun_colour)
    annulus(sides, -half_width, inner_radius, radius, -1.0, SIDE_TILE)
    annulus(sides, half_width, inner_radius, radius, 1.0, SIDE_TILE)
    wall(spinning, HUB_RADIUS * a, hub_front, -hub_front, True, hull_tile)
    disc(spinning, hub_front, HUB_RADIUS * a, -1.0, hull_tile)
    disc(spinning, -hub_front, HUB_RADIUS * a, 1.0, hull_tile)
    spokes = Builder(sun_colour)
    for step in range(4):
        angle = step * math.pi / 2.0
        along = (math.cos(angle), math.sin(angle), 0.0)
        across = (-math.sin(angle), math.cos(angle), 0.0)
        half = SPOKE_SIZE * a / 2.0
        oriented_box(spokes, (along, across, z_axis),
                     ((HUB_RADIUS * a - 0.5, inner_radius + 0.5), (-half, half), (-half, half)), SPOKE_TILE,
                     skip=(0, 1))
    nozzles: list[Vector] = []
    thruster_z = -half_width - THRUSTER_LENGTH * a
    for step in range(4):
        angle = math.pi / 4.0 + step * math.pi / 2.0
        centre = ((radius - RING_THICKNESS * a / 2.0) * math.cos(angle),
                  (radius - RING_THICKNESS * a / 2.0) * math.sin(angle))
        thruster(spinning, centre, -half_width, thruster_z, THRUSTER_RADIUS * a, 2.0 * a)
        nozzles.append((centre[0], centre[1], thruster_z))

    fixed = Builder(sun_colour)
    half_w, half_h = HANGAR_WIDTH * a / 2.0, HANGAR_HEIGHT * a / 2.0
    hangar = Builder(sun_colour)
    length = hub_front - mouth_z

    def hangar_uv(axis: int, high: bool, a_coord: float, b_coord: float) -> tuple[float, float]:
        if axis == 0:  # a side: a is the height, b the depth
            return _atlas_uv(RIGHT_SIDE if high else LEFT_SIDE, (b_coord - mouth_z) / length,
                             (half_h - a_coord) / (2.0 * half_h))
        return _atlas_uv(TOP if high else BOTTOM, (a_coord + half_w) / (2.0 * half_w), (b_coord - mouth_z) / length)

    cut = HANGAR_CHAMFER * a
    oriented_box(hangar, (x_axis, y_axis, z_axis), ((-half_w, half_w), (-(half_h - cut), half_h - cut),
                                                    (mouth_z, hub_front)), hull_tile, skip=(2, 3, 4, 5), uv_of=hangar_uv)
    oriented_box(hangar, (x_axis, y_axis, z_axis), ((-(half_w - cut), half_w - cut), (-half_h, half_h),
                                                    (mouth_z, hub_front)), hull_tile, skip=(0, 1, 4, 5), uv_of=hangar_uv)
    for sx, sy in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)):  # the cut corners, with their lights
        ends = [(sx * half_w, sy * (half_h - cut), mouth_z), (sx * (half_w - cut), sy * half_h, mouth_z),
                (sx * (half_w - cut), sy * half_h, hub_front), (sx * half_w, sy * (half_h - cut), hub_front)]
        hangar.quad(ends, [_atlas_uv(CHAMFER, across, (z - mouth_z) / length)
                           for across, z in ((0.0, mouth_z), (1.0, mouth_z), (1.0, hub_front), (0.0, hub_front))],
                    (sx * math.sqrt(0.5), sy * math.sqrt(0.5), 0.0))
    mouth_w, mouth_h = MOUTH_WIDTH * a / 2.0, MOUTH_HEIGHT * a / 2.0
    for outline, y0, y1 in (
            ([(-half_w, mouth_h), (half_w, mouth_h), (half_w, half_h - cut), (half_w - cut, half_h),
              (-half_w + cut, half_h), (-half_w, half_h - cut)], mouth_h, half_h),
            ([(-half_w, -mouth_h), (-half_w, -half_h + cut), (-half_w + cut, -half_h), (half_w - cut, -half_h),
              (half_w, -half_h + cut), (half_w, -mouth_h)], -half_h, -mouth_h),
            ([(-half_w, -mouth_h), (-mouth_w, -mouth_h), (-mouth_w, mouth_h), (-half_w, mouth_h)], -mouth_h, mouth_h),
            ([(mouth_w, -mouth_h), (half_w, -mouth_h), (half_w, mouth_h), (mouth_w, mouth_h)], -mouth_h, mouth_h)):
        fixed.polygon([(x, y, mouth_z) for x, y in outline],
                      [(x / hull_tile, PLAIN_PLATING + (1.0 - PLAIN_PLATING) * (y - y0) / (y1 - y0))
                       for x, y in outline], (0.0, 0.0, -1.0))

    # The docking place seen from the mouth: a box whose faces look inward, with the light of the lamps baked in.
    interior = Builder(sun_colour, AMBIENT_INTERIOR)
    doors = Builder(sun_colour, AMBIENT_DOOR)
    back_z = mouth_z + DOCKING_DEPTH * a
    oriented_box(interior, (x_axis, y_axis, z_axis), ((-mouth_w, mouth_w), (-mouth_h, mouth_h), (mouth_z, back_z)),
                 inner_tile, skip=(4, 5))
    interior.quad([(-mouth_w, -mouth_h, back_z), (mouth_w, -mouth_h, back_z), (mouth_w, mouth_h, back_z),
                   (-mouth_w, mouth_h, back_z)],
                  [(-mouth_w / inner_tile, -mouth_h / inner_tile), (mouth_w / inner_tile, -mouth_h / inner_tile),
                   (mouth_w / inner_tile, mouth_h / inner_tile), (-mouth_w / inner_tile, mouth_h / inner_tile)],
                  (0.0, 0.0, -1.0))
    # The rails of the arms along the ceiling, one each side of the docking place.
    rail = RAIL_SIZE * a
    for side in (-1.0, 1.0):
        centre = side * mouth_w * 0.5
        oriented_box(interior, (x_axis, y_axis, z_axis),
                     ((centre - rail / 2, centre + rail / 2), (mouth_h - 2 * rail, mouth_h - rail),
                      (mouth_z, back_z)), inner_tile)
    # The sliding door at the back of the docking place, in two leaves with a seam between them.
    door_z = back_z - 0.2 * a
    seam = DOOR_SEAM * a
    for x0, x1 in ((-mouth_w, -seam), (seam, mouth_w)):
        leaf = [(x0, -mouth_h, door_z), (x1, -mouth_h, door_z), (x1, mouth_h, door_z), (x0, mouth_h, door_z)]
        doors.quad(leaf, [(x / inner_tile, y / inner_tile) for x, y, _ in leaf], (0.0, 0.0, -1.0))
    # The frame round the door: four bars along the inner edges of the back wall, standing out toward the mouth.
    frame = DOOR_FRAME * a
    depth_range = (door_z - DOOR_FRAME_DEPTH * a, door_z)
    for ranges in (
            ((-mouth_w, mouth_w), (mouth_h - frame, mouth_h), depth_range),
            ((-mouth_w, mouth_w), (-mouth_h, -mouth_h + frame), depth_range),
            ((-mouth_w, -mouth_w + frame), (-mouth_h, mouth_h), depth_range),
            ((mouth_w - frame, mouth_w), (-mouth_h, mouth_h), depth_range)):
        oriented_box(doors, (x_axis, y_axis, z_axis), ranges, inner_tile)

    spinning_marks = Builder(sun_colour)
    offset = 0.5  # m, the marks stand off the walls: nearer, they flicker (depth fighting) as the ring turns
    for step, region in enumerate(NUMBERS):
        angle = step * math.pi / 2.0
        centre_radius = radius - RING_THICKNESS * a / 2.0
        size = RING_THICKNESS * a * 0.8 / 2.0
        centre = (centre_radius * math.cos(angle), centre_radius * math.sin(angle))
        outward = (math.cos(angle), math.sin(angle))
        around = (-math.sin(angle), math.cos(angle))
        u0, v0, u1, v1 = marks_rect(region)
        corners = [(-size, -size), (size, -size), (size, size), (-size, size)]  # (around, outward)
        points = [(centre[0] + p * around[0] + q * outward[0], centre[1] + p * around[1] + q * outward[1],
                   -half_width - offset) for p, q in corners]
        spinning_marks.quad(points, [(u1, v1), (u0, v1), (u0, v0), (u1, v0)], (0.0, 0.0, -1.0))

    fixed_marks = Builder(sun_colour)
    stripe_u0, stripe_v0, stripe_u1, stripe_v1 = marks_rect(STRIPES)
    for x0, x1, y0, y1, length in ((cut - half_w, half_w - cut, mouth_h, half_h, HANGAR_WIDTH * a),
                                   (cut - half_w, half_w - cut, -half_h, -mouth_h, HANGAR_WIDTH * a),
                                   (-half_w, -mouth_w, -mouth_h, mouth_h, MOUTH_HEIGHT * a),
                                   (mouth_w, half_w, -mouth_h, mouth_h, MOUTH_HEIGHT * a)):
        long_side_is_x = (x1 - x0) > (y1 - y0)
        end_u = stripe_u0 + (stripe_u1 - stripe_u0) * min(1.0, length / (HANGAR_WIDTH * a))
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        uvs = ([(stripe_u0, stripe_v0), (end_u, stripe_v0), (end_u, stripe_v1), (stripe_u0, stripe_v1)]
               if long_side_is_x else
               [(stripe_u0, stripe_v0), (stripe_u0, stripe_v1), (end_u, stripe_v1), (end_u, stripe_v0)])
        fixed_marks.quad([(x, y, mouth_z - offset) for x, y in corners], uvs, (0.0, 0.0, -1.0))
    chevron_u0, chevron_v0, chevron_u1, chevron_v1 = marks_rect(CHEVRON)
    chevron_half = mouth_w * 0.35
    for z in (mouth_z + 6.0 * a, mouth_z + 11.0 * a, mouth_z + 16.0 * a):
        points = [(-chevron_half, -mouth_h + offset, z - chevron_half), (chevron_half, -mouth_h + offset,
                                                                       z - chevron_half),
                  (chevron_half, -mouth_h + offset, z + chevron_half), (-chevron_half, -mouth_h + offset,
                                                                      z + chevron_half)]
        fixed_marks.quad(points, [(chevron_u0, chevron_v1), (chevron_u1, chevron_v1), (chevron_u1, chevron_v0),
                                  (chevron_u0, chevron_v0)], (0.0, 1.0, 0.0))

    far_corner = math.hypot(math.hypot(half_w, half_h), mouth_z)
    return BaseModel(
        radius=radius, scale=a, spinning_hull=spinning.build(), sides=sides.build(), spokes=spokes.build(),
        fixed_hull=fixed.build(),
        hangar=hangar.build(), interior=interior.build(), doors=doors.build(),
        spinning_marks=spinning_marks.build(), fixed_marks=fixed_marks.build(), nozzles=nozzles,
        bounding_radius=max(math.hypot(radius, half_width), far_corner),
        plume_start_z=thruster_z)
