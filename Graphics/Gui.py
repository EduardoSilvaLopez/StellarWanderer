"""Stellar Wanderer — first-person cockpit view.

Draws the pilot's-seat view of the player's ship as vector art: the starfield
seen through the canopy, the hull frame around it, and the instrument console.
The panel on the upper right is the ship clock — it starts at
500-01-01 00:00:00 and advances one second per real second.
"""

from .DeepSpace import DeepSpace
from .Stars import Stars
from .World import CurrentWorld
from .Cockpit import Cockpit
from .Constants import SPACE


class Gui:
    """Main cockpit graphics orchestrator."""

    def __init__(self):
        """Initialize the GUI with a starfield."""
        self.stars = Stars.make_starfield()

    def draw(self, surface, fonts, environment, player):
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
        surface.fill(SPACE)

        # Draw space and celestial objects
        DeepSpace.draw(surface, w, h)
        Stars.draw(surface, self.stars, w, h)
        CurrentWorld.draw(surface, w, h, environment, player)

        # Draw cockpit frame and instruments
        Cockpit.draw(surface, fonts, w, h, player, player.date_time, player.time_scale)


def draw(surface, fonts, environment, player):
    """Legacy interface for backward compatibility.

    Creates a Gui instance and draws the scene.

    Args:
        surface: Pygame surface to draw on
        fonts: Font manager
        stars: Pre-generated starfield (unused, uses Gui's own)
        environment: Game environment
        player: Player object
    """
    gui = Gui()
    gui.draw(surface, fonts, environment, player)
