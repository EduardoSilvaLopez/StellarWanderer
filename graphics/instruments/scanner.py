"""Target scanner display."""

from __future__ import annotations
from typing import Any, Optional, Tuple, TYPE_CHECKING
import math
import numpy as np
import pygame
from ..constants import ACCENT
from ..constants import MINE_HULL_COLOR, MINE_HULL_DARK, MINE_HULL_LIGHT, MINE_ACCENT, MINE_WARNING_A, MINE_CAP_COLOR
from ..rock_shape import rock_meshes, rotate
from .common import draw_beveled_panel, bezel_depth, draw_panel_title, panel_box_top

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from galaxies.rock import Rock
    from galaxies.ore_mine import OreMine
    from galaxies.outpost import Outpost

# The last scaled portrait: (source surface id, target size, scaled surface). Scaling is not repeated every frame.
_portrait_cache: Optional[Tuple[int, Tuple[int, int], pygame.Surface]] = None

# Rock temperature colours, for 0-25%, 25-50%, 50-75% and 75-100% of Rock.TEMP_MAX (black, dark red, gray, blue).
TEMPERATURE_COLORS = ((0, 0, 0), (96, 24, 24), (96, 96, 96), (96, 96, 192))


class Scanner:
    """Draw a square scanner readout showing targeted rock, ore mine or outpost."""

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, title_top: int, bottom: int, mfd_right: int) -> None:
        """Draw the scanner display.

        Mirrors whatever rock or ore mine is currently in the scanner's
        crosshair (whether or not the beam is actually on), scaled to
        fill the square but kept at the same relative orientation and color
        the player sees ahead. Rocks take priority if somehow both are set.

        A rock shows its temperature (only above 0°) in the centre of the square, coloured by how
        hot it is, and below the square, if it is ore rich, its purity. The square always leaves room
        for the purity line.
        """
        label_font = fonts.get(max(9, int(h * 0.017)))
        text_line_height = label_font.get_height() + 2

        margin = int(w * 0.02)
        available = max(0, (w - margin) - (mfd_right + margin))
        box_top = panel_box_top(label_font, title_top)
        size = max(20, min(bottom - box_top, available))  # the square ends at `bottom`; its text goes below it

        rect = pygame.Rect(0, 0, size, size)
        rect.top = box_top
        rect.right = w - margin

        draw_panel_title(surface, label_font, 'SCANNER', rect.centerx, title_top)

        bevel_depth = bezel_depth(h)
        draw_beveled_panel(surface, rect, depth=bevel_depth)

        text_y = rect.bottom + bevel_depth + 6

        rock = ship.scanner.targeted_rock
        mine = ship.scanner.targeted_mine
        outpost = ship.scanner.targeted_outpost
        if outpost is not None:
            Scanner._draw_scanned_outpost(surface, rect, outpost)
        elif rock is not None:
            Scanner._draw_scanned_rock(surface, rect, ship, rock)
            if rock.temperature > 0.0:
                temperature_text = label_font.render(
                    f'{round(rock.temperature)}°', True, Scanner._temperature_color(rock.temperature)
                )
                surface.blit(temperature_text, temperature_text.get_rect(center=rect.center))
            if rock.is_ore_rich():
                purity_text = label_font.render(f'Ore Purity: {round(rock.get_purity() * 100)}%', True, (255, 255, 0))
                surface.blit(purity_text, purity_text.get_rect(midtop=(rect.centerx, text_y)))
        elif mine is not None:
            Scanner._draw_scanned_mine(surface, rect, mine)
            content_text = label_font.render(f'Content: {int(mine.content)} Kg Ore', True, ACCENT)
            surface.blit(content_text, content_text.get_rect(midtop=(rect.centerx, text_y)))
            text_y += text_line_height
            field_text = label_font.render(f'Field: {int(mine.parent_field.remaining_ore)} Kg Ore', True, ACCENT)
            surface.blit(field_text, field_text.get_rect(midtop=(rect.centerx, text_y)))

    @staticmethod
    def _temperature_color(temperature: float) -> Tuple[int, int, int]:
        """The colour for a rock temperature above 0: one of TEMPERATURE_COLORS, by quarters of Rock.TEMP_MAX."""
        from galaxies.rock import Rock
        quarter = int(temperature / Rock.TEMP_MAX * len(TEMPERATURE_COLORS))
        return TEMPERATURE_COLORS[min(len(TEMPERATURE_COLORS) - 1, max(0, quarter))]

    @staticmethod
    def _draw_scanned_outpost(surface: pygame.Surface, rect: pygame.Rect, outpost: Outpost) -> None:
        """Draw the outpost's com officer's portrait to fill `rect`: scaled to cover it, keeping its proportions,
        and cropped equally from the top and bottom (or sides) where it overflows. No padding."""
        global _portrait_cache
        icon = outpost.com_officer.icon
        if icon is None:
            return
        scale = max(rect.width / icon.get_width(), rect.height / icon.get_height())
        size = (max(rect.width, round(icon.get_width() * scale)), max(rect.height, round(icon.get_height() * scale)))
        key = (id(icon), size)
        if _portrait_cache is None or _portrait_cache[:2] != key:
            _portrait_cache = (id(icon), size, pygame.transform.smoothscale(icon, size))
        scaled = _portrait_cache[2]
        crop = pygame.Rect(0, 0, rect.width, rect.height)
        crop.center = (scaled.get_width() // 2, scaled.get_height() // 2)
        surface.blit(scaled, rect.topleft, area=crop)

    @staticmethod
    def _draw_scanned_rock(surface: pygame.Surface, rect: pygame.Rect, ship: Ship, rock: Rock) -> None:
        """Render `rock`'s boulder inside `rect`, at the same relative orientation the player currently sees it
        from, normalized to its bounding cube so every rock, regardless of true size or distance, fills the square.
        The shape is the one the 3D view draws (graphics/rock_shape.py); each triangle is shaded by its normal."""
        view = math.radians(ship.attitude.yaw)
        cos_view, sin_view = math.cos(view), math.sin(view)
        tilt, orientation = np.array([rock.tilt]), np.array([rock.orientation])

        triangles, normals, tones = rock_meshes([rock.shape_seed])
        points = rotate(triangles.reshape(1, -1, 3), tilt, orientation)[0].reshape(-1, 3, 3)
        normals = rotate(normals, tilt, orientation)[0]

        def camera(vectors: np.ndarray) -> np.ndarray:
            """(x east-ish, y up, z depth) in the player's view; larger z is farther."""
            return np.stack((vectors[..., 0] * cos_view - vectors[..., 2] * sin_view, vectors[..., 1],
                             vectors[..., 0] * sin_view + vectors[..., 2] * cos_view), axis=-1)

        points, normals = camera(points), camera(normals)
        span = max(np.ptp(points[..., 0]), np.ptp(points[..., 1]), 1e-6)
        padding = max(10, int(min(rect.width, rect.height) * 0.18))
        scale = (min(rect.width, rect.height) - padding * 2) / span
        cx, cy = rect.centerx, rect.centery

        # Triangles facing the viewer, farthest first.
        order = [i for i in np.argsort(-points[..., 2].mean(axis=1)) if normals[i, 2] < 0.0]
        for i in order:
            shade = (0.55 + 0.45 * (normals[i, 1] + 1.0) / 2.0) * tones[0, i]
            colour = tuple(min(255, int(value * shade)) for value in rock.color)
            pygame.draw.polygon(surface, colour, [(int(cx + x * scale), int(cy - y * scale)) for x, y, _ in points[i]])

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
