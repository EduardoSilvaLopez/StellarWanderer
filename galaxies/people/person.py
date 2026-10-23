from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from functools import cache
import logging
import os
import random
from typing import Any, Optional, Tuple

import pygame

from galaxies.politics import political_entity
from galaxies.people.role import Role
import game_environment as gem
from common.paths import resource_path

PEOPLE_DIR = resource_path('people')
SECONDS_PER_YEAR = 365.2425 * 24 * 60 * 60

logger = logging.getLogger(__name__)


@cache
def _read_names(file_name: str) -> Tuple[str, ...]:
    """The non-empty lines of common/resources/people/<file_name>, read once. A missing file gives no names."""
    try:
        with open(os.path.join(PEOPLE_DIR, file_name), encoding='utf-8') as file:
            return tuple(line.strip() for line in file if line.strip())
    except OSError as e:
        print(f"Warning: Could not read person names from {file_name}: {e}")
        return ()


def _pick_name(my_random: random.Random, file_name: str) -> str:
    names = _read_names(file_name)
    return my_random.choice(names) if names else ''


def _nudged(value: float, change: float) -> float:
    """A 'personality' trait (0 to 100) after `change`: it moves slower the nearer it is to the extremes."""
    return max(0, min(100, value + change / (1 + abs(value - 50))))


class Person:
    class Race(Enum):
        ASIAN = 1
        BLACK = 2
        WHITE = 3
        LATIN = 4

    class GenderGroup(Enum):  # aesthetically speaking, identification can be done later.
        MALE = 1
        FEMALE = 2

    # region Generation
    def __init__(self, seed: int, residency: Any, social_factor: float, role: Role, age_min: int = 15,
                 age_max: int = 70) -> None:
        my_random = random.Random(seed)
        self.seed: int = seed
        self.role: Role = role

        self.race: Person.Race = Person.Race.ASIAN
        rnd: float = my_random.random()
        if rnd > 0.93:
            self.race = Person.Race.BLACK
        elif rnd > 0.82:
            self.race = Person.Race.LATIN
        elif rnd > 0.53:
            self.race = Person.Race.WHITE

        self.gender_group = Person.GenderGroup.MALE
        rnd = my_random.random()
        if rnd > 0.55:  # sue me :D
            self.gender_group = Person.GenderGroup.FEMALE

        # All these can change later: mixed heritage, gender-fluid, french, german
        language = 'chinese' if self.race == Person.Race.ASIAN \
            else 'english' if self.race in (Person.Race.WHITE, Person.Race.BLACK) \
            else 'spanish'
        gender = self.gender_group.name.lower()

        self.name: str = _pick_name(my_random, f'{language}_{gender}_names.txt')
        self.surname: str = _pick_name(my_random, f'{language}_{gender}_surnames.txt')
        self.reputation: float = 5 * social_factor * my_random.gauss(1.0, 0.3) + role.reputation_bonus

        self.empathy100: float = my_random.random() * 100
        self.sociability100: float = my_random.random() * 100
        self.loyalty100: float = my_random.random() * 100
        self.loyalty100 = _nudged(self.loyalty100, self.reputation - 5)
        self.sympathy100: float = 50.0

        seconds_after_birth: float = (my_random.random() * (age_max - age_min) + age_min) * 365.2425 * 24 * 60 * 60
        self.dob = gem.current_environment.date_time + timedelta(seconds=-seconds_after_birth)

        self.residency: Any = residency
        self.last_communication_at: Optional[datetime] = None

        self.icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self._load_icon(my_random)

        self.interactions: dict = {}
        # Where the player first talked to this person, e.g. "Consequential Task, planet Iuief, Aqakhaceia System"
        # (see meet). None until then, also for a person already in `persons` (see record).
        self.first_met_at: Optional[str] = None
        self.comment: str = ''  # what the player wrote about this person (see set_comment)
        if self.seed in gem.current_environment.persons:
            # Apply alterations.
            my_alterations = gem.current_environment.persons[self.seed]
            self.first_met_at = my_alterations['first_met_at']
            self.comment = my_alterations.get('comment', '')
            if my_alterations.get('last_communication_at'):
                self.last_communication_at = datetime.fromisoformat(my_alterations['last_communication_at'])
            if 'sympathy' in my_alterations:
                self.sympathy100 = my_alterations['sympathy']
            if 'interactions' in my_alterations:
                for dt_str, lines in my_alterations['interactions'].items():
                    dt = datetime.fromisoformat(dt_str)
                    self.interactions[dt] = lines
            self.log_description()

    def _load_icon(self, my_random: random.Random) -> None:
        """The portrait, into `icon`: one of the pictures for the person's occupation, race, age and gender, by the
        seed."""
        age_group: str = 'young' if self.age < 30\
            else 'adult' if self.age < 45\
            else 'mature' if self.age < 65\
            else 'old'

        from galaxies.outpost import Outpost
        occupation: str = 'outpost' if isinstance(self.residency, Outpost)\
            else 'generic'

        filename_prefix: str = (occupation + "." + str(self.race.name).lower() + "." + age_group + "."
                                + str(self.gender_group.name).lower())
        portraits_dir = resource_path('portraits')
        try:
            names = os.listdir(portraits_dir)
        except OSError:
            names = []

        # Sorted, so the same seed always picks the same portrait whatever order the OS lists the files in.
        candidates = sorted(name for name in names if name.startswith(filename_prefix))
        if not candidates:
            print(f"Warning: No person portrait starting with {filename_prefix} in {portraits_dir}")
            return
        filename: str = my_random.choice(candidates)

        icon_path = os.path.join(portraits_dir, filename)
        try:
            self.icon = pygame.image.load(icon_path)
        except Exception as e:
            print(f"Warning: Could not load person entity icon {filename}: {e}")
    # endregion

    # region Description
    @property
    def age(self) -> int:
        """Whole years since the date of birth, at the game's date."""
        return int((gem.current_environment.date_time - self.dob).total_seconds() / SECONDS_PER_YEAR)

    def last_time_met_text(self) -> str:
        """When the player last talked to this person: the date, else "Not met yet" or "Don't remember."."""
        last_time_met: Optional[datetime] = next(reversed(self.interactions.keys()), None)
        if last_time_met:
            return last_time_met.strftime('%Y-%m-%d')
        return "Not met yet" if self.first_met_at is None else "Don't remember."

    def description_fields(self) -> list[tuple[str, str]]:
        """The person's characteristics as (label, value): what the log and the people dialog show. The label is empty
        for the gender and race, which are shown as a plain line."""
        result: list[tuple[str, str]] = [
            ('ID', f"{self.seed}."),
            ('', f"{self.gender_group.name.capitalize()}, {self.race.name.capitalize()}"),
            ('D.O.B.', f"{self.dob.strftime('%Y-%m-%d')} ({self.age} y.o.)"),
            ('Last time met', self.last_time_met_text()),
        ]

        from galaxies.outpost import Outpost
        if isinstance(self.residency, Outpost):
            result.append((
                'Residency',
                f"Outpost {self.residency.name}, planet {self.residency.planet.name}"
                f", {self.residency.planet.parent_orbit.parent_stellar_system.name}"
            ))
        return result

    def log_description(self) -> Person:
        """Logs the person's characteristics, one ' - ' line each."""
        description = ''.join(f" - {label}: {value}\n" if label else f" - {value}\n" for label,
                              value in self.description_fields())
        logger.info(
            f"PERSON UPDATE: {self.get_full_name()}"
            f"\n{description}"
            f"\n - Sympathy: {self.sympathy100}" # Not told to player.
            )
        return self

    def get_title(self) -> str:
        # Find out where this person is... as for now, guess Those-Who-Share
        return political_entity.THOSE_WHO_SHARE.title_for(self.reputation)

    def get_full_name(self) -> str:
        return f"{self.get_title()} {self.name} {self.surname}"  # No Chinese exception. Intentional.
    # endregion

    # region Record
    def serialize(self) -> dict:
        interactions_dict: dict = {
            int_date_time.strftime("%Y-%m-%d %H:%M:%S"): int_lines for int_date_time,
            int_lines in self.interactions.items()
        }

        result: dict = {'seed': self.seed, 'first_met_at': self.first_met_at}
        if self.comment:
            result['comment'] = self.comment
        if self.last_communication_at:
            result['last_communication_at'] = str(self.last_communication_at)
        result['sympathy'] = self.sympathy100
        if interactions_dict:
            result['interactions'] = interactions_dict

        return result

    def record(self) -> Person:
        """Writes this person into `persons` as they are now: makes the record, or updates it. Call it after anything
        about the person changes. A person the player has not met is kept too, with `first_met_at` None (`meet` fills it
        in)."""
        gem.current_environment.persons[self.seed] = self.serialize()
        return self

    def set_comment(self, text: str) -> Person:
        """The player's comment on this person, saved with the person (in `persons`) at once."""
        self.comment = text
        return self.record()

    def meet(self) -> Person:
        """The player talks to this person (a Conversation starts): from now on they are in `persons`, with the place
        they were first met at, which is written once. For now the residence is always an outpost (on a planet, or a
        moon with its planet): a person with any other residence has no place yet."""
        if self.first_met_at is None:
            from galaxies.outpost import Outpost
            self.first_met_at = self.residency.address() if isinstance(self.residency, Outpost) else ''
            self.record()
        return self

    def adjust_sympathy(self, change: float) -> Person:
        """Changes the sympathy and saves it (see record)."""
        self.sympathy100 = _nudged(self.sympathy100, change)
        logger.debug(f"Sympathy of {self.get_full_name()} changed to {self.sympathy100:.2f}")
        return self.record()
    # endregion
