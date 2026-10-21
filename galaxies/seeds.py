"""The seeds: every generated object draws its values from its own `random.Random(seed)`, and its seed is derived from its
parent's, so a given galaxy seed always gives the same universe whatever the order the player visits it in.

    seed = derive(parent.seed, kind, *keys)

where `keys` place the child in its parent. The chain, from the galaxy seed given by the user (the only float):

    galaxy -> quadrant -> district -> sector -> star -> stellar system -> orbit -> planet -> moon
                                                                  \\-> (planet) -> outpost -> staff member
    planet or moon -> Km2 -> rock, ore field
    asteroid belt (an orbit) -> sector of a tier and epoch -> its asteroids (drawn together); a relevant asteroid ->
    orbit (see asteroid_belt.py)

Quadrants (QUADRANT_SIZE ly) and districts (DISTRICT_SIZE ly) only feed the seed for now (see fixed_stars.py): when they
are used for generation later, the seeds of everything already generated stay the same. The keys of a region are its
absolute indices, not the indices within its parent.

Each object draws in a fixed order, and a new draw goes last, so earlier values do not change.
"""

import hashlib


def of_text(text: str) -> int:
    """A seed for a text: the first 8 bytes of its sha256. The same text gives the same seed in every run (unlike hash())."""
    return int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest()[:8], 'big')


def derive(parent_seed: int | float, kind: str, *keys: int | float | str) -> int:
    """The seed of a child: its parent's seed, its kind and the keys that place it in its parent."""
    return of_text('|'.join([repr(parent_seed), kind, *(repr(key) for key in keys)]))
