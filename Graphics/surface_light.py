"""Sunlight on the surface of the nearest world while bound: the brightness of a surface facing any way, from
the direction of the star. Computed on the CPU once per frame and applied to vertex colours, so no OpenGL
lighting state is needed. The light is the cosine between the surface normal and the direction to the star,
with WORLD_AMBIENT_LIGHT still visible on the unlit side, as for worlds in the sky (see LitWorlds)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Tuple

from Vector3 import Vector3
from .Constants import SURFACE_STARLIGHT
from .lit_worlds import LitWorlds

if TYPE_CHECKING:
    from Galaxies.People.player import Player
    from game_environment import GameEnvironment

Colour = Tuple[int, int, int]


class SurfaceLight:
    """The sun seen from the ground: `sun` is the unit vector from the ship's surface towards the star,
    in the surface frame (x east, y up, z north), the same axes the 3D view uses for every object;
    `tint` is the albedo times the star's colour, 0..255 per channel."""

    def __init__(self, sun: Vector3, tint: Tuple[float, float, float]) -> None:
        self.sun: Vector3 = sun
        self.tint: Tuple[float, float, float] = tint

    @staticmethod
    def of(player: Player, environment: GameEnvironment) -> SurfaceLight:
        """The sun as seen from `player`, which must be bound (the surface frame is only defined then)."""
        world = environment.nearest_world
        star = world.parent_orbit.parent_stellar_system
        sun = player.direction_to_star(world, environment.date_time).normalized()
        return SurfaceLight(sun, LitWorlds.light_tint(star.color))

    def brightness(self, normal_x: float, normal_y: float, normal_z: float) -> float:
        """Share of full light (0..1) for a surface with the unit normal (x east, y up, z north): the starlight
        floor everywhere, plus the sun's share on the side that faces it."""
        facing = normal_x * self.sun.x + normal_y * self.sun.y + normal_z * self.sun.z
        return SURFACE_STARLIGHT + (1.0 - SURFACE_STARLIGHT) * max(0.0, facing)

    @staticmethod
    def shade(colour: Colour, brightness: float) -> Colour:
        """`colour` scaled by a brightness (0..1)."""
        return (int(colour[0] * brightness), int(colour[1] * brightness), int(colour[2] * brightness))

    def ground_colour(self) -> Colour:
        """The colour of the ground under the ship (its normal is up)."""
        return self.shade(self.tint, self.brightness(0.0, 1.0, 0.0))
