"""Cockpit instrumentation: canopy, console, and clock."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
import pygame
from datetime import datetime
from .instruments.canopy import Canopy
from .instruments.console import Console
from .instruments.clock import Clock
from .instruments.location_info import LocationInfo
from .instruments.crosshair import Crosshair
from .instruments.cockpit_buttons import CockpitButtons
from .instruments.political_info import PoliticalInfo
from .object_labels import ObjectLabels
from .target_marker import TargetMarker
from .lead_marker import LeadMarker
from .velocity_markers import VelocityMarkers

if TYPE_CHECKING:
    from galaxies.people.player import Player


class Cockpit:
    """Renders cockpit instrumentation: hull, console, and clock."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, date_time: datetime) -> None:
        """Draw all cockpit elements.

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            w: Window width
            h: Window height
            player: Player object
            date_time: Player's ship time
        """
        import game_environment as gem
        Canopy.draw(surface, w, h)
        Crosshair.draw(surface, w, h)
        VelocityMarkers.draw(surface, fonts, w, h, player.ship)
        TargetMarker.draw(surface, w, h, gem.current_environment, player.ship)
        LeadMarker.draw(surface, w, h, player.ship)
        ObjectLabels.draw(surface, fonts, w, h, gem.current_environment, player.ship)
        CockpitButtons.draw(surface, w, h, PoliticalInfo.draw(surface, fonts, w, h), player)
        Console.draw(surface, fonts, w, h, player.ship, date_time)
        LocationInfo.draw_name(surface, fonts, w, h)
        Clock.draw(surface, fonts, date_time, player.time_scale, w, h)
