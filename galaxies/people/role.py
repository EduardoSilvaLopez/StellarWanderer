"""The roles of the staff of a settlement (galaxies/settlement.py says which roles it has, and how many teams of each).

A role is data only: what depends on the role and not on the settlement. The teams, the rota, the substitute and the
people themselves belong to the settlement (see people/staffing.py). A role with shifts takes one member for each 8-hour
shift, and one more is the substitute, on duty when a shift member is on leave (`vacation` is the chance of that). A
role with one shift and no vacation is on duty all the time.

A person gets the role's traits once, when hired (see Person): a later change of role does not change them.
"""

from __future__ import annotations
from dataclasses import dataclass

STAFF_AGE_MIN = 25  # the age range of the staff when hired; a role raises it with `age_raise`
STAFF_AGE_MAX = 60
RETIREMENT_AGE_MIN = 65  # the age range of the retirement; a positive `age_raise` raises it too, so a leader hired at
RETIREMENT_AGE_MAX = 70  # the top of the hiring range never retires at once


@dataclass(frozen=True)
class Role:
    seed_kind: str  # the kind in the seeds of the role's vacation draws (seeds.derive), whatever the title
    name: str  # the title, as shown to the player
    shifts: int  # 8-hour shifts; 1 means on duty all the time
    vacation: float  # the chance that the substitute is on duty instead of a shift member
    ideal_for: tuple # Ideal for loyalty, empathy, sociability.
    personality_bonus: tuple  # Added to loyalty, empathy, sociability.
    age_raise: int = 0  # years added to both ends of the age range
    reputation_bonus: float = 0.0  # added to the reputation of each person if positive, multiplied if negative
    portrait: str = 'uniform'  # the part of the portrait file names (common/resources/portraits) that the role uses

    @property
    def team_size(self) -> int:
        """The members of one team: its shift members, and the substitute if the role has any vacation."""
        return self.shifts + (1 if self.vacation > 0 else 0)


COM_OFFICER = Role(
    'person',
    'Communication Officer',
    reputation_bonus=5,
    personality_bonus=(5, 5, 5),  #loy, emp, soc
    ideal_for=(60, 50, 60),
    shifts=3,
    vacation=0.33,
    )
DOCKMASTER = Role(
    'outpost_dockmaster',
    'Dockmaster',
    reputation_bonus=10,
    personality_bonus=(-5, -5, -5),  #loy, emp, soc
    ideal_for=(65, 45, 50),
    shifts=3,
    vacation=0.33,
    )
BUREAUCRAT = Role(
    'bureaucrat',
    'Bureaucrat',
    reputation_bonus=10,
    personality_bonus=(0, -10, 10),  #loy, emp, soc
    ideal_for=(50, 45, 55),
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )
ENGINEER = Role(
    'engineer',
    'Engineer',
    reputation_bonus=5,
    personality_bonus=(0, 0, 0),  #loy, emp, soc
    ideal_for=(50, 50, 50),
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )
GUNNER = Role(
    'gunner',
    'Gunner',
    age_raise=-2,
    personality_bonus=(10, -10, -10),  #loy, emp, soc
    ideal_for=(70, 30, 30),
    shifts=3,
    vacation=0.0,
    )
JANITOR = Role(
    'janitor',
    'Janitor',
    personality_bonus=(0, -5, -5),  #loy, emp, soc
    ideal_for=(30, 20, 30),
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )
RESEARCHER = Role(
    'researcher',
    'Researcher',
    age_raise=10,
    reputation_bonus=100,
    personality_bonus=(5, -10, -10),  #loy, emp, soc
    ideal_for=(50, 45, 40),
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )
SECURITY = Role(
    'security',
    'Security',
    age_raise=-2,
    reputation_bonus=5,
    personality_bonus=(5, 0, 0),  #loy, emp, soc
    ideal_for=(60, 45, 50),
    shifts=3,
    vacation=0.33,
    )
SMITH = Role(
    'smith',
    'Smith',
    age_raise=0,
    reputation_bonus=-5,
    personality_bonus=(-5, -5, -10),  #loy, emp, soc
    ideal_for=(40, 40, 20),
    shifts=3,
    vacation=0.33,
    portrait="hydroponic",
    )
STEVEDORE = Role(
    'stevedore',
    'Stevedore',
    reputation_bonus=-0.8,
    personality_bonus=(-5, -10, 0),  #loy, emp, soc
    ideal_for=(30, 30, 30),
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
    personality_bonus=(10, 0, 5),  #loy, emp, soc
    ideal_for=(70, 50, 60),
    shifts=1,
    vacation=0.0,
    )
KOMISAR = Role(
    'komisar',
    'Komisar',
    age_raise=5,
    reputation_bonus=50.0,
    personality_bonus=(40, 10, 20),  #loy, emp, soc
    ideal_for=(80, 50, 80),
    shifts=1,
    vacation=0.0,
    portrait="hydroponic",
    )
CAPTAIN = Role(
    'chief_captain',
    'Captain',
    age_raise=10,
    reputation_bonus=50,
    personality_bonus=(10, 0, 5),  #loy, emp, soc
    ideal_for=(65, 45, 60),
    shifts=1,
    vacation=0.0,
    )
RINGMASTER = Role(
    'ringmaster',
    'Ringmaster',
    age_raise=10,
    reputation_bonus=2000.0,
    personality_bonus=(20, 10, 20),  #loy, emp, soc
    ideal_for=(90, 40, 65),
    shifts=1,
    vacation=0.0,
    portrait="hydroponic",
    )
