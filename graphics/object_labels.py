"""Labels for visible objects (star and all worlds) showing name and compact distance."""

from __future__ import annotations
from typing import Dict, Tuple, TYPE_CHECKING
import math
import pygame
from common.units import format_compact_distance
from common.vector3 import Vector3
from .instruments.common import view_geometry, project_to_camera
from .outpost_markers import OutpostMarkers
from .constants import (
    ACCENT, OUTPOST_DOT_COLOR, OUTPOST_DOT_RADIUS_PX, CANOPY_TOP, CANOPY_TOP_INSET, CANOPY_BOTTOM_INSET, CONSOLE_TOP,
)

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.world import World
    from graphics.fallback_font import FallbackFont
    from graphics.font_cache import FontCache
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class ObjectLabels:
    """Render name and distance labels for visible objects (star and all worlds in the stellar system).

    Outposts of planets within FIXED_ZONE_RADIUS_MULTIPLE radii of the ship get a label with name and distance, unbound.
    Bound, only the outposts of the world the ship is bound to get one (see OutpostMarkers.in_fixed_zone). The sky dot for an outpost (OutpostMarkers) is drawn in the sky while unbound, and while bound on the
    surface in this overlay, so the 3D ground does not hide it. Outposts on the far side of their planet get no dot,
    but keep their label.

    Where the label sits depends on the frame. Unbound, it is the sphere geometry (`Navigation.direction_to_point`).
    Bound, it is the flat offsets (longitude - player.x, latitude - player.z) that the ship moves in, that the world
    map shows and that the 3D view draws objects with (the geometry of the bound frame is flat on purpose). The
    sphere differs from them: a longitude offset is shorter by cos(latitude), and almost nothing at the pole, so a
    sphere label would sit away from the building and approach it only as the ship does. With the flat offsets the
    label is where the building will be drawn, at any distance, and flying towards it leads there. The east
    offset is the nearest copy of the world, since the ship wraps at the anti-meridian.

    One thing is not flat: how far below the horizontal a bound label sits. That is the sphere's, from R + altitude,
    like the planet's edge that `FixedWorld.draw_surface` draws. With flat offsets only, an outpost beyond the horizon
    would hang in the empty sky above the planet's edge, a few degrees below the view axis, when the real horizon is
    far lower (at 400 km of altitude on a 6,000 km world it is 20 degrees down). So an outpost beyond the horizon is
    labelled on the horizon line, in its flat direction.

    A label is drawn only when its anchor is inside the windshield panes (see `_in_windshield`): an object seen above or
    beside the glass gets no label, so no label lies on the canopy frame.
    """

    LABEL_OFFSET_X = 4  # pixels from object center to the left edge of the label
    LABEL_OFFSET_Y = -4  # pixels from object center to the top of the label (negative = up)

    @staticmethod
    def draw(surface: pygame.Surface, fonts: FontCache, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        """Draw labels: outposts in the fixed zone (bound and unbound), and the star and all worlds
        while unbound.

        A moon's label is skipped when it would overlap its planet's label.
        """
        _, horizon_y, focal_length_px = view_geometry(h)
        label_font = fonts.get(max(9, int(h * 0.017)))
        ObjectLabels._draw_outpost_labels(surface, label_font, w, h, horizon_y, focal_length_px, environment, ship)
        if not ship.is_bound:
            ObjectLabels._draw_body_labels(surface, label_font, w, h, horizon_y, focal_length_px, environment, ship)

    @staticmethod
    def _draw_outpost_labels(surface: pygame.Surface, label_font: FallbackFont, w: int, h: int, horizon_y: int,
                             focal_length_px: float, environment: GameEnvironment, ship: Ship) -> None:
        """Outposts in the fixed zone: label with name and distance, also when they are behind their planet. Bound, the
        label sits where the 3D view draws the building (flat offsets); unbound, where the sphere puts it."""
        for outpost, point, visible in OutpostMarkers.in_fixed_zone(environment, ship):
            if ship.is_bound:
                vector, distance = ObjectLabels._bound_view_of_outpost(outpost, ship)
            else:
                vector = ship.navigation.direction_to_point(point, environment.date_time)
                distance = vector.length()
            projected = project_to_camera(ship, vector, w, horizon_y, focal_length_px)
            if projected is None or not ObjectLabels._in_windshield(projected, w, h):
                continue
            # Bound, the dot sits on the surface, in the overlay so the ground drawn in 3D does not hide it.
            # Only outposts in front of the planet get one; labels stay for all of them.
            if visible and ship.is_bound:
                pygame.draw.circle(surface, OUTPOST_DOT_COLOR, (int(projected[0]), int(projected[1])), OUTPOST_DOT_RADIUS_PX)
            label_surf, rect = ObjectLabels._render_label(
                label_font, outpost.name, format_compact_distance(distance),
                int(projected[0]), int(projected[1])
            )
            surface.blit(label_surf, rect)

    @staticmethod
    def _draw_body_labels(surface: pygame.Surface, label_font: FallbackFont, w: int, h: int, horizon_y: int,
                          focal_length_px: float, environment: GameEnvironment, ship: Ship) -> None:
        """The star and every world of the targeted body's system (unbound)."""
        body = environment.targeted_body
        system = body.stellar_system

        # Draw star label
        star_vector = ship.navigation.direction_to_star(body, environment.date_time)
        projected = project_to_camera(ship, star_vector, w, horizon_y, focal_length_px)
        if projected is not None and ObjectLabels._in_windshield(projected, w, h):
            screen_x, screen_y = projected
            label_surf, rect = ObjectLabels._render_label(
                label_font, system.star.name, format_compact_distance(star_vector.length()),
                int(screen_x), int(screen_y)
            )
            surface.blit(label_surf, rect)

        # Draw labels for all worlds in the stellar system. get_all_worlds() lists each
        # planet before its moons, so the planet's label rectangle is known for its moons.
        drawn_rects: Dict[World, pygame.Rect] = {}
        for world_obj in system.get_all_worlds():
            world_vector = world_obj.calculate_stellar_position(environment.date_time) - ship.position.as_vector()
            projected = project_to_camera(ship, world_vector, w, horizon_y, focal_length_px)
            if projected is None or not ObjectLabels._in_windshield(projected, w, h):
                continue
            screen_x, screen_y = projected
            label_surf, rect = ObjectLabels._render_label(
                label_font, world_obj.name, format_compact_distance(world_vector.length()),
                int(screen_x), int(screen_y)
            )
            if world_obj.parent_planet is not None:
                planet_rect = drawn_rects.get(world_obj.parent_planet)
                if planet_rect is not None and rect.colliderect(planet_rect):
                    continue
            drawn_rects[world_obj] = rect
            surface.blit(label_surf, rect)

    @staticmethod
    def _bound_view_of_outpost(outpost: Outpost, ship: Ship) -> Tuple[Vector3, float]:
        """The direction from the ship to the foot of the outpost's building, in the bound frame (east, up, north), and the
        distance to show. The azimuth and the distance are the flat offsets the 3D view draws with. How far down the direction
        points is the sphere's: the outpost is `ground / radius` of arc away, at most the arc to the horizon, so one beyond
        the horizon sits on the horizon line (see the class docstring)."""
        radius = outpost.planet.radius
        half_world = math.pi * radius  # the ship wraps at the anti-meridian, half the equator away
        east = (outpost.longitude - ship.position.x + half_world) % (2.0 * half_world) - half_world
        north = outpost.latitude - ship.position.z
        altitude = max(ship.position.y, 0.0)
        ground = math.hypot(east, north)
        distance = math.hypot(ground, altitude)
        if ground == 0.0:
            return Vector3(0.0, -altitude, 0.0), distance
        arc = min(ground / radius, math.acos(radius / (radius + altitude)))
        reach = radius * math.sin(arc)  # along the ground, in the plane tangent under the ship
        drop = radius + altitude - radius * math.cos(arc)  # below that plane
        return Vector3(east / ground * reach, -drop, north / ground * reach), distance

    @staticmethod
    def _in_windshield(point: Tuple[float, float], w: int, h: int) -> bool:
        """True if the screen point is in the windshield panes: below the top rail and between the two A-pillars, which
        angle inward from the top of the canopy to its bottom (see Canopy.draw)."""
        x, y = point
        top = h * CANOPY_TOP
        bottom = h * CONSOLE_TOP
        if not top <= y <= bottom:
            return False
        t = (y - top) / (bottom - top)
        left_pillar = w * (CANOPY_TOP_INSET + (CANOPY_BOTTOM_INSET - CANOPY_TOP_INSET) * t)
        return left_pillar <= x <= w - left_pillar

    @staticmethod
    def _render_label(font: FallbackFont, name: str, distance: str, center_x: int, center_y: int) -> Tuple[pygame.Surface, pygame.Rect]:
        """Render a single object label; returns its surface and its screen rectangle."""
        text = f'{name} {distance}'
        label_surf = font.render(text, True, ACCENT)
        rect = label_surf.get_rect(
            topleft=(center_x + ObjectLabels.LABEL_OFFSET_X, center_y + ObjectLabels.LABEL_OFFSET_Y)
        )
        return label_surf, rect
