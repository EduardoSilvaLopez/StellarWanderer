"""Cockpit instrumentation: canopy, console, and clock."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
import pygame
from datetime import datetime
from .Instruments.canopy import Canopy
from .Instruments.console import Console
from .Instruments.clock import Clock
from .Instruments.crosshair import Crosshair
from .Instruments.political_info import PoliticalInfo
from .ObjectLabels import ObjectLabels

if TYPE_CHECKING:
    from Player import Player


class Cockpit:
    """Renders cockpit instrumentation: hull, console, and clock."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, date_time: datetime, time_scale: int) -> None:
        """Draw all cockpit elements.

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            w: Window width
            h: Window height
            player: Player object
            date_time: Player's ship time
            time_scale: Time acceleration factor
        """
        import GameEnvironment as gem
        Canopy.draw(surface, w, h)
        Crosshair.draw(surface, w, h)
        ObjectLabels.draw(surface, fonts, w, h, gem.current_environment, player)
        PoliticalInfo.draw(surface, fonts, w, h, player)
        Console.draw(surface, fonts, w, h, player, date_time)
        Clock.draw(surface, fonts, date_time, time_scale, w, h)
