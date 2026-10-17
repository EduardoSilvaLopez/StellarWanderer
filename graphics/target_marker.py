"""The target marker: an X on the canopy where the targeted body is, or on the canopy's border in the direction to it when the
body is out of view. Drawn while unbound only (while bound, the target is the world under the ship)."""

from __future__ import annotations
from typing import List, Optional, Tuple, TYPE_CHECKING
import pygame
from .constants import CANOPY_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET, CONSOLE_TOP, NEAR_CLIP, TARGET_MARKER_COLOR
from .instruments.common import view_geometry

if TYPE_CHECKING:
    from game_environment import GameEnvironment
    from spaceships.ship import Ship

Point = Tuple[float, float]


class TargetMarker:
    """Draws an X at the targeted body. The window is the canopy's trapezoid: its top edge, its bottom edge at the console,
    and the two pillars' inner edges. The X sits where the body projects if that is inside the trapezoid. Otherwise it
    sits where the ray from the crosshair toward the body leaves the trapezoid, so it points the way to turn."""

    ARM = 7  # length of each segment, from the outer end to the centre, in pixels
    GAP = 3  # the centre stays open: each segment starts this far from the centre
    THICKNESS = 2

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        if ship.is_bound:
            return
        body = environment.targeted_body
        direction = ship.navigation.direction_to_body(body, environment.date_time)
        window = TargetMarker._window(w, h)
        _, horizon_y, focal_length_px = view_geometry(h)
        centre: Point = (w / 2, horizon_y)  # where the crosshair is: the projection of the forward direction

        right, up, forward = ship.attitude.camera_components(direction)
        if forward > NEAR_CLIP:
            on_screen: Point = (
                w / 2 + focal_length_px * right / forward,
                horizon_y - focal_length_px * up / forward,
            )
            if TargetMarker._inside(on_screen, window):
                TargetMarker._draw_x(surface, on_screen)
                return
        # Out of view (behind, or beyond the window): the ray from the crosshair in the same screen direction as the body
        # leaves the window at this point.
        ray = (right, -up)
        point = TargetMarker._exit_point(centre, ray, window)
        if point is not None:
            TargetMarker._draw_x(surface, point)

    @staticmethod
    def _window(w: int, h: int) -> List[Point]:
        """The canopy's trapezoid, corners in order: top left, top right, bottom right, bottom left."""
        top = h * CANOPY_TOP
        bottom = h * CONSOLE_TOP
        top_inset = w * CANOPY_TOP_INSET
        bottom_inset = w * CANOPY_BOTTOM_INSET
        return [(top_inset, top), (w - top_inset, top), (w - bottom_inset, bottom), (bottom_inset, bottom)]

    @staticmethod
    def _inside(point: Point, polygon: List[Point]) -> bool:
        """True if the point is inside the convex polygon (corners in order, either winding)."""
        signs = set()
        for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
            cross = (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)
            if cross != 0.0:
                signs.add(cross > 0.0)
        return len(signs) <= 1

    @staticmethod
    def _exit_point(origin: Point, ray: Point, polygon: List[Point]) -> Optional[Point]:
        """Where the ray from origin (inside the polygon) leaves it, or None if the ray has no direction."""
        dx, dy = ray
        length = (dx * dx + dy * dy) ** 0.5
        if length == 0.0:
            return None
        dx, dy = dx / length, dy / length
        best: Optional[float] = None
        for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
            ex, ey = bx - ax, by - ay
            rx, ry = ax - origin[0], ay - origin[1]
            det = -dx * ey + ex * dy
            if det == 0.0:
                continue  # parallel to this edge
            t = (-rx * ey + ex * ry) / det
            s = (dx * ry - dy * rx) / det
            if t > 0.0 and 0.0 <= s <= 1.0 and (best is None or t < best):
                best = t
        if best is None:
            return None
        return origin[0] + best * dx, origin[1] + best * dy

    @staticmethod
    def _draw_x(surface: pygame.Surface, centre: Point) -> None:
        """Four separate segments forming an X, with the centre left open."""
        x, y = int(round(centre[0])), int(round(centre[1]))
        arm, gap = TargetMarker.ARM, TargetMarker.GAP
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            start = (x + sx * gap, y + sy * gap)
            end = (x + sx * arm, y + sy * arm)
            pygame.draw.line(surface, TARGET_MARKER_COLOR, start, end, TargetMarker.THICKNESS)
