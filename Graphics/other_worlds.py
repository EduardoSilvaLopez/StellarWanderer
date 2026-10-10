"""Planets and moons other than the nearest world, drawn in the sky lit by the star."""

from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING
from Vector3 import Vector3
import pygame
from .lit_worlds import LitWorlds

if TYPE_CHECKING:
    from Galaxies.world import World
    from Player import Player
    from GameEnvironment import GameEnvironment


class OtherWorlds:
    """Renders every world of the stellar system except the nearest one."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player,
             behind_star: bool) -> None:
        """Draw the other worlds at their true direction, bound or unbound, farthest first, each lit
        by the star (see LitWorlds).

        Called twice per frame around LocalStar.draw: first with behind_star=True (worlds
        farther than the star, which the star then covers), then with behind_star=False
        (worlds nearer than the star). The nearest world is drawn afterwards, so it naturally
        hides the worlds behind it (while bound, as an opaque disc below the horizon).
        """
        to_star = player.direction_to_star(environment.nearest_world, environment.date_time)
        star = environment.nearest_world.parent_orbit.parent_stellar_system
        star_distance = to_star.length()

        worlds: List[Tuple[float, World, Vector3]] = []
        for world in environment.nearest_system.get_all_worlds():
            if world is environment.nearest_world:
                continue
            to_world = player.direction_to_world(world, environment.date_time)
            distance = to_world.length()
            if (distance > star_distance) == behind_star:
                worlds.append((distance, world, to_world))

        for _, world, to_world in sorted(worlds, key=lambda item: item[0], reverse=True):
            LitWorlds.draw_world(surface, w, h, to_world, to_star, world.radius, star.color, player)
