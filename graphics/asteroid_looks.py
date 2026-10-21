"""How the surface of an asteroid looks: its class, its colour and how patchy it is, and how the sun lights it.

An asteroid has one of the classes the real ones are sorted in (galaxies/asteroid_class.py): carbonaceous (dark, most of
those in the main belt), stony (a reddish brown), metallic (grey) and basaltic (bright). Each class has several
variants that differ in how patchy the surface is: broad dark and light areas, finer mottling. The class and the variant
come from the asteroid's seed, so the same asteroid always looks the same. The colours are display values: the real
differences in reflectance are compressed, so that the darkest is still seen against the sky.

No image is used: the surface colour is a smooth noise over the asteroid's own directions (so it has no seams), times
the tones of the mesh (darker crater floors, lighter rims, see asteroid_shape.py). The mesh is lit face by face
(or corner by corner, for a smooth round one) by the star, with the same ambient light as the rocks (`shade`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from galaxies.asteroid_class import class_of
from .asteroid_shape import AsteroidMesh, smooth_noise
from .constants import SURFACE_STARLIGHT

Colour = tuple[float, float, float]


COLOURS = {  # by class name
    'carbonaceous': (80.0, 75.0, 72.0),
    'stony': (140.0, 118.0, 96.0),
    'metallic': (122.0, 120.0, 116.0),
    'basaltic': (168.0, 154.0, 136.0),
}
VARIANTS = ((0.10, 2.0), (0.18, 3.5), (0.28, 6.0))  # (patchiness, spatial frequency) of the surface colour
TINT_JITTER = 0.06  # the colour of each asteroid differs a little from its class's
FINE_SHARE = 0.5  # the weight of the fine mottling against the broad patches


@dataclass(frozen=True)
class Look:
    """What an asteroid looks like: a class, a variant and its own colour."""
    name: str
    colour: Colour
    patchiness: float
    frequency: float


def look_of(seed: int) -> Look:
    """The look of the asteroid of this seed: its class (`class_of`), a variant and a small tint."""
    asteroid_class = class_of(seed)
    rng = np.random.default_rng([seed, 8])
    variant = int(rng.integers(len(VARIANTS)))
    patchiness, frequency = VARIANTS[variant]
    tint = 1.0 + TINT_JITTER * (rng.random(3) - 0.5)
    colour = tuple(float(value) for value in np.array(COLOURS[asteroid_class.name]) * tint)
    return Look(f"{asteroid_class.name} {variant + 1}", colour, patchiness, frequency)


def corner_colours(mesh: AsteroidMesh, look: Look, seed: int) -> np.ndarray:
    """The colour (float, 0 to 255) at each corner of each face, before the sun: the look's colour, varied by patches
    of the surface and by the mesh's tones. (faces, 3, 3)."""
    rng = np.random.default_rng([seed, 9])
    broad = smooth_noise(mesh.centres, rng, 8, look.frequency, look.frequency * 2.5)
    fine = smooth_noise(mesh.centres, rng, 8, look.frequency * 4.0, look.frequency * 10.0)
    factor = 1.0 + look.patchiness * (broad + FINE_SHARE * fine)
    return np.array(look.colour) * factor[:, None, None] * mesh.tones[..., None]


def shade(colours: np.ndarray, normals: np.ndarray, sun: np.ndarray) -> np.ndarray:
    """The colours lit by the sun (a unit vector, from the asteroid to the star), as uint8 values, one row per corner
    (faces * 3, 3): the ambient starlight plus the part that faces the sun, as SurfaceLight.brightness does."""
    facing = normals @ sun
    brightness = SURFACE_STARLIGHT + (1.0 - SURFACE_STARLIGHT) * np.maximum(0.0, facing)
    return np.ascontiguousarray(np.clip(colours * brightness[..., None], 0.0, 255.0).reshape(-1, 3), dtype=np.uint8)
