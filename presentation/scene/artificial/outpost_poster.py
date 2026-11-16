"""The propaganda billboard of a size 4 outpost: which poster it shows and how wide it is.

The posters are the images in common/resources/posters named after the entity, `<entity name>.<title>.<extension>`;
files that start otherwise (the "Alt." ones, the prompts) are ignored. The outpost's seed picks one, always the same.
An entity with no poster gets a plain grey board. It is plain Python, with no GL, so the preview in temp/ uses it too.
"""

from __future__ import annotations
import functools
import os
import random
from typing import TYPE_CHECKING, List, Optional, Tuple

import pygame

from common.paths import resource_path
from galaxies import seeds
from .outpost_yard import BILLBOARD_HEIGHT as HEIGHT

if TYPE_CHECKING:
    from galaxies.outpost import Outpost

POSTERS_FOLDER = resource_path('posters')
EXTENSIONS = ('.jpg', '.jpeg', '.png')
GREY_ASPECT = 1.25  # width over height of the board when there is no poster


@functools.lru_cache(maxsize=None)
def posters_of(entity_name: str) -> Tuple[str, ...]:
    """The poster files of an entity, by name."""
    if not os.path.isdir(POSTERS_FOLDER):
        return ()
    return tuple(os.path.join(POSTERS_FOLDER, name) for name in sorted(os.listdir(POSTERS_FOLDER))
                 if name.startswith(entity_name + '.') and name.lower().endswith(EXTENSIONS))


@functools.lru_cache(maxsize=None)
def aspect_of(path: str) -> float:
    """Width over height of a poster image."""
    width, height = pygame.image.load(path).get_size()
    return width / height


def poster_for(outpost: Outpost) -> Tuple[Optional[str], float]:
    """The poster file of the outpost (None if its entity has none) and the width in metres of the board, which keeps
    the poster's shape at a fixed height."""
    return _choice(outpost.seed, outpost.stellar_system.political_entity.name)


@functools.lru_cache(maxsize=None)
def _choice(seed: int, entity_name: str) -> Tuple[Optional[str], float]:
    files: List[str] = list(posters_of(entity_name))
    if not files:
        return None, GREY_ASPECT * HEIGHT
    path = random.Random(seeds.derive(seed, 'poster')).choice(files)
    return path, aspect_of(path) * HEIGHT
