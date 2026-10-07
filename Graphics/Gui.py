"""Stellar Wanderer — first-person cockpit view.

Draws the pilot's-seat view of the player's ship as vector art: the starfield
seen through the canopy, the hull frame around it, and the instrument console.
The panel on the upper right is the ship clock — it starts at
500-01-01 00:00:00 and advances one second per real second.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
import pygame
from .DeepSpace import DeepSpace
from .NearestWorld import NearestWorld
from .Cockpit import Cockpit
from .Constants import SPACE_COLOR

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment


class Gui:
    """Main cockpit graphics orchestrator."""

    def draw(self, surface: pygame.Surface, fonts: Any, environment: GameEnvironment, player: Player) -> None:
        """Draw the complete cockpit view.

        Renders in order:
        1. Deep space background
        2. Starfield
        3. Planet surface
        4. Rocks
        5. Cockpit hull and instrumentation

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            environment: Game environment
            player: Player object
        """
        w, h = surface.get_size()
        surface.fill(SPACE_COLOR)

        # Draw space and celestial objects
        DeepSpace.draw(surface, w, h)
        NearestWorld.draw(surface, w, h, environment, player)

        # Draw cockpit frame and instruments
        Cockpit.draw(surface, fonts, w, h, player, environment.date_time, player.time_scale)


def draw(surface: pygame.Surface, fonts: Any, environment: GameEnvironment, player: Player) -> None:
    """Legacy interface for backward compatibility.

    Creates a Gui instance and draws the scene.

    Args:
        surface: Pygame surface to draw on
        fonts: Font manager
        environment: Game environment
        player: Player object
    """
    gui = Gui()
    gui.draw(surface, fonts, environment, player)
