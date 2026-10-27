"""The roles of the staff of a settlement (galaxies/settlement.py says which roles it has, and how many teams of each).

A role is data only: what depends on the role and not on the settlement. The teams, the rota, the substitute and the
people themselves belong to the settlement. A role with shifts takes one member for each 8-hour shift, and the member
after them is the substitute, on duty when a shift member is on leave (`vacation` is the chance of that). A role with
one shift and no vacation is on duty all the time.
"""

from __future__ import annotations
from dataclasses import dataclass

STAFF_AGE_MIN = 25  # the age range of the staff; a role raises it with `age_raise`
STAFF_AGE_MAX = 60


@dataclass(frozen=True)
class Role:
    seed_kind: str  # the kind in the seed of each member (seeds.derive): it stays the same, whatever the title
    name: str  # the title, as shown to the player
    shifts: int  # 8-hour shifts; 1 means on duty all the time
    vacation: float  # the chance that the substitute is on duty instead of a shift member
    age_raise: int = 0  # years added to both ends of the age range
    reputation_bonus: float = 0.0  # added to the reputation of each person if positive, multiplied if negative
    loyalty_bonus: float = 0.0  # added to the loyalty of each person.
    portrait: str = 'uniform'  # the part of the portrait file names (common/resources/portraits) that the role uses


# The seed kind is still 'person', as before the roles: the communication officers are the same people as in the saves.
COM_OFFICER = Role(
    'person',
    'Communication Officer',
    reputation_bonus=5,
    loyalty_bonus=5,
    shifts=3,
    vacation=0.33,
    )
DOCKMASTER = Role(
    'outpost_dockmaster',
    'Dockmaster',
    reputation_bonus=10,
    loyalty_bonus=-10,
    shifts=3,
    vacation=0.33,
    )
GUNNER = Role(
    'gunner',
    'Gunner',
    age_raise=-2,
    loyalty_bonus=10,
    shifts=3,
    vacation=0.0,
    )
JANITOR = Role(
    'janitor',
    'Janitor',
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )
SECURITY = Role(
    'security',
    'Security',
    age_raise=-2,
    reputation_bonus=5,
    loyalty_bonus=5,
    shifts=3,
    vacation=0.33,
    )
STEVEDORE = Role(
    'stevedore',
    'Stevedore',
    reputation_bonus=-0.8,
    loyalty_bonus=-5,
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )

# Leaders are always available but work when they please.
COORDINATOR = Role(
    'outpost_coordinator',
    'Coordinator',
    age_raise=10,
    reputation_bonus=100.0,
    loyalty_bonus=5,
    shifts=1,
    vacation=0.0,
    )
KOMISAR = Role(
    'komisar',
    'Komisar',
    age_raise=5,
    reputation_bonus=50.0,
    loyalty_bonus=50,
    shifts=1,
    vacation=0.0,
    portrait="hydroponic",
    )
RINGMASTER = Role(
    'ringmaster',
    'Ringmaster',
    age_raise=10,
    reputation_bonus=2000.0,
    loyalty_bonus=25,
    shifts=1,
    vacation=0.0,
    portrait="hydroponic",
    )
