"""Planet surface and rocks rendering."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple, Any
import math
import pygame
from .Constants import (
    PLANET_GRAY, ROCK_EDGE_COLOR, LASER_COLOR, NEAR_CLIP
)
from Graphics.Instruments.common import view_geometry

if TYPE_CHECKING:
    from Player import Player
    from GameEnvironment import GameEnvironment
    from Galaxies.Rock import Rock
    from Galaxies.OreField import OreField


class NearestWorld:
    """Renders the planet surface and rocks visible from the cockpit."""

    ROCK_DEPTH_PERSPECTIVE = 0.5

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """Draw planet surface and rocks.

        Args:
            surface: Pygame surface to draw on
            w: Window width
            h: Window height
            environment: Game environment with current world
            player: Player object with position
        """
        NearestWorld.draw_surface(surface, w, h, environment, player)

        # Find the Km2 to be drawn, poviding they exist.
        rocks = []
        ore_fields = []
        for km2 in environment.nearest_world.km2s:
            if (km2.longitude - km2.SIZE*2 <= player.position.x < km2.longitude + km2.SIZE*2 and
                km2.latitude - km2.SIZE*2 <= player.position.z < km2.latitude + km2.SIZE*2):
                rocks.extend(km2.rocks)
                ore_fields.extend(km2.ore_fields)
        NearestWorld.draw_ore_fields(surface, w, h, player, ore_fields, environment)
        NearestWorld.draw_rocks(surface, w, h, player, rocks, environment)

    @staticmethod
    def draw_surface(surface: pygame.Surface, w: int, h: int, environment: GameEnvironment, player: Player) -> None:
        """Draw the planet below the horizon as seen from the player's altitude.

        The camera looks horizontally, so the planet's centre lies straight down,
        off the bottom of the view. A pixel shows the planet when its view ray is
        within the sphere's angular radius of straight down. With sy measured below
        the horizon and sx sideways, that is sx^2 <= sy^2 * tan^2(a) - f^2, where a
        is the angular radius and f the focal length.
        """
        view_h, centre_y, focal_length_px = view_geometry(h)
        world_radius = environment.nearest_world.radius
        distance_to_center = world_radius + player.altitude_above_surface(environment.nearest_world)

        sin_angular = min(world_radius / distance_to_center, 0.9999)
        cos_angular = math.sqrt(1.0 - sin_angular * sin_angular)

        down_right, down_up, down_forward = player.camera_components(
            player.direction_down(environment.nearest_world, environment.date_time)
        )
        nadir_x, nadir_y, nadir_z = down_right, -down_up, down_forward

        center_x = w / 2
        focal = focal_length_px
        cos_sq = cos_angular * cos_angular

        def clamp_x(x: float) -> int:
            return int(max(-w, min(2 * w, x)))

        def visible_spans(sy: float) -> list:
            """Screen x offsets (from centre) inside the planet's disc on row sy."""
            a_term = nadir_y * sy + nadir_z * focal
            a = nadir_x * nadir_x - cos_sq
            b = 2.0 * nadir_x * a_term
            c = a_term * a_term - cos_sq * (sy * sy + focal * focal)
            if abs(a) < 1e-12:
                if abs(b) < 1e-12:
                    spans = [(-math.inf, math.inf)] if c >= 0 else []
                else:
                    root = -c / b
                    spans = [(root, math.inf)] if b > 0 else [(-math.inf, root)]
            else:
                disc = b * b - 4.0 * a * c
                if a < 0:
                    if disc < 0:
                        return []
                    root = math.sqrt(disc)
                    spans = [tuple(sorted(((-b - root) / (2 * a), (-b + root) / (2 * a))))]
                elif disc < 0:
                    spans = [(-math.inf, math.inf)]
                else:
                    root = math.sqrt(disc)
                    low, high = sorted(((-b - root) / (2 * a), (-b + root) / (2 * a)))
                    spans = [(-math.inf, low), (high, math.inf)]

            if abs(nadir_x) < 1e-12:
                allowed = (-math.inf, math.inf) if a_term > 0 else None
            elif nadir_x > 0:
                allowed = (-a_term / nadir_x, math.inf)
            else:
                allowed = (-math.inf, -a_term / nadir_x)
            if allowed is None:
                return []
            clipped = []
            for lo, hi in spans:
                lo, hi = max(lo, allowed[0]), min(hi, allowed[1])
                if lo < hi:
                    clipped.append((lo, hi))
            return clipped

        for y in range(view_h):
            for lo, hi in visible_spans(y - centre_y):
                pygame.draw.line(surface, PLANET_GRAY, (clamp_x(center_x + lo), y), (clamp_x(center_x + hi), y))

    @staticmethod
    def _camera_coordinates(world_x: float, world_z: float, player_x: float, player_z: float, sin_yaw: float, cos_yaw: float) -> Tuple[float, float]:
        """Yaw-only rotation of a world (x, z) offset into ship-relative (right, forward).
        While bound the ship only yaws (never pitches/rolls), so this 2-axis rotation is
        used instead of the full 3D player.camera_components for rocks/ore fields."""
        offset_x = world_x - player_x
        offset_z = world_z - player_z
        right = offset_x * cos_yaw - offset_z * sin_yaw
        forward = offset_x * sin_yaw + offset_z * cos_yaw
        return right, forward

    @staticmethod
    def _project_bound(cx: float, cy: float, cz: float, w: int, horizon_y: int, focal_length_px: float,
                        horizontal_depth: Optional[float] = None, depth_factor: float = 0.0) -> Tuple[float, float]:
        """Pinhole-project ship-relative (right, up, forward) coordinates while bound.
        draw_rocks passes horizontal_depth (a cube's center forward-depth) and depth_factor
        (ROCK_DEPTH_PERSPECTIVE) for its damped near/far perspective; draw_ore_fields calls
        with the defaults, which reduce to a plain project(cx, cy, cz)."""
        if horizontal_depth is None:
            horizontal_depth = cz
        blended_depth = horizontal_depth + depth_factor * (cz - horizontal_depth)
        screen_x = w / 2 + focal_length_px * cx / blended_depth
        screen_y = horizon_y - focal_length_px * cy / cz
        return screen_x, screen_y

    @staticmethod
    def draw_rocks(surface: pygame.Surface, w: int, h: int, player: Player, rocks: List[Rock], environment: GameEnvironment) -> None:
        """Draw rocks from the current world chunk as cubes on the surface.

        Each cube's 8 corners are projected individually through a pinhole-camera
        model (screen = focal_length * offset / forward_depth), so a cube's
        apparent shape genuinely depends on its position relative to the player:
        cubes ahead show only the front face, cubes off to one side reveal the
        matching lateral face, and size falls off with true forward depth rather
        than straight-line distance.
        """
        _, horizon_y, focal_length_px = view_geometry(h, horizon_fraction=0.52)

        player_x = player.position.x
        player_z = player.position.z
        player_y = player.position.y
        yaw = math.radians(player.yaw)
        sin_yaw = math.sin(yaw)
        cos_yaw = math.cos(yaw)

        depth_factor = NearestWorld.ROCK_DEPTH_PERSPECTIVE

        def camera_coordinates(world_x: float, world_z: float) -> Tuple[float, float]:
            return NearestWorld._camera_coordinates(world_x, world_z, player_x, player_z, sin_yaw, cos_yaw)

        # Gather rocks with their near-face depth, for far-to-near draw order.
        visible_rocks = []
        for rock in rocks:
            half = rock.size / 2.0
            near_depths = [
                camera_coordinates(rock.longitude - half, rock.latitude - half)[1],
                camera_coordinates(rock.longitude + half, rock.latitude - half)[1],
                camera_coordinates(rock.longitude - half, rock.latitude + half)[1],
                camera_coordinates(rock.longitude + half, rock.latitude + half)[1],
            ]
            z0 = min(near_depths)
            if z0 <= NEAR_CLIP or z0 > environment.nearest_world.SURROUNDINGS_RADIUS:
                continue
            visible_rocks.append((z0, rock, half))

        visible_rocks.sort(key=lambda item: item[0], reverse=True)  # far first

        for z0, rock, half in visible_rocks:
            # Build the actual axis-aligned cube in world space. Its dimensions
            # stay fixed while the camera yaw changes.
            x0, x1 = rock.longitude - half, rock.longitude + half
            z0_world, z1_world = rock.latitude - half, rock.latitude + half
            y0, y1 = 0.0, rock.size
            cy0, cy1 = y0 - player_y, y1 - player_y
            _, center_depth = camera_coordinates(rock.longitude, rock.latitude)

            # Project the 8 corners and retain depth for face sorting.
            corners = {}
            corner_depths = {}
            for ix, world_x in ((0, x0), (1, x1)):
                for iy, cy in ((0, cy0), (1, cy1)):
                    for iz, world_z in ((0, z0_world), (1, z1_world)):
                        corner_cx, corner_cz = camera_coordinates(world_x, world_z)
                        corners[(ix, iy, iz)] = NearestWorld._project_bound(
                            corner_cx, cy, corner_cz, w, horizon_y, focal_length_px,
                            horizontal_depth=center_depth, depth_factor=depth_factor
                        )
                        corner_depths[(ix, iy, iz)] = corner_cz

            if min(corner_depths.values()) <= NEAR_CLIP:
                continue

            top_quad = [corners[(0, 1, 0)], corners[(1, 1, 0)],
                        corners[(1, 1, 1)], corners[(0, 1, 1)]]
            bottom_quad = [corners[(0, 0, 1)], corners[(1, 0, 1)],
                           corners[(1, 0, 0)], corners[(0, 0, 0)]]
            x0_quad = [corners[(0, 0, 0)], corners[(0, 0, 1)],
                       corners[(0, 1, 1)], corners[(0, 1, 0)]]
            x1_quad = [corners[(1, 0, 1)], corners[(1, 0, 0)],
                       corners[(1, 1, 0)], corners[(1, 1, 1)]]
            z0_quad = [corners[(0, 0, 0)], corners[(1, 0, 0)],
                       corners[(1, 1, 0)], corners[(0, 1, 0)]]
            z1_quad = [corners[(1, 0, 1)], corners[(0, 0, 1)],
                       corners[(0, 1, 1)], corners[(1, 1, 1)]]

            # Skip degenerate/too-small cubes.
            face_span = max(abs(z0_quad[1][0] - z0_quad[0][0]),
                            abs(z0_quad[0][1] - z0_quad[2][1]))
            if face_span < 1:
                continue

            faces = [
                (top_quad, tuple(max(0, c - 50) for c in rock.color), 1,
                 [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]),
                (bottom_quad, tuple(max(0, c - 70) for c in rock.color), 1,
                 [(0, 0, 1), (1, 0, 1), (1, 0, 0), (0, 0, 0)]),
                (x0_quad, tuple(max(0, c - 25) for c in rock.color), 1,
                 [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
                (x1_quad, tuple(max(0, c - 25) for c in rock.color), 1,
                 [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)]),
                (z0_quad, rock.color, 2,
                 [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]),
                (z1_quad, rock.color, 2,
                 [(1, 0, 1), (0, 0, 1), (0, 1, 1), (1, 1, 1)]),
            ]

            def face_depth(face: Tuple[Any, Any, Any, List[Tuple[int, int, int]]]) -> float:
                return sum(corner_depths[index] for index in face[3])

            for face, color, edge_width, _ in sorted(faces, key=face_depth, reverse=True):
                pygame.draw.polygon(surface, color, face)
                pygame.draw.lines(surface, ROCK_EDGE_COLOR, True, face, edge_width)

    @staticmethod
    def draw_ore_fields(surface: pygame.Surface, w: int, h: int, player: Player, ore_fields: List[OreField], environment: GameEnvironment) -> None:
        """Draw ore fields as circles on the planet surface.

        Ore fields are 2D circles centered at (x, z) on the ground (y=0),
        projected using the same perspective as rocks.
        """
        _, horizon_y, focal_length_px = view_geometry(h, horizon_fraction=0.52)

        player_x = player.position.x
        player_z = player.position.z
        player_y = player.position.y
        yaw = math.radians(player.yaw)
        sin_yaw = math.sin(yaw)
        cos_yaw = math.cos(yaw)

        def project(cx: float, cy: float, cz: float) -> Tuple[float, float]:
            return NearestWorld._project_bound(cx, cy, cz, w, horizon_y, focal_length_px)

        def camera_coordinates(world_x: float, world_z: float) -> Tuple[float, float]:
            return NearestWorld._camera_coordinates(world_x, world_z, player_x, player_z, sin_yaw, cos_yaw)

        # Gather ore fields with their center depth, for far-to-near draw order.
        visible_fields = []
        for ore_field in ore_fields:
            center_cx, center_cz = camera_coordinates(ore_field.longitude, ore_field.latitude)
            if center_cz <= NEAR_CLIP or center_cz > environment.nearest_world.SURROUNDINGS_RADIUS:
                continue
            visible_fields.append((center_cz, ore_field, center_cx, center_cz))

        visible_fields.sort(key=lambda item: item[0], reverse=True)  # far first

        for depth, ore_field, center_cx, center_cz in visible_fields:
            # Project center and edge point to get radius on screen.
            # Apply radius in world space before camera rotation.
            center_screen = project(center_cx, -player_y, center_cz)

            # Project a point at the field's edge (world space: longitude + radius)
            edge_world_cx, edge_world_cz = camera_coordinates(
                ore_field.longitude + ore_field.radius, ore_field.latitude
            )
            edge_screen = project(edge_world_cx, -player_y, edge_world_cz)

            # Screen radius is the distance from center to edge projection
            dx = edge_screen[0] - center_screen[0]
            dy = edge_screen[1] - center_screen[1]
            radius_px = math.sqrt(dx * dx + dy * dy)

            if radius_px >= 1:
                pygame.draw.circle(surface, ore_field.color,
                                 (int(center_screen[0]), int(center_screen[1])),
                                 max(1, int(radius_px)))
