"""Target scanner display."""

from __future__ import annotations
from typing import Any, Optional, Tuple, TYPE_CHECKING
import math
import numpy as np
import pygame
from ..constants import ACCENT, ACCENT_LABEL, AMBER
from ..constants import MINE_HULL_COLOR, MINE_HULL_DARK, MINE_HULL_LIGHT, MINE_ACCENT, MINE_WARNING_A, MINE_CAP_COLOR
from ..rock_shape import rock_meshes, rotate
from ..special_rocks import special_mesh
from .common import draw_beveled_panel, bezel_depth, panel_box_top

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from galaxies.asteroid import Asteroid
    from galaxies.rock import Rock
    from galaxies.ore_mine import OreMine
    from galaxies.outpost import Outpost

# The last scaled portrait: (source surface id, target size, scaled surface). Scaling is not repeated every frame.
_portrait_cache: Optional[Tuple[int, Tuple[int, int], pygame.Surface]] = None

# Rock temperature colours:
TEMPERATURE_COLORS = ((0, 0, 0), (48, 0, 0), (48, 8, 48), (24, 24, 64), (32, 32, 128))


class Scanner:
    """Draw a square scanner readout showing targeted rock, ore mine or outpost."""

    # Where the square is while the scoop is open (Ship.scoop_open), else None: the scoop's view (ScoopView) is drawn
    # there by OpenGLGui, over the cockpit.
    scoop_rect: Optional[pygame.Rect] = None

    @staticmethod
    def draw(surface: pygame.Surface, fonts: Any, w: int, h: int, ship: Ship, title_top: int, bottom: int,
             mfd_right: int) -> None:
        """Draw the scanner display.

        Mirrors whatever outpost, rock or ore mine is currently in the scanner's
        crosshair (whether or not the beam is actually on), scaled to
        fill the square but kept at the same relative orientation and color
        the player sees ahead. If somehow several are set, an outpost comes first, then a rock.

        A scanned outpost is titled SCANNER. With the scoop open the square is left empty, titled SCOOP: its view is
        drawn over it (`scoop_rect`).

        A rock shows its temperature (only above 0°) in the centre of the square, coloured by how
        hot it is. If it is ore rich, its purity is written above the square, in place of the title.
        A mine's content is written above the square, in place of the title, and its field's remaining
        ore inside the square, at the bottom. An external mine (another miners', see ExternalMine) says "Not ours"
        instead, with no field line.

        While unbound, the targeted asteroid that is not yet fully scanned and within scan range (`Scanner.scan_asteroid`)
        takes the square
        when nothing else is in it: its name in place of the title, its shape as the ship sees it (the mesh the 3D view
        draws, lit by the star), and over it the share scanned in the middle with a bar under it,
        and under that, in amber, what keeps the beam from working (`Scanner.scan_problem`) or, if nothing does, an
        invitation to hold SPACE (accent colour while the beam is on it).
        """
        label_font = fonts.get(max(9, int(h * 0.017)))

        margin = int(w * 0.02)
        available = max(0, (w - margin) - (mfd_right + margin))
        box_top = panel_box_top(label_font, title_top)
        size = max(20, min(bottom - box_top, available))  # the square ends at `bottom`

        rect = pygame.Rect(0, 0, size, size)
        rect.top = box_top
        rect.right = w - margin

        bevel_depth = bezel_depth(h)
        draw_beveled_panel(surface, rect, depth=bevel_depth)

        Scanner.scoop_rect = rect if ship.scoop_open else None
        if ship.scoop_open:
            title = label_font.render('SCOOP', True, ACCENT)
            surface.blit(title, title.get_rect(midtop=(rect.centerx, title_top)))
            return

        rock = ship.scanner.targeted_rock
        mine = ship.scanner.targeted_mine
        outpost = ship.scanner.targeted_outpost
        asteroid = ship.scanner.scan_asteroid if outpost is None and rock is None and mine is None else None
        # What the square shows (outposts first, then rocks, then mines), and the title above it. An ore rich rock
        # shows its purity, a mine its content, in place of the title.
        ore_rock = rock if outpost is None and rock is not None and rock.is_ore_rich() else None
        shown_mine = mine if outpost is None and rock is None else None
        if ore_rock is not None:
            title = label_font.render(f'Ore Purity: {round(ore_rock.get_purity() * 100)}%', True, (255, 255, 0))
        elif shown_mine is not None:
            title = label_font.render('Not ours' if shown_mine.is_external else f'Content: {int(shown_mine.content)} Kg Ore',
                                      True, ACCENT)
        elif asteroid is not None:
            title = label_font.render(asteroid.name, True, ACCENT)
        else:
            title = label_font.render('SCANNER', True, ACCENT)
        title_rect = title.get_rect(midtop=(rect.centerx, title_top))
        surface.blit(title, title_rect)
        if outpost is not None:
            Scanner._draw_scanned_outpost(surface, rect, outpost)
        elif rock is not None:
            Scanner._draw_scanned_rock(surface, rect, ship, rock)
            if rock.temperature > 0.0:
                temperature_text = label_font.render(
                    f'{round(rock.temperature)}°', True, Scanner._temperature_color(rock)
                )
                surface.blit(temperature_text, temperature_text.get_rect(center=rect.center))
        elif asteroid is not None:
            Scanner._draw_asteroid_scan(surface, label_font, rect, ship, asteroid)
        elif mine is not None:
            Scanner._draw_scanned_mine(surface, rect, mine)
            if not mine.is_external:
                field_text = label_font.render(f'Field: {int(mine.parent_field.remaining_ore)} Kg Ore', True, ACCENT)
                surface.blit(field_text, field_text.get_rect(midbottom=(rect.centerx, rect.bottom - 4)))

    @staticmethod
    def _draw_asteroid_scan(surface: pygame.Surface, font: pygame.font.Font, rect: pygame.Rect, ship: Ship,
                            asteroid: Asteroid) -> None:
        """The asteroid, then the share scanned as a number in the middle and a bar under it, and what the beam
        needs."""
        scanner = ship.scanner
        Scanner._draw_asteroid(surface, rect, ship, asteroid)
        percentage = Scanner._outlined(font, f'{int(asteroid.scan_progress * 100)}%', ACCENT)
        surface.blit(percentage, percentage.get_rect(center=rect.center))

        pad = max(6, rect.width // 12)
        track = pygame.Rect(rect.left + pad, rect.centery + percentage.get_height(), rect.width - 2 * pad,
                            max(6, font.get_height() // 2))
        pygame.draw.rect(surface, ACCENT_LABEL, track, 1)
        filled = int((track.width - 4) * asteroid.scan_progress)
        pygame.draw.rect(surface, ACCENT, (track.left + 2, track.top + 2, filled, track.height - 4))

        if scanner.scan_problem is not None:
            colour, text = AMBER, scanner.scan_problem
        elif ship.laser.firing:
            colour, text = ACCENT, 'Scanning...'
        else:
            colour, text = ACCENT, 'Hold SPACE to scan'
        for index, line in enumerate(text.split(': ')):  # "Too fast: 60 m/s, 50 m/s at most" on two lines
            rendered = Scanner._outlined(font, line, colour)
            top = track.bottom + 6 + index * font.get_linesize()
            surface.blit(rendered, rendered.get_rect(midtop=(rect.centerx, top)))

    @staticmethod
    def _outlined(font: pygame.font.Font, text: str, colour: Tuple[int, int, int]) -> pygame.Surface:
        """The text with a dark outline, to be read over the asteroid."""
        text_surface = font.render(text, True, colour)
        outline = font.render(text, True, (0, 0, 0))
        result = pygame.Surface((text_surface.get_width() + 2, text_surface.get_height() + 2), pygame.SRCALPHA)
        for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            result.blit(outline, (dx, dy))
        result.blit(text_surface, (1, 1))
        return result

    @staticmethod
    def _draw_asteroid(surface: pygame.Surface, rect: pygame.Rect, ship: Ship, asteroid: Asteroid) -> None:
        """The asteroid's mesh (graphics/asteroids.py) seen from the ship, filling the square: each face in the colour
        the star gives it, the ones turned away from the ship left out, the farthest first."""
        import game_environment as gem
        from ..asteroids import Asteroids
        model = Asteroids.model(asteroid.seed, 2.0 * asteroid.radius)
        date = gem.current_environment.date_time
        centre = np.array(tuple(asteroid.calculate_stellar_position(date)))
        to_ship = np.array(tuple(ship.position.as_vector())) - centre
        to_ship /= max(float(np.linalg.norm(to_ship)), 1.0)
        sun = -centre / max(float(np.linalg.norm(centre)), 1.0)

        faces = model.positions.reshape(-1, 3, 3).astype(np.float64)
        colours = model.colours(sun).reshape(-1, 3, 3).mean(axis=1)
        attitude = ship.attitude
        right, up, forward = (np.array(tuple(axis)) for axis in (attitude.right, attitude.up, attitude.forward))
        visible = np.flatnonzero(faces.mean(axis=1) @ to_ship > 0.0)
        depth = (faces[visible] @ forward).mean(axis=1)
        scale = (min(rect.width, rect.height) * 0.8) / (2.0 * asteroid.radius * 1.15)
        for i in visible[np.argsort(-depth)]:
            points = [(int(rect.centerx + float(corner @ right) * scale),
                       int(rect.centery - float(corner @ up) * scale)) for corner in faces[i]]
            pygame.draw.polygon(surface, tuple(int(value) for value in colours[i]), points)

    @staticmethod
    def _temperature_color(rock: Rock) -> Tuple[int, int, int]:
        """The colour for a rock's temperature above 0: one of TEMPERATURE_COLORS, by quarters of the rock's
        max_temperature."""
        quarter = int(rock.temperature / rock.max_temperature * len(TEMPERATURE_COLORS))
        return TEMPERATURE_COLORS[min(len(TEMPERATURE_COLORS) - 1, max(0, quarter))]

    @staticmethod
    def _draw_scanned_outpost(surface: pygame.Surface, rect: pygame.Rect, outpost: Outpost) -> None:
        """Draw the outpost's com officer's portrait to fill `rect`: scaled to cover it, keeping its proportions,
        and cropped equally from the top and bottom (or sides) where it overflows. No padding."""
        global _portrait_cache  # noqa: PLW0603 - a module-level cache, like the other textures
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

        if rock.adjective:
            triangles, normals, colours = special_mesh(rock.shape_seed, rock.adjective)  # the minerals' own colours
            triangles, normals = triangles[None], normals[None]
        else:
            triangles, normals, tones = rock_meshes([rock.shape_seed])
            colours = np.array(rock.color, dtype=np.float64) * tones[0][:, None]
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
            shade = 0.55 + 0.45 * (normals[i, 1] + 1.0) / 2.0
            colour = tuple(min(255, int(value * shade)) for value in colours[i])
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
        pygame.draw.rect(surface, MINE_HULL_DARK, (body_rect.left, body_rect.top, body_rect.width // 3,
                                                   body_rect.height))
        pygame.draw.rect(surface, MINE_HULL_LIGHT, (body_rect.right - body_rect.width // 6, body_rect.top,
                                                    body_rect.width // 6, body_rect.height))

        top_cap_rect = pygame.Rect(body_left, body_top, body_width, cap_height)
        pygame.draw.ellipse(surface, MINE_CAP_COLOR, top_cap_rect)
        pygame.draw.ellipse(surface, MINE_HULL_DARK, top_cap_rect, 1)

        band_y = body_rect.top + int(body_rect.height * 0.42)
        pygame.draw.rect(surface, MINE_ACCENT, (body_rect.left, band_y, body_rect.width,
                                                max(2, body_rect.height // 20)))

        stripe_h = max(3, body_rect.height // 14)
        stripe_y = body_rect.bottom - stripe_h - 4
        pygame.draw.rect(surface, MINE_WARNING_A, (body_rect.left, stripe_y, body_rect.width, stripe_h))

        pygame.draw.rect(surface, MINE_HULL_DARK, body_rect, 1)
