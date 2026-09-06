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

    def test_north_view_has_top_and_front_faces_only(self):
        player = self.make_player(orientation=0.0)
        rock = self.make_rock(0.0, 300.0)

        polygons, _ = self.render(player, rock)

        self.assertEqual(2, len(polygons))
        self.assertEqual(tuple(max(0, value - 50) for value in self.ROCK_COLOR), polygons[0][0])
        self.assertEqual(self.ROCK_COLOR, polygons[1][0])

    def test_north_west_view_keeps_the_same_lateral_face(self):
        left_x, left_z = self.world_position(315.0, -100.0, 300.0)
        right_x, right_z = self.world_position(315.0, 100.0, 300.0)

        left_polygons, _ = self.render(self.make_player(orientation=315.0), self.make_rock(left_x, left_z))
        right_polygons, _ = self.render(self.make_player(orientation=315.0), self.make_rock(right_x, right_z))

        self.assertEqual(3, len(left_polygons))
        self.assertEqual(3, len(right_polygons))

        left_side = left_polygons[1][1]
        right_side = right_polygons[1][1]
        left_origin = min(point[0] for point in left_side)
        right_origin = min(point[0] for point in right_side)
        left_shape = tuple((x - left_origin, y) for x, y in left_side)
        right_shape = tuple((x - right_origin, y) for x, y in right_side)
        self.assertEqual(len(left_shape), len(right_shape))
        for left_point, right_point in zip(left_shape, right_shape):
            self.assertAlmostEqual(left_point[0], right_point[0])
            self.assertAlmostEqual(left_point[1], right_point[1])

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
