"""Depth-tested OpenGL laser beam rendering.

The beam is a round glow: concentric cylinders from yellow to white at the axis, to orange at the edge, each added to
the others (additive blending), so the light falls off smoothly and has no edge. Where it leaves the ship there is a
muzzle flash, brightest for a moment when the beam switches on, and where it meets a rock a hot spot, brighter the
hotter the rock is.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple
import math
import time

from OpenGL import GL, GLU

from .constants import (
    CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, NEAR_CLIP, MAX_DEPTH, LASER_BEAM_SEGMENTS, LASER_BEAM_LAYERS,
    LASER_MUZZLE_COLOR, LASER_MUZZLE_RADIUS, LASER_MUZZLE_STEADY, LASER_MUZZLE_BURST_SECONDS, LASER_IMPACT_COLOR,
    LASER_IMPACT_RADIUS, LASER_IMPACT_LIFT, LASER_IMPACT_ALPHA, LASER_IMPACT_SEGMENTS,
)

if TYPE_CHECKING:
    from galaxies.rock import Rock
    from spaceships.ship import Ship

Vector = Tuple[float, float, float]

# The unit circle the cylinders and the flash are drawn with: (cos, sin) of each segment's angle.
_CIRCLE: List[Tuple[float, float]] = [
    (math.cos(2 * math.pi * i / LASER_BEAM_SEGMENTS), math.sin(2 * math.pi * i / LASER_BEAM_SEGMENTS))
    for i in range(LASER_BEAM_SEGMENTS)
]


class Laser:
    """Render the laser beam using the OpenGL depth buffer for occlusion."""

    @staticmethod
    def draw(width: int, height: int, ship: Ship) -> None:
        """Draw the laser beam if the player is firing.

        Laser is a straight segment from just below the camera to its end point (Scanner.update_target in
        spaceships/scanner.py): while bound the end is on the ground MAX_LENGTH metres ahead, while unbound it extends
        MAX_LENGTH metres along the ship's forward axis. Depth-tested against rocks/ground. The beam, its muzzle flash
        and the hot spot on a rock are all added light, so none of them writes depth.
        """
        if not ship.laser.firing:
            return

        view_height = int(height * CONSOLE_TOP)
        aspect = width / view_height
        near_plane = max(0.1, NEAR_CLIP)

        # Match OpenGLRocks viewport and camera transform exactly.
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GLU.gluPerspective(
            math.degrees(VIEW_VERTICAL_FOV_RADIANS), aspect, near_plane, MAX_DEPTH
        )
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glMultMatrixf(ship.attitude.camera_matrix())
        # X/Z made camera-relative on the CPU (double precision) instead of via
        # glTranslatef, to avoid float32 truncation at large world coordinates
        # — see the matching comment in Rocks.draw() for why.
        if ship.is_bound:
            GL.glTranslatef(0.0, -ship.position.y, 0.0)
            # Perpendicular vector (right): rotate forward 90° in XZ plane
            yaw = math.radians(ship.attitude.yaw)
            right_axis = (math.cos(yaw), 0.0, -math.sin(yaw))
            up_axis = (0.0, 1.0, 0.0)
            origin = (ship.position.x, 0.0, ship.position.z)
        else:
            # Unbound the beam is stored relative to the ship, along its own axes.
            right_axis = ship.attitude.right
            up_axis = ship.attitude.up
            origin = (0.0, 0.0, 0.0)

        # Beam radius, in meters: the layers of the glow are shares of it (LASER_BEAM_LAYERS).
        half_size = 0.5

        scanner = ship.scanner
        start: Vector = (scanner.start_x, scanner.start_y, scanner.start_z)
        end: Vector = (scanner.end_x, scanner.end_y, scanner.end_z)
        hit_rock: Optional[Rock] = ship.laser.hitting_rock

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)  # additive: the layers add up, from the outside in
        GL.glDepthMask(GL.GL_FALSE)
        for share, colour, alpha in LASER_BEAM_LAYERS:
            GL.glColor4ub(*colour, alpha)
            Laser._draw_cylinder(start, end, half_size * share, origin, right_axis, up_axis)
        Laser._draw_muzzle(start, origin, right_axis, up_axis, ship.laser.fired_at)
        if hit_rock is not None:
            Laser._draw_impact(start, end, hit_rock, origin, right_axis, up_axis)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_DEPTH_TEST)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    @staticmethod
    def _ring(centre: Vector, radius: float, origin: Vector, right_axis: Vector, up_axis: Vector) -> List[Vector]:
        """The points of a circle of `radius` around `centre`, in the plane of right_axis and up_axis, with `origin`
        subtracted from each (see `draw`)."""
        return [
            tuple(c - b + radius * (across * r + around * u) for c, b, r, u in zip(centre, origin, right_axis, up_axis))
            for across, around in _CIRCLE
        ]

    @staticmethod
    def _draw_cylinder(start: Vector, end: Vector, radius: float, origin: Vector, right_axis: Vector,
                       up_axis: Vector) -> None:
        """A round tube of `radius` from start to end, in the colour and alpha already set."""
        start_ring = Laser._ring(start, radius, origin, right_axis, up_axis)
        end_ring = Laser._ring(end, radius, origin, right_axis, up_axis)
        GL.glBegin(GL.GL_QUAD_STRIP)
        for i in range(LASER_BEAM_SEGMENTS + 1):
            j = i % LASER_BEAM_SEGMENTS
            GL.glVertex3f(*start_ring[j])
            GL.glVertex3f(*end_ring[j])
        GL.glEnd()

    @staticmethod
    def _draw_muzzle(start: Vector, origin: Vector, right_axis: Vector, up_axis: Vector, fired_at: float) -> None:
        """A round flash at the emitter, facing the camera. It is brightest just after the beam switched on (`fired_at`,
        a time.monotonic() value) and then settles to a steady, flickering glow while the beam fires. Cosmetic: it uses
        the real time, and nothing about it is kept."""
        now = time.monotonic()
        burst = math.exp(-(now - fired_at) / LASER_MUZZLE_BURST_SECONDS)
        flicker = 0.75 + 0.25 * math.sin(2 * math.pi * 17 * now) * math.sin(2 * math.pi * 5 * now + 1)
        brightness = min(1.0, max(LASER_MUZZLE_STEADY, burst) * flicker)
        radius = LASER_MUZZLE_RADIUS * (1.0 + 0.5 * burst)
        centre = tuple(s - b for s, b in zip(start, origin))
        rim = Laser._ring(start, radius, origin, right_axis, up_axis)
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glColor4ub(*LASER_MUZZLE_COLOR, int(255 * brightness))
        GL.glVertex3f(*centre)
        GL.glColor4ub(*LASER_MUZZLE_COLOR, 0)
        for point in rim + rim[:1]:  # back to the first point, closing the disc
            GL.glVertex3f(*point)
        GL.glEnd()

    @staticmethod
    def _draw_impact(start: Vector, end: Vector, rock: Rock, origin: Vector, right_axis: Vector,
                     up_axis: Vector) -> None:
        """A soft hot spot where the beam ends on `rock`: a disc that is brightest at its centre and fades to nothing at
        its rim, facing the camera. It grows and brightens with the rock's temperature, and is drawn a little back
        along the beam, so the rock does not hide it."""
        heat = min(1.0, rock.temperature / rock.max_temperature)
        radius = LASER_IMPACT_RADIUS * (0.6 + 0.4 * heat)
        alpha = int(LASER_IMPACT_ALPHA * (0.4 + 0.6 * heat))
        along = [e - s for e, s in zip(end, start)]
        length = math.sqrt(sum(d * d for d in along))
        if length < 1e-9:
            return
        centre = [e - b - d / length * LASER_IMPACT_LIFT for e, b, d in zip(end, origin, along)]
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glColor4ub(*LASER_IMPACT_COLOR, alpha)
        GL.glVertex3f(*centre)
        GL.glColor4ub(*LASER_IMPACT_COLOR, 0)
        for i in range(LASER_IMPACT_SEGMENTS + 1):
            angle = 2 * math.pi * i / LASER_IMPACT_SEGMENTS
            across, around = math.cos(angle), math.sin(angle)
            GL.glVertex3f(*(p + radius * (r * across + u * around)
                            for p, r, u in zip(centre, right_axis, up_axis)))
        GL.glEnd()
