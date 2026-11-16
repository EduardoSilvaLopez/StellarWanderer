"""The still picture of the portal base, for the scanner: the base as in the hero view, with its ring at rest.

It is drawn once per base and size, in software (flat colours, no texture, the faces sorted far to near), and kept: the
scanner shows it without spinning, to keep the frame rate. The model is the one the 3D view draws
(portal_base_shape.py), with the same light from the star.
"""

from __future__ import annotations
import numpy as np
import pygame

from .portal_base_shape import make_model

# The camera of the picture, in radii of the base (the hero view), and what it looks at.
VIEW_FROM = (1.1, -0.7, -3.2)
VIEW_AT = (0.0, 0.0, -0.1)
MARGIN = 0.08  # of the picture's size, round the base
PARTS = ('spinning_hull', 'sides', 'spokes', 'fixed_hull', 'hangar', 'interior', 'doors')
# The colour of each part's material, as a share of the light on it (the picture has no texture): the plating is
# reddish gunmetal (the textures' STEEL), the docking place is darker.
MATERIAL = {
    'spinning_hull': (0.47, 0.19, 0.20), 'sides': (0.47, 0.19, 0.20), 'spokes': (0.47, 0.19, 0.20),
    'fixed_hull': (0.47, 0.19, 0.20), 'hangar': (0.42, 0.18, 0.19), 'interior': (0.36, 0.31, 0.32),
    'doors': (0.36, 0.31, 0.32),
}


class PortalBaseHero:
    """Makes and keeps the pictures of the bases."""

    _pictures: dict[tuple[int, int], pygame.Surface] = {}

    @staticmethod
    def picture(base, size: int) -> pygame.Surface:
        """The picture of `base` in a `size` x `size` square, transparent where there is no base. Made the first
        time."""
        key = (base.seed, size)
        if key not in PortalBaseHero._pictures:
            PortalBaseHero._pictures[key] = PortalBaseHero._draw(base, size)
        return PortalBaseHero._pictures[key]

    @staticmethod
    def _draw(base, size: int) -> pygame.Surface:
        star_colour = base.stellar_system.star.color
        tint = tuple(int(255 * (0.7 + 0.3 * channel / 255.0)) for channel in star_colour)  # as PortalBaseGl
        model = make_model(base.radius, tint)
        radius = base.radius
        eye = np.array(VIEW_FROM) * radius
        forward = np.array(VIEW_AT) * radius - eye
        forward /= np.linalg.norm(forward)
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(up, forward)
        right /= np.linalg.norm(right)
        up = np.cross(forward, right)

        triangles, colours = [], []
        for name in PARTS:
            mesh = getattr(model, name)
            if len(mesh.positions) == 0:
                continue
            triangles.append(mesh.positions.reshape(-1, 3, 3))
            light = mesh.colours.reshape(-1, 3, 3)[:, 0, :].astype(np.float64) / 255.0  # one for each triangle
            colours.append(light * np.array(MATERIAL[name]) * 255.0)
        points = np.concatenate(triangles).astype(np.float64)
        colours = np.concatenate(colours)
        relative = points - eye
        screen = np.stack([relative @ right, relative @ up], axis=-1)  # (n, 3, 2)
        depth = (relative @ forward).mean(axis=1)
        order = np.argsort(-depth)  # far to near: the near faces are drawn last

        low = screen.reshape(-1, 2).min(axis=0)
        high = screen.reshape(-1, 2).max(axis=0)
        scale = size * (1.0 - 2.0 * MARGIN) / max(float((high - low).max()), 1e-9)
        centre = (low + high) / 2.0
        pixels = (screen - centre) * scale + size / 2.0
        pixels[..., 1] = size - pixels[..., 1]  # the picture's rows go down

        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))
        for index in order:
            colour = (int(colours[index, 0]), int(colours[index, 1]), int(colours[index, 2]), 255)
            pygame.draw.polygon(surface, colour, [(float(x), float(y)) for x, y in pixels[index]])
        return surface
