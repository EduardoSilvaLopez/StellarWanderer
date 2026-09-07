"""Planet surface and rocks rendering."""

import math
import pygame
from .Constants import (
    CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, PLANET_GRAY, PLANET_HORIZON,
    ROCK_EDGE, NEAR_CLIP, MAX_DEPTH
)


class NearestWorld:
    """Renders the planet surface and rocks visible from the cockpit."""

    ROCK_DEPTH_PERSPECTIVE = 0.5

    @staticmethod
    def draw(surface, w, h, environment, player):
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
        for km2 in environment.current_world.Km2s:
            if (km2.longitude - km2.SIZE*2 <= player.position.x < km2.longitude + km2.SIZE*2 and
                km2.latitude - km2.SIZE*2 <= player.position.z < km2.latitude + km2.SIZE*2):
                rocks.extend(km2.rocks)
        NearestWorld.draw_rocks(surface, w, h, player, rocks)

    @staticmethod
    def draw_surface(surface, w, h, environment, player):
        """Draw planet surface and horizon.

        Planet is not fitted to viewport; its screen radius is the projected
        angular radius seen by the observer. Large planets produce an enormous
        off-screen circle and a nearly flat horizon, while small planets show
        visible curvature.
        """
        view_h = int(h * CONSOLE_TOP)
        planet_radius = environment.current_world.radius
        observer_radius = planet_radius + player.position.y

        focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
        angular_radius = math.asin(planet_radius / observer_radius)
        planet_radius_px = focal_length_px * math.tan(angular_radius)

        horizon_y = int(view_h * 0.5)
        planet_center = (w // 2, int(horizon_y + planet_radius_px))

        pygame.draw.circle(
            surface,
            PLANET_GRAY,
            planet_center,
            max(1, int(planet_radius_px)),
        )
        pygame.draw.arc(
            surface,
            PLANET_HORIZON,
            pygame.Rect(
                int(planet_center[0] - planet_radius_px),
                int(planet_center[1] - planet_radius_px),
                int(planet_radius_px * 2),
                int(planet_radius_px * 2),
            ),
            math.pi,
            math.tau,
            2,
        )

    @staticmethod
    def draw_rocks(surface, w, h, player, rocks):
        """Draw rocks from the current world chunk as cubes on the surface.

        Each cube's 8 corners are projected individually through a pinhole-camera
        model (screen = focal_length * offset / forward_depth), so a cube's
        apparent shape genuinely depends on its position relative to the player:
        cubes ahead show only the front face, cubes off to one side reveal the
        matching lateral face, and size falls off with true forward depth rather
        than straight-line distance.
        """
        view_h = int(h * CONSOLE_TOP)

        player_x = player.position.x
        player_z = player.position.z
        player_y = player.position.y
        orientation = math.radians(player.orientation)
        sin_orientation = math.sin(orientation)
        cos_orientation = math.cos(orientation)

        focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
        horizon_y = int(view_h * 0.52)

        depth_factor = NearestWorld.ROCK_DEPTH_PERSPECTIVE

        def project(cx, cy, cz, horizontal_depth):
            """Project a corner with damped horizontal depth perspective."""
            blended_depth = horizontal_depth + depth_factor * (cz - horizontal_depth)
            screen_x = w / 2 + focal_length_px * cx / blended_depth
            screen_y = horizon_y - focal_length_px * cy / cz
            return (screen_x, screen_y)

        def camera_coordinates(world_x, world_z):
            """Convert world coordinates to offsets relative to the ship's heading."""
            offset_x = world_x - player_x
            offset_z = world_z - player_z
            right = offset_x * cos_orientation - offset_z * sin_orientation
            forward = offset_x * sin_orientation + offset_z * cos_orientation
            return right, forward

        # Gather rocks with their near-face depth, for far-to-near draw order.
        visible_rocks = []
        for rock in rocks:
            half = rock.size / 2.0
            near_depths = [
                camera_coordinates(rock.x - half, rock.z - half)[1],
                camera_coordinates(rock.x + half, rock.z - half)[1],
                camera_coordinates(rock.x - half, rock.z + half)[1],
                camera_coordinates(rock.x + half, rock.z + half)[1],
            ]
            z0 = min(near_depths)
            if z0 <= NEAR_CLIP or z0 > MAX_DEPTH:
                continue
            visible_rocks.append((z0, rock, half))

        visible_rocks.sort(key=lambda item: item[0], reverse=True)  # far first

        for z0, rock, half in visible_rocks:
            # Build the actual axis-aligned cube in world space. Its dimensions
            # stay fixed while the camera orientation changes.
            x0, x1 = rock.x - half, rock.x + half
            z0_world, z1_world = rock.z - half, rock.z + half
            y0, y1 = 0.0, rock.size
            cy0, cy1 = y0 - player_y, y1 - player_y
            _, center_depth = camera_coordinates(rock.x, rock.z)

            # Project the 8 corners and retain depth for face sorting.
            corners = {}
            corner_depths = {}
            for ix, world_x in ((0, x0), (1, x1)):
                for iy, cy in ((0, cy0), (1, cy1)):
                    for iz, world_z in ((0, z0_world), (1, z1_world)):
                        corner_cx, corner_cz = camera_coordinates(world_x, world_z)
                        corners[(ix, iy, iz)] = project(
                            corner_cx, cy, corner_cz, center_depth
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

            def face_depth(face):
                return sum(corner_depths[index] for index in face[3])

            for face, color, edge_width, _ in sorted(faces, key=face_depth, reverse=True):
                pygame.draw.polygon(surface, color, face)
                pygame.draw.lines(surface, ROCK_EDGE, True, face, edge_width)
