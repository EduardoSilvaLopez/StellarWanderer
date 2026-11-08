"""Cockpit instrumentation: canopy, console, and clock."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
import pygame
from datetime import datetime
from common.frame_watch import frame_watch
from .instruments.canopy import Canopy
from .instruments.console import Console
from .instruments.clock import Clock
from .instruments.location_info import LocationInfo
from .instruments.crosshair import Crosshair
from .instruments.cockpit_buttons import CockpitButtons
from .instruments.political_info import PoliticalInfo
from .object_labels import ObjectLabels
from .target_marker import TargetMarker
from .velocity_markers import VelocityMarkers

if TYPE_CHECKING:
    from galaxies.people.player import Player


class Cockpit:
    """Renders cockpit instrumentation: hull, console, and clock."""

    @staticmethod
    def draw_console(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, date_time: datetime) -> None:
        """The console: everything below the windshield. It changes slowly, so the caller draws it a few times a second
        (see OpenGLGui) and keeps it in between."""
        Console.draw(surface, fonts, w, h, player.ship, date_time)
        frame_watch.mark('console')

    @staticmethod
    def draw_upper(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, date_time: datetime) -> None:
        """Draw the cockpit above the console, every frame: the canopy (which starts the layer), the markers, the
        labels, the buttons, the name of the place and the clock.

        Args:
            surface: Pygame surface to draw on
            fonts: Font manager
            w: Window width
            h: Window height
            player: Player object
            date_time: Player's ship time
        """
        import game_environment as gem
        Canopy.draw(surface, w, h, player.ship.COCKPIT_TEXTURE)
        frame_watch.mark('canopy')
        Crosshair.draw(surface, w, h)
        VelocityMarkers.draw(surface, fonts, w, h, player.ship)
        TargetMarker.draw(surface, w, h, gem.current_environment, player.ship)
        ObjectLabels.draw(surface, fonts, w, h, gem.current_environment, player.ship)
        frame_watch.mark('markers and labels')
        CockpitButtons.draw(surface, w, h, PoliticalInfo.draw(surface, fonts, w, h), player)
        frame_watch.mark('buttons and political info')
        name = LocationInfo.draw_name(surface, fonts, w, h)
        Clock.draw(surface, fonts, date_time, player.time_scale, w, h,
                   right_middle=(name.left - max(12, int(w * 0.012)), name.centery),
                   dangerous=player.is_time_scale_dangerous())
