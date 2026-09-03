"""Planet surface and rocks rendering."""

import math
import pygame
from .Constants import (
    CONSOLE_TOP, VIEW_VERTICAL_FOV_RADIANS, PLANET_GRAY, PLANET_HORIZON,
    ROCK_EDGE, NEAR_CLIP, MAX_DEPTH, ROCK_DEPTH_SCALE
)


class CurrentWorld:
    """Renders the planet surface and rocks visible from the cockpit."""

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
        CurrentWorld.draw_surface(surface, w, h, environment, player)

        # Find the Km2 to be drawn, poviding they exist.
        rocks = []
        for km2 in environment.current_world.Km2s:
            if (km2.longitude - km2.SIZE*2 <= player.position.x < km2.longitude + km2.SIZE*2 and
                km2.latitude - km2.SIZE*2 <= player.position.z < km2.latitude + km2.SIZE*2):
                rocks.extend(km2.rocks)
        CurrentWorld.draw_rocks(surface, w, h, player, rocks)

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

        horizon_y = int(view_h * 0.52)
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

        focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
        horizon_y = int(view_h * 0.52)

        def project(cx, cy, cz):
            """Project a camera-space offset (right, up, forward) to screen (x, y)."""
            screen_x = w / 2 + focal_length_px * cx / cz
            screen_y = horizon_y - focal_length_px * cy / cz
            return (screen_x, screen_y)

        # Gather rocks with their near-face depth, for far-to-near draw order.
        visible_rocks = []
        for rock in rocks:
            half = rock.size / 2.0
            z0 = rock.z - half - player_z  # near face forward depth
            if z0 <= NEAR_CLIP or z0 > MAX_DEPTH:
                continue
            visible_rocks.append((z0, rock, half))

        visible_rocks.sort(key=lambda item: item[0], reverse=True)  # far first

        for z0, rock, half in visible_rocks:
            # Cube extents in world space. It rests on the surface (y=0) and
            # rises to y=rock.size; x spans rock.x +/- half (true size).
            # z (depth) is rendered at ROCK_DEPTH_SCALE of the true size.
            x0, x1 = rock.x - half, rock.x + half
            y0, y1 = 0.0, rock.size
            render_depth = rock.size * ROCK_DEPTH_SCALE
            z1 = z0 + render_depth  # far face forward depth

            if z1 <= NEAR_CLIP:
                continue

            # Camera-space offsets (right, up) for each x/y value, forward depths for z.
            cx0, cx1 = x0 - player_x, x1 - player_x
            cy0, cy1 = y0 - player_y, y1 - player_y

            # Project the 8 corners.
            corners = {}
            for ix, cx in ((0, cx0), (1, cx1)):
                for iy, cy in ((0, cy0), (1, cy1)):
                    for iz, cz in ((0, z0), (1, z1)):
                        corners[(ix, iy, iz)] = project(cx, cy, cz)

            # A lateral face is visible only if the camera sits outside it.
            show_x1_face = player_x > x1  # camera east of the cube: see its +x face
            show_x0_face = player_x < x0  # camera west of the cube: see its -x face

            top_quad = [corners[(0, 1, 0)], corners[(1, 1, 0)],
                        corners[(1, 1, 1)], corners[(0, 1, 1)]]
            front_quad = [corners[(0, 0, 0)], corners[(1, 0, 0)],
                          corners[(1, 1, 0)], corners[(0, 1, 0)]]

            # Skip degenerate/too-small cubes.
            front_span = max(abs(front_quad[1][0] - front_quad[0][0]),
                              abs(front_quad[0][1] - front_quad[2][1]))
            if front_span < 1:
                continue

            # Draw back-to-front: top, side, front.
            top_color = tuple(max(0, c - 50) for c in rock.color)
            pygame.draw.polygon(surface, top_color, top_quad)
            pygame.draw.lines(surface, ROCK_EDGE, True, top_quad, 1)

            if show_x1_face:
                side_quad = [corners[(1, 0, 0)], corners[(1, 0, 1)],
                             corners[(1, 1, 1)], corners[(1, 1, 0)]]
                side_color = tuple(max(0, c - 25) for c in rock.color)
                pygame.draw.polygon(surface, side_color, side_quad)
                pygame.draw.lines(surface, ROCK_EDGE, True, side_quad, 1)
            elif show_x0_face:
                side_quad = [corners[(0, 0, 0)], corners[(0, 0, 1)],
                             corners[(0, 1, 1)], corners[(0, 1, 0)]]
                side_color = tuple(max(0, c - 25) for c in rock.color)
                pygame.draw.polygon(surface, side_color, side_quad)
                pygame.draw.lines(surface, ROCK_EDGE, True, side_quad, 1)

            pygame.draw.polygon(surface, rock.color, front_quad)
            pygame.draw.lines(surface, ROCK_EDGE, True, front_quad, 2)
