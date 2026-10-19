"""Planets and moons other than the targeted body, drawn in the sky lit by the star."""

from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING
from common.vector3 import Vector3
import pygame
from .lit_worlds import LitWorlds

if TYPE_CHECKING:
    from galaxies.world import World
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class OtherWorlds:
    """Renders every world of the stellar system except the targeted body (when that is a world)."""

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship,
             behind_star: bool) -> None:
        """Draw the other worlds at their true direction, bound or unbound, farthest first, each lit
        by the star (see LitWorlds).

        Called twice per frame around the sun (its hole in the sky, see OpenGLGui.draw): first with behind_star=True (worlds
        farther than the star, which the star then covers), then with behind_star=False
        (worlds nearer than the star). Unbound, the targeted body is one of them, drawn in distance order like the others;
        bound, it is the opaque disc below the horizon (LitWorlds.draw_targeted), so it is left out here.
        """
        to_star = ship.navigation.direction_to_star(environment.targeted_body, environment.date_time)
        star_distance = to_star.length()

        worlds: List[Tuple[float, World, Vector3]] = []
        for world in environment.nearest_system.get_all_worlds():
            if world is environment.targeted_body and ship.is_bound:
                continue
            to_world = ship.navigation.direction_to_body(world, environment.date_time)
            distance = to_world.length()
            if (distance > star_distance) == behind_star:
                worlds.append((distance, world, to_world))

        star = environment.targeted_body.stellar_system.star
        for _, world, to_world in sorted(worlds, key=lambda item: item[0], reverse=True):
            LitWorlds.draw_world(surface, w, h, to_world, to_star, world.radius, star.color, world.surface_colour, ship)
