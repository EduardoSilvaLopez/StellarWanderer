"""The class of an asteroid, as the real ones are sorted by their spectra: what it is made of, how much of the light it
reflects and how dense it is. The class is a function of the asteroid's seed, with the shares of the main belt, so the
same asteroid is always of the same class. The graphics give each class its colour (graphics/asteroid_looks.py) and the
knowledge base shows it (`Asteroid.markdown`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AsteroidClass:
    name: str
    share: float  # of the asteroids
    reflectance: float  # of the light it receives (the real values are the albedos of these classes)
    density: float  # kg/m3, bulk: a rubble pile is less dense than the rock it is made of


CLASSES = (
    AsteroidClass('carbonaceous', 0.72, 0.05, 1300.0),
    AsteroidClass('stony', 0.17, 0.20, 2700.0),
    AsteroidClass('metallic', 0.08, 0.15, 4500.0),
    AsteroidClass('basaltic', 0.03, 0.40, 3400.0),
)


def class_of(seed: int) -> AsteroidClass:
    """The class of the asteroid of this seed."""
    pick = float(np.random.default_rng([seed, 7]).random())
    for asteroid_class in CLASSES:
        if pick < asteroid_class.share:
            return asteroid_class
        pick -= asteroid_class.share
    return CLASSES[-1]
