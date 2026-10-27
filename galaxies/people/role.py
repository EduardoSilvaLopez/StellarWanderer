"""The roles of the staff of an outpost (see galaxies/outpost.py for who holds them, and how many).

A role is data only: what depends on the role and not on the outpost. The rota, the substitute and the people themselves
belong to the outpost. A role with shifts takes one member for each 8-hour shift, and the member after them is the
substitute, on duty when a shift member is on leave (`vacation` is the chance of that). A role with one shift and no
vacation is on duty all the time.
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
    teams: int = 1  # how many teams work this role at once: each has its shift members and a substitute

    @property
    def headcount(self) -> int:
        """The members of the role in a settlement: each team's shifts, and its substitute if there is vacation."""
        return self.teams * (self.shifts + (1 if self.vacation > 0 else 0))


# The seed kind is still 'person', as before the roles: the communication officers are the same people as in the saves.
COM_OFFICER = Role(
    'person',
    'Communication Officer',
    shifts=3,
    vacation=0.33,
    reputation_bonus=5,
    loyalty_bonus=5,
    )
DOCKMASTER = Role(
    'outpost_dockmaster',
    'Dockmaster',
    shifts=3,
    vacation=0.33,
    reputation_bonus=10,
    loyalty_bonus=-10,
    )
GUNNER = Role(
    'gunner',
    'Gunner',
    shifts=3,
    vacation=0.0,
    loyalty_bonus=10,
    )
JANITOR = Role(
    'janitor',
    'Janitor',
    shifts=3,
    vacation=0.33,
    )
SECURITY = Role(
    'security',
    'Security',
    shifts=3,
    vacation=0.33,
    reputation_bonus=5,
    loyalty_bonus=5,
    )
STEVEDORE = Role(
    'stevedore',
    'Stevedore',
    shifts=3,
    vacation=0.33,
    teams=2,  # two teams work at once
    reputation_bonus=-0.8,
    loyalty_bonus=-5,
    )

# Leaders are always available but work when they please.
COORDINATOR = Role(
    'outpost_coordinator',
    'Coordinator',
    shifts=1,
    vacation=0.0,
    age_raise=10,
    reputation_bonus=100.0,
    loyalty_bonus=5,
    )
KOMISAR = Role(
    'komisar',
    'Komisar',
    shifts=1,
    vacation=0.0,
    age_raise=5,
    reputation_bonus=50.0,
    loyalty_bonus=50,
    )
RINGMASTER = Role(
    'ringmaster',
    'Ringmaster',
    shifts=1,
    vacation=0.0,
    age_raise=10,
    reputation_bonus=2000.0,
    loyalty_bonus=25,
    )

ROLES = (COM_OFFICER, DOCKMASTER, COORDINATOR)  # an outpost's staff
# the portal base's staff: the chief (Komisar) and the ring's master (Ringmaster) are on duty all the time
BASE_ROLES = (COM_OFFICER, DOCKMASTER, STEVEDORE, GUNNER, JANITOR, SECURITY, KOMISAR, RINGMASTER)
