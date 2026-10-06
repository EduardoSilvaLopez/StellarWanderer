"""Heading indicator compass."""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import math
import pygame
from ..Constants import READOUT_BG, CONSOLE_EDGE_COLOR, ACCENT, ACCENT_DIM

if TYPE_CHECKING:
    from Player import Player


class Compass:
    """Draw a north-up compass dial with a needle showing the player's heading."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, cluster_top: int, cluster_height: int, left_bound: int) -> None:
        """Draw the compass dial.

        The dial stays fixed with 'N' at the top; the needle rotates to point
        in the direction the player is currently facing (player.yaw is
        in degrees, clockwise from north). Sized to fit between left_bound
        (the coordinate text block) and the centre multi-function display.
        """
        margin = int(w * 0.04)
        radius = max(10, int(cluster_height * 0.5))
        center = (left_bound + margin + radius + int(radius * 0.2), cluster_top + cluster_height // 2)

        pygame.draw.circle(surface, READOUT_BG, center, radius)
        pygame.draw.circle(surface, CONSOLE_EDGE_COLOR, center, radius, 2)

        # Cardinal tick marks (N/E/S/W), with N fixed at the top of the dial.
        tick_font = fonts.get(max(9, int(h * 0.015)))
        tick_len = max(3, int(radius * 0.16))
        for label, angle_deg in (('N', 0), ('E', 90), ('S', 180), ('W', 270)):
            angle = math.radians(angle_deg)
            dx, dy = math.sin(angle), -math.cos(angle)
            outer = (center[0] + dx * radius, center[1] + dy * radius)
            inner = (center[0] + dx * (radius - tick_len), center[1] + dy * (radius - tick_len))
            pygame.draw.line(surface, ACCENT_DIM, inner, outer, 2)

            label_pos = (center[0] + dx * (radius + tick_len), center[1] + dy * (radius + tick_len))
            label_surf = tick_font.render(label, True, ACCENT_DIM if label != 'N' else ACCENT)
            surface.blit(label_surf, label_surf.get_rect(center=label_pos))

        # Needle: points toward the player's current heading.
        heading = math.radians(player.yaw)
        dir_x, dir_y = math.sin(heading), -math.cos(heading)
        perp_x, perp_y = math.cos(heading), math.sin(heading)

        tip_len = radius * 0.75
        tail_len = radius * 0.3
        tip = (center[0] + dir_x * tip_len, center[1] + dir_y * tip_len)
        tail = (center[0] - dir_x * tail_len, center[1] - dir_y * tail_len)
        pygame.draw.line(surface, ACCENT, tail, tip, max(2, int(h * 0.004)))

        # Arrowhead at the tip.
        arrow_size = radius * 0.22
        base = (tip[0] - dir_x * arrow_size, tip[1] - dir_y * arrow_size)
        left = (base[0] + perp_x * arrow_size * 0.5, base[1] + perp_y * arrow_size * 0.5)
        right = (base[0] - perp_x * arrow_size * 0.5, base[1] - perp_y * arrow_size * 0.5)
        pygame.draw.polygon(surface, ACCENT, (tip, left, right))

        pygame.draw.circle(surface, ACCENT, center, max(2, int(h * 0.006)))
