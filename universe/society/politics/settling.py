"""How a settling system chooses the star it settles: a weighted random draw among the stars in reach.

The candidates are the stars within SETTLING_MAX_DISTANCE of the settling star, except itself (the stars of the sectors
that touch that sphere, from the star field). Each has a weight, the product of three factors:
- colour: a red dwarf (M) is discouraged, an orange star (K) half as much, the other types not at all (COLOUR_WEIGHT);
- direction: stars away from Sol are preferred. At the settling star, the angle between the hop and the direction from
  Sol through it gives a factor from 1 (straight away from Sol) down to AWAY_FROM_SOL_MIN (straight back toward it).
  Sol itself has no direction, so every star gets 1 from it;
- distance: exp(-d / SETTLING_REACH), so near stars are much more likely, and far ones keep a small weight.

The draw is random with weights, from the settling system's own generator. It can give a star that is already settled:
the caller then drops the settling. A sphere with no star at all gives None, and the settling does not happen. The
maximum distance is a hard limit: a star beyond it is never a candidate, however far the draw has to look.
"""

from __future__ import annotations

import math
import random
from typing import Optional

from universe.bodies.star import Star
from universe.structure.fixed_stars import StarField

SETTLING_MAX_DISTANCE = 20.0  # ly: no settling reaches farther
SETTLING_REACH = 10.0  # ly: the distance at which the weight of a candidate's distance falls to 1/e
AWAY_FROM_SOL_MIN = 0.05  # the direction factor of a star straight back toward Sol
COLOUR_WEIGHT: dict[Star.Type, float] = {Star.Type.M: 0.2, Star.Type.K: 0.6}  # the other types weigh 1


def colour_weight(star_type: Star.Type) -> float:
    return COLOUR_WEIGHT.get(star_type, 1.0)


def direction_weight(settling: tuple[float, float, float], sol: tuple[float, float, float],
                     candidate: tuple[float, float, float]) -> float:
    """The factor of a candidate by its direction from the settling star, seen from Sol: 1 straight away from Sol,
    AWAY_FROM_SOL_MIN straight back toward it, and 1 for the settling star when it is Sol itself."""
    away: tuple[float, ...] = tuple(s - o for s, o in zip(settling, sol))
    hop: tuple[float, ...] = tuple(c - s for c, s in zip(candidate, settling))
    away_length: float = math.hypot(*away)
    hop_length: float = math.hypot(*hop)
    if away_length == 0.0 or hop_length == 0.0:
        return 1.0
    cosine: float = sum(a * h for a, h in zip(away, hop)) / (away_length * hop_length)
    return AWAY_FROM_SOL_MIN + (1.0 - AWAY_FROM_SOL_MIN) * (1.0 + cosine) / 2.0


def candidate_weight(settling: Star, candidate: Star, sol_position: tuple[float, float, float]) -> float:
    """The weight of a candidate for the settling star: colour, direction and distance multiplied."""
    distance: float = math.dist(settling.position, candidate.position)
    return (colour_weight(candidate.type)
            * direction_weight(settling.position, sol_position, candidate.position)
            * math.exp(-distance / SETTLING_REACH))


def draw_candidate(field: StarField, settling: Star, sol_position: tuple[float, float, float],
                   my_random: random.Random) -> Optional[Star]:
    """The star the settling star settles, drawn by weight from the stars in reach (see the module docstring), or None
    when there is none. The result may already be settled: the caller decides."""
    candidates: list[Star] = [star for star in field.stars_within(settling.position, SETTLING_MAX_DISTANCE)
                              if star.cell != settling.cell]
    if not candidates:
        return None
    weights: list[float] = [candidate_weight(settling, star, sol_position) for star in candidates]
    return my_random.choices(candidates, weights=weights, k=1)[0]
