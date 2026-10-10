"""Target scanner display."""

from __future__ import annotations
from typing import Any, Tuple, TYPE_CHECKING
import math
import pygame
from ..Constants import ACCENT, ACCENT_DIM, AMBER, READOUT_BG, CONSOLE_EDGE_COLOR, ROCK_EDGE_COLOR
from ..Constants import MINE_HULL_COLOR, MINE_HULL_DARK, MINE_HULL_LIGHT, MINE_ACCENT, MINE_WARNING_A, MINE_CAP_COLOR
from .common import draw_beveled_panel

if TYPE_CHECKING:
    from Player import Player
    from Galaxies.Rock import Rock
    from Galaxies.ore_mine import OreMine


class Scanner:
    """Draw a square scanner readout showing targeted rock or ore mine."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, player: Player, cluster_top: int, cluster_height: int, mfd_right: int) -> None:
        """Draw the scanner display.

        Mirrors whatever rock or ore mine is currently in the laser's
        crosshair (whether or not the laser is actually firing), scaled to
        fill the square but kept at the same relative orientation and color
        the player sees ahead. Rocks take priority if somehow both are set.

        Below the square a rock shows its temperature (only above 0°) and then, if it is
        ore rich, its purity. The square always leaves room for those two text lines.
        """
        label_font = fonts.get(max(9, int(h * 0.017)))
        text_line_height = label_font.get_height() + 2

        margin = int(w * 0.04)
        available = max(0, (w - margin) - (mfd_right + margin))
        size = max(20, min(cluster_height - text_line_height, available))

        rect = pygame.Rect(0, 0, size, size)
        rect.centery = cluster_top + (cluster_height - text_line_height) // 2
        rect.right = w - margin

        label = label_font.render('SCANNER', True, ACCENT_DIM)
        surface.blit(label, label.get_rect(midbottom=(rect.centerx, rect.top - 6)))

        draw_beveled_panel(surface, rect)

        bevel_depth = max(2, rect.width // 24)
        text_y = rect.bottom + bevel_depth + 6

        rock = player.ship.laser.targeted_rock
        mine = player.ship.laser.targeted_mine
        if rock is not None:
            Scanner._draw_scanned_rock(surface, rect, player, rock)
            if rock.temperature > 0.0:
                temperature_text = label_font.render(f'Temperature: {round(rock.temperature)}°', True, AMBER)
                surface.blit(temperature_text, temperature_text.get_rect(midtop=(rect.centerx, text_y)))
                text_y += text_line_height
            if rock.is_ore_rich():
                purity_text = label_font.render(f'Ore Purity: {round(rock.get_purity() * 100)}%', True, (255, 255, 0))
                surface.blit(purity_text, purity_text.get_rect(midtop=(rect.centerx, text_y)))
        elif mine is not None:
            Scanner._draw_scanned_mine(surface, rect, mine)
            content_text = label_font.render(f'Content: {mine.content} Kg Ore', True, ACCENT)
            surface.blit(content_text, content_text.get_rect(midtop=(rect.centerx, text_y)))

    @staticmethod
    def _draw_scanned_rock(surface: pygame.Surface, rect: pygame.Rect, player: Player, rock: Rock) -> None:
        """Render `rock` inside `rect`, at the same relative orientation the
        player currently sees it from, normalized to a unit cube so every
        rock — regardless of true size or distance — fills the square.
        """
        view = math.radians(player.yaw)
        cos_view, sin_view = math.cos(view), math.sin(view)

        tilt = math.radians(rock.tilt)
        cos_t, sin_t = math.cos(tilt), math.sin(tilt)
        rock_orientation = math.radians(rock.orientation)
        cos_o, sin_o = math.cos(rock_orientation), math.sin(rock_orientation)

        def corner(sign_x: int, sign_y: int, sign_z: int) -> Tuple[float, float, float]:
            lx, ly, lz = float(sign_x), float(sign_y), float(sign_z)
            x1 = lx * cos_t - ly * sin_t
            y1 = lx * sin_t + ly * cos_t
            z1 = lz
            x2 = x1 * cos_o + z1 * sin_o
            z2 = -x1 * sin_o + z1 * cos_o
            cam_x = x2 * cos_view - z2 * sin_view
            cam_z = x2 * sin_view + z2 * cos_view
            return (cam_x, y1, cam_z)

        corners = {
            (sx, sy, sz): corner(sx, sy, sz)
            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)
        }

        xs = [c[0] for c in corners.values()]
        ys = [-c[1] for c in corners.values()]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)

        padding = max(10, int(min(rect.width, rect.height) * 0.18))
        scale = (min(rect.width, rect.height) - padding * 2) / span
        cx, cy = rect.centerx, rect.centery

        def project(c: Tuple[float, float, float]) -> Tuple[int, int]:
            return (int(cx + c[0] * scale), int(cy - c[1] * scale))

        top_color = tuple(max(0, v - 50) for v in rock.color)
        bottom_color = tuple(max(0, v - 70) for v in rock.color)
        side_color = tuple(max(0, v - 25) for v in rock.color)
        base_color = rock.color

        faces = (
            (top_color, ((-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1))),
            (bottom_color, ((-1, -1, 1), (1, -1, 1), (1, -1, -1), (-1, -1, -1))),
            (side_color, ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1))),
            (side_color, ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1))),
            (base_color, ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1))),
            (base_color, ((1, -1, 1), (-1, -1, 1), (-1, 1, 1), (1, 1, 1))),
        )

        def face_depth(indices: Tuple[Tuple[int, int, int], ...]) -> float:
            return sum(corners[index][2] for index in indices)

        for color, indices in sorted(faces, key=lambda face: face_depth(face[1]), reverse=True):
            points = [project(corners[index]) for index in indices]
            pygame.draw.polygon(surface, color, points)
            pygame.draw.lines(surface, ROCK_EDGE_COLOR, True, points, 1)

    @staticmethod
    def _draw_scanned_mine(surface: pygame.Surface, rect: pygame.Rect, mine: OreMine) -> None:
        """Render a simplified elevation icon of `mine` inside `rect`."""
        padding = max(6, int(min(rect.width, rect.height) * 0.12))
        body_width = int((rect.width - padding * 2) * 0.6)
        cap_height = max(4, int(body_width * 0.28))
        body_top = rect.top + padding
        body_left = rect.centerx - body_width // 2
        body_height = (rect.height - padding * 2) - cap_height

        body_rect = pygame.Rect(body_left, body_top + cap_height // 2, body_width, body_height)
        pygame.draw.rect(surface, MINE_HULL_COLOR, body_rect)
        pygame.draw.rect(surface, MINE_HULL_DARK, (body_rect.left, body_rect.top, body_rect.width // 3, body_rect.height))
        pygame.draw.rect(surface, MINE_HULL_LIGHT, (body_rect.right - body_rect.width // 6, body_rect.top, body_rect.width // 6, body_rect.height))

        top_cap_rect = pygame.Rect(body_left, body_top, body_width, cap_height)
        pygame.draw.ellipse(surface, MINE_CAP_COLOR, top_cap_rect)
        pygame.draw.ellipse(surface, MINE_HULL_DARK, top_cap_rect, 1)

        band_y = body_rect.top + int(body_rect.height * 0.42)
        pygame.draw.rect(surface, MINE_ACCENT, (body_rect.left, band_y, body_rect.width, max(2, body_rect.height // 20)))

        stripe_h = max(3, body_rect.height // 14)
        stripe_y = body_rect.bottom - stripe_h - 4
        pygame.draw.rect(surface, MINE_WARNING_A, (body_rect.left, stripe_y, body_rect.width, stripe_h))

        pygame.draw.rect(surface, MINE_HULL_DARK, body_rect, 1)
