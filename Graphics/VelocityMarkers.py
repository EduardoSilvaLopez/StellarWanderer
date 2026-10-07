"""Prograde/retrograde velocity markers over the canopy, shown only while unbound."""

from __future__ import annotations
from typing import Any, Tuple, TYPE_CHECKING
import pygame
from .Constants import PROGRADE_COLOR, RETROGRADE_COLOR

if TYPE_CHECKING:
    from Player import Player


class VelocityMarkers:
    """Markers showing the ship's current direction of travel (prograde) and its
    exact opposite (retrograde — point here and hold W to cancel drift), both
    measured in the same reference frame as linear braking (Player.velocity_reference_frame)."""

    MIN_SPEED = 0.01  # m/s; below this the direction is numerically meaningless
    PROJECTION_DISTANCE = 1000.0  # arbitrary "reach" for the direction vector, see draw()
    PROGRADE_RADIUS = 6
    RETROGRADE_RADIUS = 12
    RETROGRADE_THICKNESS = 2
    LABEL_OFFSET_Y = 16

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player) -> None:
        """Draw prograde/retrograde markers while unbound; no-op while bound or near-stationary."""
        if player.is_bound:
            return

        relative = player.velocity.as_vector() - player.velocity_reference_frame()
        if relative.length() < VelocityMarkers.MIN_SPEED:
            return

        from Graphics.Instruments.common import view_geometry, project_to_camera
        _, horizon_y, focal_length_px = view_geometry(h)

        # project_to_camera's near-clip check expects a position-like vector in
        # metres (NEAR_CLIP = 0.5 m). A raw velocity vector would get wrongly
        # near-clip-rejected whenever its forward-axis component is small, even
        # for a residual drift the player still needs to see. Project a pure
        # direction at a fixed, arbitrary distance instead, so clipping depends
        # only on true geometric direction, never on how fast the ship is moving.
        direction = relative.normalized() * VelocityMarkers.PROJECTION_DISTANCE

        prograde = project_to_camera(player, direction, w, horizon_y, focal_length_px)
        if prograde is not None:
            VelocityMarkers._draw_prograde(surface, fonts, prograde)

        retrograde = project_to_camera(player, -direction, w, horizon_y, focal_length_px)
        if retrograde is not None:
            VelocityMarkers._draw_retrograde(surface, fonts, retrograde)

    @staticmethod
    def _draw_prograde(surface: pygame.Surface, fonts: Any, center: Tuple[float, float]) -> None:
        pos = (int(center[0]), int(center[1]))
        pygame.draw.circle(surface, PROGRADE_COLOR, pos, VelocityMarkers.PROGRADE_RADIUS)
        VelocityMarkers._draw_label(surface, fonts, 'PRO', PROGRADE_COLOR, pos)

    @staticmethod
    def _draw_retrograde(surface: pygame.Surface, fonts: Any, center: Tuple[float, float]) -> None:
        pos = (int(center[0]), int(center[1]))
        pygame.draw.circle(surface, RETROGRADE_COLOR, pos, VelocityMarkers.RETROGRADE_RADIUS, VelocityMarkers.RETROGRADE_THICKNESS)
        VelocityMarkers._draw_label(surface, fonts, 'RETRO', RETROGRADE_COLOR, pos)

    @staticmethod
    def _draw_label(surface: pygame.Surface, fonts: Any, text: str, color: Tuple[int, int, int], center: Tuple[int, int]) -> None:
        font = fonts.get(10)
        label_surf = font.render(text, True, color)
        rect = label_surf.get_rect(center=(center[0], center[1] + VelocityMarkers.LABEL_OFFSET_Y))
        surface.blit(label_surf, rect)
