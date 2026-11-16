"""The surface of a world: its temperature, its type and its colour.

The temperature is the equilibrium temperature of an airless world at its distance from the star (a moon takes its
planet's distance). It picks the odds of each surface type; the seed picks the type and the colour, so the same world
always looks the same and nothing is saved. A world's colour is a mix, by WORLD_COLOUR_REALISM, of the realistic
colour of its type (the Moon, Mars, Io, Europa...) and a random vivid colour of the same brightness, then scaled a
little brighter or darker."""

from __future__ import annotations
import colorsys
import math
import random
from enum import Enum
from typing import Dict, Tuple, TYPE_CHECKING

from galaxies.constants import (
    WORLD_BOND_ALBEDO, WORLD_BRIGHTNESS_JITTER, WORLD_COLOUR_REALISM, WORLD_VIVID_SATURATION_MAX,
    WORLD_VIVID_SATURATION_MIN,
)

if TYPE_CHECKING:
    from galaxies.star import Star

Colour = Tuple[int, int, int]


class SurfaceType(Enum):
    """The kinds of surface a world can have: a name for the knowledge base, and the colour of the real thing."""
    BASALT = ('Dark basalt', (96, 92, 88))
    HIGHLAND = ('Grey highlands', (150, 147, 142))
    REGOLITH = ('Tan regolith', (160, 134, 104))
    RUST = ('Rust-red dust', (178, 106, 74))
    OCHRE = ('Sulphur ochre', (190, 168, 92))
    ICE = ('Ice', (196, 200, 208))

    def __init__(self, label: str, colour: Colour) -> None:
        self.label = label
        self.colour = colour


# The odds of each type by temperature: (the band's upper limit in K, the weights). The first band that the
# temperature is below applies. Cold worlds are icy or grey, hot ones dark, baked or sulphurous.
SURFACE_WEIGHTS: Tuple[Tuple[float, Dict[SurfaceType, int]], ...] = (
    (190.0, {SurfaceType.ICE: 35, SurfaceType.HIGHLAND: 25, SurfaceType.BASALT: 20, SurfaceType.REGOLITH: 15,
             SurfaceType.RUST: 5}),
    (300.0, {SurfaceType.HIGHLAND: 30, SurfaceType.BASALT: 25, SurfaceType.REGOLITH: 25, SurfaceType.RUST: 15,
             SurfaceType.ICE: 5}),
    (420.0, {SurfaceType.REGOLITH: 30, SurfaceType.RUST: 25, SurfaceType.BASALT: 25, SurfaceType.OCHRE: 10,
             SurfaceType.HIGHLAND: 10}),
    (math.inf, {SurfaceType.BASALT: 55, SurfaceType.OCHRE: 20, SurfaceType.REGOLITH: 15, SurfaceType.RUST: 10}),
)


def equilibrium_temperature(star: Star, distance: float, bond_albedo: float = WORLD_BOND_ALBEDO) -> float:
    """K: the temperature of a world `distance` m from the star, in balance with the light it takes in (it reflects
    `bond_albedo` of it and radiates the rest from its whole surface). The default albedo is an airless world's."""
    absorbed = star.luminosity * (1.0 - bond_albedo)
    return (absorbed / (16.0 * math.pi * star.STEFAN_BOLTZMANN * distance ** 2)) ** 0.25


def _luminance(colour: Tuple[float, float, float]) -> float:
    return 0.2126 * colour[0] + 0.7152 * colour[1] + 0.0722 * colour[2]


def generate_surface(my_random: random.Random, temperature: float) -> Tuple[SurfaceType, Colour]:
    """The type and the colour of a world at `temperature` K. Draws four values from `my_random`: the type, the
    vivid colour's hue and saturation, and the brightness."""
    weights = next(band for limit, band in SURFACE_WEIGHTS if temperature < limit)
    surface_type = my_random.choices(list(weights), weights=list(weights.values()))[0]
    return surface_type, vary_colour(my_random, surface_type.colour)


def vary_colour(my_random: random.Random, real_colour: Colour) -> Colour:
    """A colour near the realistic one: a mix, by WORLD_COLOUR_REALISM, of it and a random vivid colour of the same
    brightness, scaled a little brighter or darker. Draws three values from `my_random`: the vivid colour's hue and
    saturation, and the brightness."""
    vivid = colorsys.hsv_to_rgb(
        my_random.random(), my_random.uniform(WORLD_VIVID_SATURATION_MIN, WORLD_VIVID_SATURATION_MAX), 1.0
    )
    scale = _luminance(real_colour) / (255.0 * _luminance(vivid))
    jitter = 1.0 + my_random.uniform(-WORLD_BRIGHTNESS_JITTER, WORLD_BRIGHTNESS_JITTER)
    red, green, blue = (
        round(min(255.0, max(0.0, jitter * (
            WORLD_COLOUR_REALISM * real + (1.0 - WORLD_COLOUR_REALISM) * min(255.0, 255.0 * v * scale)
        ))))
        for real, v in zip(real_colour, vivid)
    )
    return red, green, blue
