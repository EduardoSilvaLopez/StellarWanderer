"""The pictures of the areas of a screen: the files of common/resources/backgrounds named <prefix>*, chosen from
the seed of the place, so the same place always shows the same picture.

The outpost's files are outpost.<area>.*; the portal base's are portal_base.<area>.*. An area with no file has no
picture: the screen then falls back to what its place says (the outpost keeps its Dockmaster picture), and the portal
base shows black. A file is kept as it is; `cover` and `darken` make it fit the screen and fade it.
"""

from __future__ import annotations
import os
import random
from typing import Dict, List, Optional, Tuple

import pygame

from common.paths import resource_path

PORTAL_BASE_AREA_PREFIXES = {  # the picture of each area of the portal base, if a file of that prefix exists
    'Dockmaster': 'portal_base.dockmaster.',
    'Cargo': 'portal_base.cargo.',
    'Missions': 'portal_base.missions.',
    'Chat': 'portal_base.chat.',
    'Leave': 'portal_base.leave.',
}


def pictures_of(prefix: str) -> List[str]:
    """The files of common/resources/backgrounds whose names start with `prefix`, in a fixed order (none if the folder
    has no such file)."""
    folder = resource_path('backgrounds')
    if not os.path.isdir(folder):
        return []
    return sorted(
        os.path.join(folder, name) for name in os.listdir(folder)
        if name.startswith(prefix) and name.lower().endswith(('.jpg', '.jpeg', '.png'))
    )


def choose(prefixes: Dict[str, str], seed: int) -> Dict[str, Optional[str]]:
    """One file for each area, chosen from `seed` among the files of its prefix; None for an area with no file."""
    chosen: Dict[str, Optional[str]] = {}
    for area, prefix in prefixes.items():
        pictures = pictures_of(prefix)
        chosen[area] = random.Random(seed).choice(pictures) if pictures else None
    return chosen


def cover(image: pygame.Surface, size: Tuple[int, int]) -> pygame.Surface:
    """`image` scaled to fill `size` (keeping its proportions), cropped to its middle."""
    width, height = size
    scale = max(width / image.get_width(), height / image.get_height())
    scaled = pygame.transform.smoothscale(image, (round(image.get_width() * scale), round(image.get_height() * scale)))
    crop = pygame.Rect(0, 0, width, height)
    crop.center = scaled.get_rect().center
    return scaled.subsurface(crop).copy()


def darken(image: pygame.Surface, fraction: float) -> pygame.Surface:
    """`image` with `fraction` of it covered by black (0 leaves it as it is, 1 makes it black)."""
    shade = pygame.Surface(image.get_size())
    shade.fill((0, 0, 0))
    shade.set_alpha(round(255 * fraction))
    image.blit(shade, (0, 0))
    return image


def faded(file: Optional[str], size: Tuple[int, int], fade: float) -> pygame.Surface:
    """The picture of `file` covering `size` and darkened by `fade`, or black when there is no file (the portal base's
    fallback)."""
    if file is None:
        surface = pygame.Surface(size)
        surface.fill((0, 0, 0))
        return surface
    return darken(cover(pygame.image.load(file).convert(), size), fade)
