"""The ORBIT button, bottom left of the cockpit while the ship is unbound, the left half of its row (the TRAVEL button
has the right one, see travel_button.py): the sideways speed an orbit needs, as a bar the drift fills over the whole
row's width, and the button that starts the ORBIT assist (spaceships/orbit_assist.py), or leaves the orbit."""

from __future__ import annotations
import math
from typing import Any, Tuple, TYPE_CHECKING
import pygame

from ..constants import ACCENT, ACCENT_DIM, ACCENT_LABEL, BINDING_NEAR_GREEN, GRAVITY_GREEN, GRAVITY_RED, READOUT_BG

if TYPE_CHECKING:
    from galaxies.body import Body
    from spaceships.ship import Ship


class OrbitButton:
    """The ORBIT button and its bar. The bar's target is the circular speed at the ship's distance; it is red while the
    lowest point of the path is under the bind shell, and green once the path clears it (the darker set of the gravity
    bar). Its place is that of the last
    draw, and a click counts only in the cockpit (see hit)."""

    rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
    GAP = 4  # pixels between the ORBIT and TRAVEL buttons

    @staticmethod
    def enabled(ship: Ship) -> bool:
        """The button lights up in a fixed zone of a world that pulls, unbound, but not inside a giant."""
        import game_environment as gem
        from galaxies.world import World
        body = gem.current_environment.fixed_body
        return not ship.is_bound and isinstance(body, World) and body.gravitational_parameter > 0.0 \
            and ship.navigation.in_fixed_zone(body) and not ship.navigation.is_inside(body)

    @staticmethod
    def hit(position: Tuple[int, int], ship: Ship) -> bool:
        """Whether a click at `position` is on the button while it does something: lit, or in orbit (to leave it)."""
        if ship.owner.inside is not None:
            return False
        return OrbitButton.rect.collidepoint(position) and (ship.navigation.orbit is not None
                                                            or OrbitButton.enabled(ship))

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, h: int, ship: Ship, left: int, bottom: int, width: int) -> None:
        """The bar above the button, the button at the bottom: the bar `width` wide from `left`, the button the left half
        of that."""
        if ship.is_bound:
            return
        label_font = fonts.get(max(9, int(h * 0.017)))
        height = label_font.get_height() + 6
        OrbitButton.rect = pygame.Rect(left, bottom - height, (width - OrbitButton.GAP) // 2, height)
        running = ship.navigation.orbit is not None
        lit = OrbitButton.enabled(ship)
        colour = ACCENT if running else (BINDING_NEAR_GREEN if lit else ACCENT_DIM)
        if running:
            pygame.draw.rect(surface, colour, OrbitButton.rect, border_radius=3)
        pygame.draw.rect(surface, colour, OrbitButton.rect, 1, border_radius=3)
        text = label_font.render('ORBIT', True, READOUT_BG if running else colour)
        surface.blit(text, text.get_rect(center=OrbitButton.rect.center))
        if lit:
            OrbitButton._draw_bar(surface, label_font, ship, left, OrbitButton.rect.top - height, width)

    @staticmethod
    def _draw_bar(surface: pygame.Surface, label_font: Any, ship: Ship, left: int, top: int, width: int) -> None:
        """The label and the track of the sideways speed, on the row at `top`: the drift as a share of the circular
        speed at the ship's distance, red while the lowest point is under the bind shell, else green."""
        import game_environment as gem
        from galaxies.kepler import apsides
        from spaceships.navigation import Navigation
        body: Body = gem.current_environment.fixed_body
        r_vec, v_vec = ship.navigation._relative_to_body(body)
        periapsis, _, _ = apsides(body.gravitational_parameter, r_vec, v_vec)
        circular_speed = math.sqrt(body.gravitational_parameter / r_vec.length())
        fraction = min(1.0, ship.navigation.drift_speed(body) / circular_speed)
        colour = GRAVITY_RED if periapsis < Navigation.BIND_RADIUS_MULTIPLE * body.radius else GRAVITY_GREEN

        label = label_font.render('Orbit:', True, ACCENT_LABEL)
        gap = label_font.size(' ')[0]
        surface.blit(label, (left, top))
        track = pygame.Rect(left + label.get_width() + gap, top + 3, width - label.get_width() - gap,
                            label_font.get_height() - 6)
        pygame.draw.rect(surface, ACCENT_DIM, track, 1)
        pygame.draw.rect(surface, colour, (track.left + 2, track.top + 2, int((track.width - 4) * fraction),
                                           track.height - 4))
