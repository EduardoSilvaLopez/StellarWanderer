"""Labels for visible objects (star and all worlds) showing name and compact distance."""

from __future__ import annotations
from typing import Dict, Tuple, TYPE_CHECKING
import pygame
from .constants import ACCENT, OUTPOST_DOT_COLOR, OUTPOST_DOT_RADIUS_PX

if TYPE_CHECKING:
    from galaxies.world import World
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class ObjectLabels:
    """Render name and distance labels for visible objects (star and all worlds in the stellar system).

    Outposts of planets within BRAKING_RADIUS_MULTIPLE radii of the ship get a label with name and distance, bound
    and unbound. Their position is the sphere geometry (`Navigation.direction_to_point`) in both frames, so a label sits
    where the outpost really is. The sky dot for an outpost (OutpostMarkers) is drawn in the sky while unbound, and
    while bound on the surface in this overlay, so the 3D ground does not hide it. Outposts on the far side of their
    planet get no dot, but keep their label.

    While bound, the 3D view draws the ground flat from the surface offsets (longitude - player.x,
    latitude - player.z), and objects are drawn with those offsets. The flat ground differs from the sphere only by
    the curvature drop (about d²/2R, under 1 m within 2 km), so near the ship the labels and the drawn objects agree.
    Labels of distant outposts use the sphere geometry, not the flat offsets: a flat model would put far outposts on
    the horizon, while on a planet they can be hidden behind its curve.
    """

    LABEL_OFFSET_X = 4  # pixels from object center to the left edge of the label
    LABEL_OFFSET_Y = -4  # pixels from object center to the top of the label (negative = up)

    @staticmethod
    def draw(surface: pygame.Surface, fonts, w: int, h: int, environment: GameEnvironment, ship: Ship) -> None:
        """Draw labels: outposts in braking distance (bound and unbound), and the star and all worlds
        while unbound.

        A moon's label is skipped when it would overlap its planet's label.
        """
        from graphics.instruments.common import view_geometry, project_to_camera
        from common.units import format_compact_distance
        _, horizon_y, focal_length_px = view_geometry(h)
        label_font = fonts.get(max(9, int(h * 0.017)))

        # Outposts in braking distance: label with name and distance, also when they are behind their planet.
        # The sphere geometry is used in both frames, so the label sits where the outpost really is.
        from .outpost_markers import OutpostMarkers
        for outpost, point, visible in OutpostMarkers.in_braking_distance(environment, ship):
            vector = ship.navigation.direction_to_point(point, environment.date_time)
            projected = project_to_camera(ship, vector, w, horizon_y, focal_length_px)
            if projected is None:
                continue
            # Bound, the dot sits on the surface, in the overlay so the ground drawn in 3D does not hide it.
            # Only outposts in front of the planet get one; labels stay for all of them.
            if visible and ship.is_bound:
                pygame.draw.circle(surface, OUTPOST_DOT_COLOR, (int(projected[0]), int(projected[1])), OUTPOST_DOT_RADIUS_PX)
            label_surf, rect = ObjectLabels._render_label(
                label_font, outpost.name, format_compact_distance(vector.length()),
                int(projected[0]), int(projected[1])
            )
            surface.blit(label_surf, rect)

        if ship.is_bound:
            return

        world = environment.nearest_world
        star = world.parent_orbit.parent_stellar_system

        # Draw star label
        star_vector = ship.navigation.direction_to_star(world, environment.date_time)
        projected = project_to_camera(ship, star_vector, w, horizon_y, focal_length_px)
        if projected is not None:
            screen_x, screen_y = projected
            label_surf, rect = ObjectLabels._render_label(
                label_font, star.name, format_compact_distance(star_vector.length()),
                int(screen_x), int(screen_y)
            )
            surface.blit(label_surf, rect)

        # Draw labels for all worlds in the stellar system. get_all_worlds() lists each
        # planet before its moons, so the planet's label rectangle is known for its moons.
        drawn_rects: Dict[World, pygame.Rect] = {}
        for world_obj in star.get_all_worlds():
            world_vector = world_obj.calculate_stellar_position(environment.date_time) - ship.position.as_vector()
            projected = project_to_camera(ship, world_vector, w, horizon_y, focal_length_px)
            if projected is None:
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
    def _render_label(font, name: str, distance: str, center_x: int, center_y: int) -> Tuple[pygame.Surface, pygame.Rect]:
        """Render a single object label; returns its surface and its screen rectangle."""
        text = f'{name} {distance}'
        label_surf = font.render(text, True, ACCENT)
        rect = label_surf.get_rect(
            topleft=(center_x + ObjectLabels.LABEL_OFFSET_X, center_y + ObjectLabels.LABEL_OFFSET_Y)
        )
        return label_surf, rect
