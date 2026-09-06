import math
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame

from Graphics.NearestWorld import NearestWorld


class RockRendererTests(unittest.TestCase):
    WIDTH = 1200
    HEIGHT = 800
    ROCK_COLOR = (120, 130, 140)

    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((self.WIDTH, self.HEIGHT))

    def tearDown(self):
        pygame.quit()

    def make_player(self, x=0.0, z=0.0, orientation=0.0):
        return SimpleNamespace(
            position=SimpleNamespace(x=x, y=10.0, z=z),
            orientation=orientation,
        )

    def make_rock(self, x, z, size=20.0):
        return SimpleNamespace(x=x, y=0.0, z=z, size=size, color=self.ROCK_COLOR)

    def render(self, player, rock):
        polygons = []
        lines = []
        with patch.object(
            pygame.draw, 'polygon', side_effect=lambda surface, color, points: polygons.append(
                (color, tuple(points))
            )
        ), patch.object(
            pygame.draw, 'lines', side_effect=lambda surface, color, closed, points, width: lines.append(
                (color, closed, tuple(points), width)
            )
        ):
            NearestWorld.draw_rocks(
                self.surface, self.WIDTH, self.HEIGHT, player, [rock]
            )
        return polygons, lines

    @staticmethod
    def world_position(orientation, right, forward):
        angle = math.radians(orientation)
        return (
            right * math.cos(angle) + forward * math.sin(angle),
            -right * math.sin(angle) + forward * math.cos(angle),
        )

    @staticmethod
    def polygon_bounds(points):
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return min(xs), max(xs), min(ys), max(ys)

    @staticmethod
    def polygon_area(points):
        return abs(sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )) / 2

    def test_north_view_has_top_and_front_faces_only(self):
        player = self.make_player(orientation=0.0)
        rock = self.make_rock(0.0, 300.0)

        polygons, _ = self.render(player, rock)

        self.assertEqual(2, len(polygons))
        self.assertEqual(tuple(max(0, value - 50) for value in self.ROCK_COLOR), polygons[0][0])
        self.assertEqual(self.ROCK_COLOR, polygons[1][0])

    def test_north_west_view_keeps_lateral_faces_visible(self):
        left_x, left_z = self.world_position(315.0, -100.0, 300.0)
        right_x, right_z = self.world_position(315.0, 100.0, 300.0)

        left_polygons, _ = self.render(self.make_player(orientation=315.0), self.make_rock(left_x, left_z))
        right_polygons, _ = self.render(self.make_player(orientation=315.0), self.make_rock(right_x, right_z))

        self.assertEqual(3, len(left_polygons))
        self.assertEqual(3, len(right_polygons))

        lateral_color = tuple(max(0, value - 25) for value in self.ROCK_COLOR)
        self.assertIn(lateral_color, [color for color, _ in left_polygons])
        self.assertIn(lateral_color, [color for color, _ in right_polygons])

    def test_north_facing_off_center_cube_shows_lateral_side(self):
        player = self.make_player(orientation=0.0)
        rock = self.make_rock(100.0, 300.0, size=40.0)

        polygons, _ = self.render(player, rock)

        self.assertEqual(3, len(polygons))
        lateral_color = tuple(max(0, value - 25) for value in self.ROCK_COLOR)
        self.assertIn(lateral_color, [color for color, _ in polygons])

    def test_large_rock_far_left_keeps_both_visible_faces(self):
        player = self.make_player(orientation=0.0)
        rock = self.make_rock(-300.0, 300.0, size=200.0)

        polygons, _ = self.render(player, rock)

        self.assertEqual(3, len(polygons))
        colors = [color for color, _ in polygons]
        self.assertIn(self.ROCK_COLOR, colors)
        self.assertIn(tuple(max(0, value - 25) for value in self.ROCK_COLOR), colors)

    def test_exact_large_left_rock_keeps_both_faces_visible_on_surface(self):
        player = self.make_player(orientation=0.0)
        rock = self.make_rock(-300.0, 300.0, size=200.0)
        self.surface.fill((0, 0, 0))

        NearestWorld.draw_rocks(self.surface, self.WIDTH, self.HEIGHT, player, [rock])

        lateral_color = tuple(max(0, value - 25) for value in self.ROCK_COLOR)
        lateral_pixels = 0
        front_pixels = 0
        for x in range(self.WIDTH):
            for y in range(self.HEIGHT):
                pixel = self.surface.get_at((x, y))[:3]
                lateral_pixels += pixel == lateral_color
                front_pixels += pixel == self.ROCK_COLOR
        self.assertGreater(lateral_pixels, 100)
        self.assertGreater(front_pixels, 100)

    def test_saved_015108_rock_keeps_lateral_face_when_near_center(self):
        player = self.make_player(
            x=951.4327261030509,
            z=-549.2694275752888,
            orientation=39.70000000000002,
        )
        rock = self.make_rock(953.0, -521.0, size=6.842351720307235)

        polygons, _ = self.render(player, rock)

        self.assertEqual(3, len(polygons))
        lateral_color = tuple(max(0, value - 25) for value in self.ROCK_COLOR)
        self.assertIn(lateral_color, [color for color, _ in polygons])

    def test_saved_015630_rock_keeps_z_face_when_ship_is_inside_depth_span(self):
        player = self.make_player(
            x=940.2839621618207,
            z=-523.2472243137905,
            orientation=39.70000000000002,
        )
        rock = self.make_rock(953.0, -521.0, size=6.842351720307235)

        polygons, _ = self.render(player, rock)

        self.assertEqual(3, len(polygons))
        self.assertIn(self.ROCK_COLOR, [color for color, _ in polygons])

    def test_saved_015952_lateral_face_switches_at_rock_center(self):
        rock_x, rock_z = 953.0, -521.0
        angle = math.radians(99.40000000000003)
        forward = 10.0

        def player_at_camera_right(right):
            return self.make_player(
                x=rock_x - (right * math.cos(angle) + forward * math.sin(angle)),
                z=rock_z - (-right * math.sin(angle) + forward * math.cos(angle)),
                orientation=99.40000000000003,
            )

        left_player = player_at_camera_right(-20.0)
        right_player = player_at_camera_right(20.0)
        rock = self.make_rock(rock_x, rock_z, size=6.842351720307235)

        left_polygons, _ = self.render(left_player, rock)
        right_polygons, _ = self.render(right_player, rock)

        self.assertEqual(3, len(left_polygons))
        self.assertEqual(3, len(right_polygons))
        self.assertNotEqual(left_polygons[1][1], right_polygons[1][1])

    def test_saved_020648_rock_keeps_top_and_both_vertical_faces_visible(self):
        player = self.make_player(
            x=955.0269258803817,
            z=-549.7524279037881,
            orientation=42.29999999999987,
        )
        rock = self.make_rock(953.0, -521.0, size=6.842351720307235)
        self.surface.fill((0, 0, 0))

        NearestWorld.draw_rocks(self.surface, self.WIDTH, self.HEIGHT, player, [rock])

        colors = {
            tuple(max(0, value - 50) for value in rock.color): 0,
            tuple(max(0, value - 25) for value in rock.color): 0,
            rock.color: 0,
        }
        for x in range(self.WIDTH):
            for y in range(self.HEIGHT):
                pixel = self.surface.get_at((x, y))[:3]
                if pixel in colors:
                    colors[pixel] += 1

        self.assertTrue(all(count > 100 for count in colors.values()))

    def test_rotated_cube_has_moderated_near_far_perspective(self):
        player = self.make_player(orientation=315.0)
        rock = self.make_rock(0.0, 300.0, size=40.0)

        polygons, _ = self.render(player, rock)
        lateral_face = polygons[1][1]
        near_edge_height = abs(lateral_face[3][1] - lateral_face[0][1])
        far_edge_height = abs(lateral_face[2][1] - lateral_face[1][1])

        self.assertNotAlmostEqual(near_edge_height, far_edge_height)
        ratio = max(near_edge_height, far_edge_height) / min(near_edge_height, far_edge_height)
        self.assertLess(ratio, 1.5)

    def test_rotated_cube_keeps_both_lateral_faces_visible(self):
        player = self.make_player(orientation=315.0)
        left_x, left_z = self.world_position(315.0, -180.0, 300.0)
        right_x, right_z = self.world_position(315.0, 180.0, 300.0)

        for rock_x, rock_z in ((left_x, left_z), (right_x, right_z)):
            polygons, _ = self.render(player, self.make_rock(rock_x, rock_z, size=40.0))

            self.assertEqual(3, len(polygons))
            lateral_faces = polygons[1:]
            self.assertTrue(all(self.polygon_area(points) > 1 for _, points in lateral_faces))

    def test_off_center_rock_keeps_the_same_front_face_width(self):
        left_x, left_z = self.world_position(0.0, -100.0, 300.0)
        right_x, right_z = self.world_position(0.0, 100.0, 300.0)

        left_polygons, _ = self.render(self.make_player(), self.make_rock(left_x, left_z))
        right_polygons, _ = self.render(self.make_player(), self.make_rock(right_x, right_z))

        left_bounds = self.polygon_bounds(left_polygons[-1][1])
        right_bounds = self.polygon_bounds(right_polygons[-1][1])
        self.assertAlmostEqual(left_bounds[1] - left_bounds[0], right_bounds[1] - right_bounds[0])

    def test_rock_crossing_near_clip_is_not_drawn(self):
        player = self.make_player()
        rock = self.make_rock(0.0, 0.1)

        polygons, lines = self.render(player, rock)

        self.assertEqual([], polygons)
        self.assertEqual([], lines)


if __name__ == '__main__':
    unittest.main()
