"""What the pilot says about themselves at the start of a new game (PilotIdentityDialog). The sliders run from 0 to 100:
physiology and attraction both from extreme female (0) to extreme male (100)."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

from galaxies.people.person import Person


@dataclass
class PilotIdentity:
    """The values the dialog gives: the date of birth is (year, month, day). Beauty, perception and education add up
    to a fixed total (see PilotIdentityDialog)."""

    first_name: str
    surname: str
    date_of_birth: Tuple[int, int, int]
    beauty: float
    perception: float
    education: float
    pronoun: Optional[Person.Pronoun]
    physiology: float
    attracted_to: float
    sexuality: float
