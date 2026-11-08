"""The fixed stars within reach of the ship, drawn as dots where they are in the sky (labels: none yet)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

import numpy as np
from OpenGL import GL

from galaxies.constants import ABSOLUTE_MAGNITUDE_DISTANCE_LY, FIXED_STAR_SHOW_RADIUS, LIGHT_YEAR_M

from .constants import FIXED_STAR_DOT_RADIUS_PX, NAKED_EYE_LIMIT_MAGNITUDE, NEAR_CLIP

if TYPE_CHECKING:
    from game_environment import GameEnvironment
    from .local_star import StarView
    from spaceships.ship import Ship


class DistantStars:
    """Fixed stars within FIXED_STAR_SHOW_RADIUS of the ship, each as a dot in its own colour where it is in the sky.

    A star is only drawn when it is bright enough to see with the naked eye (apparent magnitude at most
    NAKED_EYE_LIMIT_MAGNITUDE), so the dim red dwarfs mostly stay out of the sky, as they do in the real one.

    Drawn bound or unbound, using the same directions as the other sky objects. Drawn first in the sky layer, so
    the sun's hole in the sky hides a star behind the sun, and the ground hides the stars below the horizon.

    The range, brightness and in-front tests run on numpy arrays of all the stars, made once for the galaxy's list
    of fixed stars (their positions do not change); only the stars that pass are projected one by one.
    """

    _source: Optional[list] = None  # the galaxy's list the arrays were made from
    _positions: Optional[np.ndarray] = None  # (n, 3), in meters, in the stellar frame
    _absolute_magnitudes: Optional[np.ndarray] = None  # (n,)
    _colours: list = []  # of each star
    _squares: Optional[tuple] = None  # the window size, the vertices and the colours of the squares last made

    @staticmethod
    def _star_arrays(environment: GameEnvironment) -> tuple[list, np.ndarray, np.ndarray]:
        """The galaxy's fixed stars, their positions and their absolute magnitudes, as arrays in the same order."""
        stars = environment.galaxy.fixed_star_positions()
        if DistantStars._source is not stars:
            DistantStars._source = stars
            DistantStars._positions = np.array([position for _, position in stars], dtype=float).reshape(-1, 3)
            DistantStars._absolute_magnitudes = np.array([star.absolute_magnitude for star, _ in stars], dtype=float)
            DistantStars._colours = [star.color for star, _ in stars]
        return stars, DistantStars._positions, DistantStars._absolute_magnitudes

    @staticmethod
    def visible_dots(environment: GameEnvironment, ship: Ship, w: int, h: int) -> list[tuple[tuple, tuple[int, int]]]:
        """(colour, screen position) for every fixed star in range, bright enough and in front of the camera."""
        from .instruments.common import view_geometry
        _, horizon_y, focal_length_px = view_geometry(h)
        date_time = environment.date_time
        ship_position = ship.navigation.stellar_position(date_time)
        stars, positions, absolute_magnitudes = DistantStars._star_arrays(environment)
        offsets = positions - np.array([ship_position.x, ship_position.y, ship_position.z])
        distance_squared = np.einsum('ij,ij->i', offsets, offsets)
        # The same brightness as Star.apparent_magnitude, for every star at once.
        distance_ly = np.sqrt(distance_squared) / LIGHT_YEAR_M
        apparent_magnitudes = absolute_magnitudes + 5 * np.log10(distance_ly / ABSOLUTE_MAGNITUDE_DISTANCE_LY)
        visible = (distance_squared <= (FIXED_STAR_SHOW_RADIUS * LIGHT_YEAR_M) ** 2) & \
            (apparent_magnitudes <= NAKED_EYE_LIMIT_MAGNITUDE)
        # Unbound, a star behind the ship is not visible: its forward component is the dot product with the ship's
        # forward axis.
        if not ship.is_bound:
            forward = ship.attitude.forward
            visible &= offsets @ np.array([forward.x, forward.y, forward.z]) > 0.0
        indices = np.flatnonzero(visible)
        if not len(indices):
            return []
        # What Navigation.direction_to_point and project_to_camera do, for all the stars at once: the direction in the
        # active frame (bound, through the surface basis), then onto the ship's axes and the screen.
        vectors = offsets[indices]
        if ship.is_bound:
            east, up, north = environment.fixed_world.surface_basis(ship.position.x, ship.position.z, date_time)
            basis = np.array([[v.x, v.y, v.z] for v in (east, up, north)])
            vectors = np.stack([vectors[:, 0], -vectors[:, 1], vectors[:, 2]], axis=1) @ basis.T
        attitude = ship.attitude
        axes = np.array([[v.x, v.y, v.z] for v in (attitude.right, attitude.up, attitude.forward)])
        camera = vectors @ axes.T
        forward = camera[:, 2]
        in_front = forward > NEAR_CLIP
        safe = np.where(in_front, forward, 1.0)
        screen_x = w / 2 + focal_length_px * camera[:, 0] / safe
        screen_y = horizon_y - focal_length_px * camera[:, 1] / safe
        margin = 10 * w
        shown = in_front & (np.abs(screen_x - w / 2) <= margin) & (np.abs(screen_y - horizon_y) <= margin)
        return [(DistantStars._colours[indices[i]], (int(screen_x[i]), int(screen_y[i])))
                for i in np.flatnonzero(shown)]

    @staticmethod
    def draw(w: int, h: int, environment: GameEnvironment, ship: Ship, view: Optional[StarView],
             refresh: bool) -> None:
        """The dots as small squares drawn straight into the frame (a layer of their own, drawn and uploaded to the
        graphics card every frame, cost several milliseconds for a few dozen dots). The sun hides the stars in its
        corona, as it hid them in the layer (`erase`). The squares are made again only when `refresh` (the sky has
        changed, see OpenGLGui) or the window has another size; they are drawn at every frame."""
        cache = DistantStars._squares
        if refresh or cache is None or cache[0] != (w, h):
            dots = DistantStars.visible_dots(environment, ship, w, h)
            hidden = min(math.ceil(view.corona_px), 2 * max(w, h)) if view is not None else 0
            if view is not None:
                dots = [(colour, (x, y)) for colour, (x, y) in dots
                        if math.hypot(x - int(view.x), y - int(view.y)) > hidden]
            radius = FIXED_STAR_DOT_RADIUS_PX
            corners = np.array([(-radius, -radius), (radius + 1, -radius), (radius + 1, radius + 1),
                                (-radius, radius + 1)], dtype=np.float32)
            centres = np.array([centre for _, centre in dots], dtype=np.float32).reshape(-1, 1, 2)
            colours = np.array([colour[:3] for colour, _ in dots], dtype=np.uint8).reshape(-1, 1, 3)
            cache = DistantStars._squares = (
                (w, h), np.ascontiguousarray((centres + corners).reshape(-1, 2)),
                np.ascontiguousarray(np.broadcast_to(colours, (len(dots), 4, 3)).reshape(-1, 3)))
        _, vertices, colours = cache
        if not len(vertices):
            return
        GL.glViewport(0, 0, w, h)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glDisable(GL.GL_BLEND)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, w, h, 0, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        GL.glVertexPointer(2, GL.GL_FLOAT, 0, vertices)
        GL.glColorPointer(3, GL.GL_UNSIGNED_BYTE, 0, colours)
        GL.glDrawArrays(GL.GL_QUADS, 0, len(vertices))
        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
