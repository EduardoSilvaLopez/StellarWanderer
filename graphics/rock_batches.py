"""Rocks drawn from cached arrays: one batch per Km2, one glDrawArrays call per batch.

The geometry of a Km2's rocks is built once, with numpy, into vertex arrays relative to the Km2's corner (each rock
an irregular boulder of FACES triangles, see rock_shape.py), and only the colours (sun light and heat glow) are
recomputed, and only when needed: they depend on the sun and on the heat glow, and neither changes much from one
frame to the next (see SUN_TOLERANCE_DEGREES). Graphics reads the rocks' temperature colour (rock.color) and shape
seed; Galaxies knows nothing about this module.

Used by `Rocks.draw`, which `OpenGLGui.draw` gives the visible Km2s (`RockBatches.visible_km2s`).

A batch is built on first use (about 5 ms) and rebuilt only when the Km2's rock count changes, which happens when a
rock melts. Rocks add their heat glow (rock.color above initial_color) after shading, so a hot rock still glows on
the dark side. A rock whose lowest point would float above the ground is lowered onto it.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple
import math
import weakref

import numpy as np
from OpenGL import GL

from .constants import SURFACE_STARLIGHT
from .rock_shape import FACES, rock_meshes, rotate

if TYPE_CHECKING:
    from Galaxies.km2 import Km2
    from Galaxies.rock import Rock
    from Galaxies.world import World
    from .surface_light import SurfaceLight

# The cached colours are reused until the sun has moved this far. At 0.1 degrees the brightness changes by less
# than 0.002, under half a level of 255, so nobody can see the difference. At normal speed the sun moves about
# 0.5 degrees per game hour, so the colours are recomputed every ~13 game minutes; at high time compression
# the sun moves fast and they are recomputed every frame, as without a cache.
SUN_TOLERANCE_DEGREES = 0.1
_SUN_TOLERANCE_COS = math.cos(math.radians(SUN_TOLERANCE_DEGREES))

# Faces facing down are a little darker (dust and shadow in the hollows), up to this share, on top of the sun.
DOWNWARD_DARKENING = 0.18

class RockBatch:
    """The rocks of one Km2 as arrays. Valid while the Km2's rock list is unchanged (see `is_current`)."""

    def __init__(self, km2: Km2) -> None:
        self.origin_x: int = km2.longitude   # vertices are relative to the Km2's corner: small, float32-safe
        self.origin_z: int = km2.latitude
        self.rocks: Tuple[Rock, ...] = tuple(km2.rocks)
        count = len(self.rocks)

        size = np.array([rock.size for rock in self.rocks], dtype=np.float64)
        tilt = np.array([rock.tilt for rock in self.rocks], dtype=np.float64)
        orientation = np.array([rock.orientation for rock in self.rocks], dtype=np.float64)
        centre = np.array([(rock.longitude - self.origin_x, rock.altitude, rock.latitude - self.origin_z)
                           for rock in self.rocks], dtype=np.float64).reshape(count, 1, 3)

        triangles, normals, tones = rock_meshes([rock.shape_seed for rock in self.rocks])
        points = rotate(triangles.reshape(count, FACES * 3, 3) * (size / 2.0)[:, None, None], tilt, orientation)
        # A rock never floats: if its lowest point is above the ground, it is lowered onto it (a rock that is
        # partly buried stays buried). The scanner's box is not lowered with it, which is close enough for aiming.
        lowest = centre[:, 0, 1] + points[..., 1].min(axis=1) if count else np.zeros(0)
        centre[:, 0, 1] -= np.maximum(0.0, lowest)
        self.positions: np.ndarray = np.ascontiguousarray((centre + points).reshape(-1, 3), dtype=np.float32)
        self.face_normals: np.ndarray = rotate(normals, tilt, orientation)
        down = DOWNWARD_DARKENING * (1.0 - (self.face_normals[..., 1] + 1.0) / 2.0)
        self.face_colours: np.ndarray = np.array(
            [rock.initial_color for rock in self.rocks], dtype=np.float64).reshape(count, 1, 3)             * (tones * (1.0 - down))[..., None]
        self.glow: np.ndarray = np.zeros((count, 3), dtype=np.int32)
        self._was_hot: List[bool] = [False] * count
        # The last colours computed, the sun they were computed for, and whether a glow has changed since.
        self._cached_colours: Optional[np.ndarray] = None
        self._cached_sun: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._glow_changed: bool = False

    def is_current(self, km2: Km2) -> bool:
        """False once a rock has melted away (the only way rocks leave a Km2, and none are added after creation)."""
        return len(self.rocks) == len(km2.rocks)

    def refresh_glow(self) -> None:
        """The heat glow (rock.color above rock.initial_color). Only rocks that are hot, or were last frame,
        are looked at, so a cold Km2 costs one pass over its rocks and nothing else. A glow that actually
        changes marks the cached colours as out of date."""
        for index, rock in enumerate(self.rocks):
            hot = rock.temperature > 0.0
            if hot or self._was_hot[index]:
                glow = [max(0, int(now) - int(start)) for now, start in zip(rock.color, rock.initial_color)]
                if glow != self.glow[index].tolist():
                    self.glow[index] = glow
                    self._glow_changed = True
                self._was_hot[index] = hot

    def colours(self, light: SurfaceLight) -> np.ndarray:
        """Per-vertex colours (uint8, one per vertex), recomputed only when the sun has moved more than
        SUN_TOLERANCE_DEGREES or a glow has changed (call `refresh_glow` first); otherwise the same array again."""
        sun = (light.sun.x, light.sun.y, light.sun.z)
        if self._cached_colours is not None and not self._glow_changed:
            cached = self._cached_sun
            if sun[0] * cached[0] + sun[1] * cached[1] + sun[2] * cached[2] >= _SUN_TOLERANCE_COS:
                return self._cached_colours
        self._cached_colours = self._compute_colours(sun)
        self._cached_sun = sun
        self._glow_changed = False
        return self._cached_colours

    def _compute_colours(self, sun_direction: Tuple[float, float, float]) -> np.ndarray:
        """Each face lit by the sun from its own normal, as in SurfaceLight.brightness, then the glow added, so
        a hot rock still glows on the dark side."""
        sun = np.array(sun_direction, dtype=np.float64)
        facing = self.face_normals @ sun
        brightness = SURFACE_STARLIGHT + (1.0 - SURFACE_STARLIGHT) * np.maximum(0.0, facing)
        shaded = (self.face_colours * brightness[..., None]).astype(np.int32)   # truncates, like SurfaceLight.shade
        lit = np.minimum(255, shaded + self.glow[:, None, :])
        return np.ascontiguousarray(np.repeat(lit, 3, axis=1).reshape(-1, 3), dtype=np.uint8)

    def draw(self, player_x: float, player_z: float, light: SurfaceLight) -> None:
        """Draw inside the camera setup of Rocks.draw. The translation is the Km2's offset from the camera, computed
        in double precision first, so only a small number reaches float32."""
        if not len(self.rocks):
            return
        self.refresh_glow()
        colours = self.colours(light)
        GL.glPushMatrix()
        GL.glTranslatef(self.origin_x - player_x, 0.0, self.origin_z - player_z)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, self.positions)
        GL.glColorPointer(3, GL.GL_UNSIGNED_BYTE, 0, colours)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(self.positions))
        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glPopMatrix()


class RockBatches:
    """One RockBatch per Km2, built on first use and rebuilt when its rock list changes. A Km2 that leaves memory
    takes its batch with it (weak keys)."""

    _batches: "weakref.WeakKeyDictionary[Km2, RockBatch]" = weakref.WeakKeyDictionary()

    @staticmethod
    def visible_km2s(world: World, player_x: float, player_z: float) -> List[Km2]:
        """The Km2s whose rocks are drawn: the same selection as OpenGLGui._rocks (two Km2s around the player)."""
        return [km2 for km2 in world.km2s
                if km2.longitude - km2.SIZE * 2 <= player_x < km2.longitude + km2.SIZE * 2
                and km2.latitude - km2.SIZE * 2 <= player_z < km2.latitude + km2.SIZE * 2]

    @staticmethod
    def draw(km2s: Sequence[Km2], player_x: float, player_z: float, light: SurfaceLight) -> None:
        for km2 in km2s:
            batch = RockBatches._batches.get(km2)
            if batch is None or not batch.is_current(km2):
                batch = RockBatch(km2)
                RockBatches._batches[km2] = batch
            batch.draw(player_x, player_z, light)
