"""Asteroids in space, drawn as OpenGL meshes while the ship is unbound.

What is drawn: the asteroids of the ongoing missions of the system (see `StellarSystem.mission_asteroids`) at any
distance, and the cosmetic asteroids of its belts that are worth it: near enough to be seen (`MIN_PIXELS` across) and
slow enough relative to the ship (`MAX_COSMETIC_SPEED`), since a pilot does not see the belt's countless rocks passing
at kilometres per second. A mission's asteroid too far to be `MIN_PIXELS` across is a point of its colour. The cosmetic
ones come from `AsteroidBelt.near`, asked again only every `REQUERY_SECONDS` or after the ship has moved
`REQUERY_DISTANCE`, and moved along their velocity in between.

Each asteroid is drawn with its own perspective, whose near and far planes just hold it, and with its own depth buffer
(cleared before it), farthest first: the distances and the sizes in space are too many orders of magnitude for one depth
buffer. Its mesh (asteroid_shape.py) and colours (asteroid_looks.py) come from its seed and are built once, then kept in
a small cache; only the colours are computed again when the sun has moved. Its place relative to the ship is worked out
in double precision before it goes to OpenGL, as for the rocks.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from OpenGL import GL, GLU

from common.vector3 import Vector3
from galaxies import seeds
from galaxies.asteroid import AsteroidKey
from galaxies.asteroid_sizes import AsteroidTier
from .asteroid_looks import Look, corner_colours, look_of, shade
from .asteroid_shape import asteroid_mesh, orientation
from .constants import CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS
from .instruments.common import view_geometry

if TYPE_CHECKING:
    from galaxies.asteroid_belt import AsteroidBelt
    from galaxies.stellar_system import StellarSystem
    from game_environment import GameEnvironment
    from spaceships.ship import Ship


class AsteroidModel:
    """The mesh of one asteroid, ready for OpenGL: vertex positions in metres round its centre, and the colours that
    the sun gives them, computed again only when the sun has moved more than `SUN_TOLERANCE_DEGREES`."""

    SUN_TOLERANCE_DEGREES = 1.0
    _SUN_TOLERANCE_COS = math.cos(math.radians(SUN_TOLERANCE_DEGREES))

    def __init__(self, seed: int, diameter: float) -> None:
        mesh = asteroid_mesh(seed, diameter)
        rotation = orientation(seed)
        self.radius: float = diameter / 2.0
        self.look: Look = look_of(seed)
        self.positions: np.ndarray = np.ascontiguousarray(
            ((mesh.corners @ rotation.T) * self.radius).reshape(-1, 3), dtype=np.float32)
        self._normals: np.ndarray = mesh.normals @ rotation.T
        self._base: np.ndarray = corner_colours(mesh, self.look, seed)
        self._cached: np.ndarray | None = None
        self._cached_sun: np.ndarray = np.zeros(3)

    def colours(self, sun: np.ndarray) -> np.ndarray:
        """The colour of each vertex (uint8) lit from the direction `sun` (a unit vector in the stellar frame)."""
        if self._cached is None or float(sun @ self._cached_sun) < self._SUN_TOLERANCE_COS:
            self._cached = shade(self._base, self._normals, sun)
            self._cached_sun = sun
        return self._cached


@dataclass(frozen=True)
class Sighting:
    """An asteroid to draw: the seed of its shape, its diameter, and its place in the stellar frame."""
    seed: int
    diameter: float
    centre: np.ndarray  # (3,) metres, from the star
    is_mission: bool


class CosmeticView:
    """The cosmetic asteroids of one belt around the ship, from the last query (see the module docstring)."""

    REQUERY_SECONDS = 2.0
    REQUERY_DISTANCE = 500.0  # m

    def __init__(self) -> None:
        self._date: datetime | None = None
        self._ship_position: np.ndarray = np.zeros(3)
        self._found = None

    def sightings(self, belt: AsteroidBelt, date: datetime, ship_position: np.ndarray, ship_velocity: np.ndarray,
                  focal: float) -> list[Sighting]:
        """The cosmetic asteroids of the belt that are near and slow enough to be drawn, at the date."""
        stale = (self._date is None or abs((date - self._date).total_seconds()) > self.REQUERY_SECONDS
                 or float(np.linalg.norm(ship_position - self._ship_position)) > self.REQUERY_DISTANCE)
        if stale:
            self._found = belt.near(Vector3(*ship_position), date, Asteroids.tier_reaches(focal))
            self._date, self._ship_position = date, ship_position
        found = self._found
        if found is None or not len(found.diameter):
            return []
        elapsed = (date - self._date).total_seconds()
        positions = found.position + found.velocity * elapsed
        distance = np.linalg.norm(positions - ship_position, axis=1)
        slow = np.linalg.norm(found.velocity - ship_velocity, axis=1) <= Asteroids.MAX_COSMETIC_SPEED
        seen = slow & (found.diameter * focal / np.maximum(distance, 1.0) >= Asteroids.MIN_PIXELS)
        nearest = np.flatnonzero(seen)[np.argsort(distance[seen])][:Asteroids.MAX_COSMETIC]
        return [Sighting(seeds.derive(belt.seed, 'asteroid', str(AsteroidKey.from_ints(found.key[index]))),
                         float(found.diameter[index]), positions[index], False) for index in nearest]


class Asteroids:
    """Draws the asteroids of the system around the ship (see the module docstring)."""

    MIN_PIXELS = 3.0  # an asteroid is a mesh from this apparent size, in pixels, up
    POINT_SIZE = 3.0  # pixels: a mission's asteroid that is smaller than MIN_PIXELS
    POINT_DISTANCE = 1000.0  # m: where a point is put, along its direction (only its direction matters)
    MAX_COSMETIC_SPEED = 50.0  # m/s relative to the ship: a faster cosmetic asteroid is not drawn
    MAX_COSMETIC = 40  # drawn at most, the nearest
    MODEL_CACHE = 128
    BOUND_MARGIN = 1.3  # of an asteroid's radius, round its centre: its near and far planes

    _models: OrderedDict[tuple[int, float], AsteroidModel] = OrderedDict()
    _views: dict[int, CosmeticView] = {}

    @staticmethod
    def draw(width: int, height: int, ship: Ship, environment: GameEnvironment) -> None:
        """Draws the asteroids that are in front of the ship, farthest first. Call while unbound, after the sky."""
        system: StellarSystem = environment.targeted_body.stellar_system
        date = environment.date_time
        position = ship.navigation.stellar_position(date)
        ship_position = np.array([position.x, position.y, position.z])
        _, _, focal = view_geometry(height)

        sightings = []
        for asteroid in system.mission_asteroids():
            centre = asteroid.calculate_stellar_position(date)
            sightings.append(Sighting(asteroid.seed, 2.0 * asteroid.radius, np.array([centre.x, centre.y, centre.z]),
                                      True))
        velocity = ship.velocity.as_vector()
        ship_velocity = np.array([velocity.x, velocity.y, velocity.z])
        for belt in Asteroids._belts(system):
            view = Asteroids._views.get(id(belt))
            if view is None:
                view = Asteroids._views[id(belt)] = CosmeticView()
            sightings += view.sightings(belt, date, ship_position, ship_velocity, focal)
        if not sightings:
            return

        ahead_axis = ship.attitude.forward
        forward = np.array([ahead_axis.x, ahead_axis.y, ahead_axis.z])
        ahead = []
        for sighting in sightings:
            relative = sighting.centre - ship_position
            distance = float(np.linalg.norm(relative))
            if float(relative @ forward) > 0.0 and distance > 0.0:
                ahead.append((distance, relative, sighting))
        if not ahead:
            return

        view_height = int(height * CONSOLE_TOP)
        aspect = width / view_height
        GL.glViewport(0, height - view_height, width, view_height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        for distance, relative, sighting in sorted(ahead, key=lambda item: item[0], reverse=True):
            if sighting.diameter * focal / distance >= Asteroids.MIN_PIXELS:
                Asteroids._draw_mesh(ship, sighting, relative, distance, aspect)
            elif sighting.is_mission:
                Asteroids._draw_point(ship, sighting, relative, aspect)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glViewport(0, 0, width, height)

    @staticmethod
    def tier_reaches(focal: float) -> dict[AsteroidTier, float]:
        """How far to look for the asteroids of each tier: up to where the largest of the tier is MIN_PIXELS across."""
        return {tier: tier.upper * focal / Asteroids.MIN_PIXELS for tier in AsteroidTier}

    @staticmethod
    def _belts(system: StellarSystem) -> list[AsteroidBelt]:
        from galaxies.asteroid_belt import AsteroidBelt
        return [orbit for orbit in system.orbits if isinstance(orbit, AsteroidBelt)]

    @staticmethod
    def _model(seed: int, diameter: float) -> AsteroidModel:
        key = (seed, diameter)
        model = Asteroids._models.get(key)
        if model is None:
            model = Asteroids._models[key] = AsteroidModel(seed, diameter)
            if len(Asteroids._models) > Asteroids.MODEL_CACHE:
                Asteroids._models.popitem(last=False)
        else:
            Asteroids._models.move_to_end(key)
        return model

    @staticmethod
    def _camera(ship: Ship, near: float, far: float, aspect: float) -> None:
        """The ship's perspective, with these near and far planes, on the model-view and projection stacks."""
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GLU.gluPerspective(math.degrees(VIEW_VERTICAL_FOV_RADIANS), aspect, near, far)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glMultMatrixf(ship.attitude.camera_matrix())  # the ship's right, up and forward onto OpenGL's eye axes

    @staticmethod
    def _draw_mesh(ship: Ship, sighting: Sighting, relative: np.ndarray, distance: float, aspect: float) -> None:
        model = Asteroids._model(sighting.seed, sighting.diameter)
        margin = Asteroids.BOUND_MARGIN * model.radius
        Asteroids._camera(ship, max(0.05, distance - margin), distance + margin, aspect)
        GL.glTranslatef(float(relative[0]), float(relative[1]), float(relative[2]))
        # towards the star, which is the origin
        sun = -sighting.centre / max(float(np.linalg.norm(sighting.centre)), 1.0)
        colours = model.colours(sun)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, model.positions)
        GL.glColorPointer(3, GL.GL_UNSIGNED_BYTE, 0, colours)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(model.positions))
        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)

    @staticmethod
    def _draw_point(ship: Ship, sighting: Sighting, relative: np.ndarray, aspect: float) -> None:
        """A mission's asteroid too far to show its shape: a point in its direction, of its colour."""
        Asteroids._camera(ship, 1.0, 10.0 * Asteroids.POINT_DISTANCE, aspect)
        direction = relative / float(np.linalg.norm(relative)) * Asteroids.POINT_DISTANCE
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glPointSize(Asteroids.POINT_SIZE)
        GL.glColor3ub(*(int(value) for value in look_of(sighting.seed).colour))
        GL.glBegin(GL.GL_POINTS)
        GL.glVertex3f(float(direction[0]), float(direction[1]), float(direction[2]))
        GL.glEnd()
