"""The sun's flares, in game time.

Flares are scheduled on the game clock: each slot of FLARE_SLOT_SECONDS of game time may hold one flare, decided by the
star's seed, so the sun behaves the same whatever the frame rate or the time scale. A flare rises over
FLARE_RISE_SECONDS of game time and decays over FLARE_DECAY_SECONDS. Above FLARE_MAX_TIME_SCALE flares are not drawn
(graphics/star_gl.py): at high time compression a flare would last a few frames and flicker.
"""

from __future__ import annotations
import math
import random
from typing import List, Tuple
from .constants import FLARE_SLOT_SECONDS, FLARE_CHANCE, FLARE_RISE_SECONDS, FLARE_DECAY_SECONDS

FLARE_MIN_SHAPE = 0.01  # a flare fainter than this is not drawn


def _random(star_seed: int, salt: int) -> random.Random:
    """A generator that depends only on the star's seed and `salt`, so the same slot always gives the same flare."""
    return random.Random(int(star_seed * 1000) * 1000003 + salt)


def flares_active(star_seed: int, game_seconds: float) -> List[Tuple[float, float]]:
    """(longitude, intensity from 0 to 1) of each flare visible at `game_seconds` (game time since EPOCH). The longitude
    is in radians from the centre of the disc, positive to the right."""
    slot = int(math.floor(game_seconds / FLARE_SLOT_SECONDS))
    active = []
    for index in (slot - 1, slot):  # a flare starting in the last slot may still be decaying
        rnd = _random(star_seed, index)
        if rnd.random() >= FLARE_CHANCE:
            continue
        start = index * FLARE_SLOT_SECONDS + rnd.random() * FLARE_SLOT_SECONDS
        amplitude = 0.4 + 0.6 * rnd.random()
        longitude = rnd.uniform(-math.pi / 2, math.pi / 2)
        age = game_seconds - start
        if age < 0:
            continue
        if age < FLARE_RISE_SECONDS:
            shape = age / FLARE_RISE_SECONDS
        else:
            shape = math.exp(-(age - FLARE_RISE_SECONDS) / FLARE_DECAY_SECONDS)
        if shape > FLARE_MIN_SHAPE:
            active.append((longitude, amplitude * shape))
    return active
