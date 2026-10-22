"""The roles of the staff of an outpost (see galaxies/outpost.py for who holds them, and how many).

A role is data only: what depends on the role and not on the outpost. The rota, the substitute and the people themselves
belong to the outpost. A role with shifts takes one member for each 8-hour shift, and the member after them is the
substitute, on duty when a shift member is on leave (`vacation` is the chance of that). A role with one shift and no
vacation is on duty all the time.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

STAFF_AGE_MIN = 25  # the age range of the staff; a role raises it with `age_raise`
STAFF_AGE_MAX = 60


@dataclass(frozen=True)
class Role:
    seed_kind: str  # the kind in the seed of each member (seeds.derive): it stays the same, whatever the title
    name: str  # the title, as shown to the player
    shifts: int  # 8-hour shifts; 1 means on duty all the time
    vacation: float  # the chance that the substitute is on duty instead of a shift member
    age_raise: int = 0  # years added to both ends of the age range
    reputation_bonus: float = 0.0  # added to the reputation of each member
    save_key: Optional[str] = None  # the key of the member on duty in a save; None when nothing is saved

    @property
    def headcount(self) -> int:
        """The members of the role in an outpost: one for each shift, and the substitute if there is vacation."""
        return self.shifts + (1 if self.vacation > 0 else 0)


# The seed kind is still 'person', as before the roles: the communication officers are the same people as in the saves.
COM_OFFICER = Role('person', 'Communication Officer', shifts=3, vacation=0.33, save_key='com_officer_on_duty')
DOCKMASTER = Role('outpost_dockmaster', 'Dockmaster', shifts=3, vacation=0.33, save_key='dockmaster_on_duty')
# Works all the time: when, and whether, he works is for the conversations to decide.
COORDINATOR = Role('outpost_coordinator', 'Coordinator', shifts=1, vacation=0.0, age_raise=10,
                   reputation_bonus=100.0)
ROLES = (COM_OFFICER, DOCKMASTER, COORDINATOR)
