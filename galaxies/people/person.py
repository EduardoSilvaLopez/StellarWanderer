from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from functools import cache
import logging
import os
import random
from typing import TYPE_CHECKING, Any, Optional, Tuple

import pygame

from galaxies.politics import political_entity
import game_environment as gem
from common.paths import resource_path

if TYPE_CHECKING:
    from galaxies.people.player import Player

PEOPLE_DIR = resource_path('people')

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


class Person:
    class Race(Enum):
        ASIAN = 1
        BLACK = 2
        WHITE = 3

    class GenderGroup(Enum):  # aesthetically speaking, identification can be done later.
        MALE = 1
        FEMALE = 2

    def __init__(self, seed: float, residency: Any, social_factor: float, age_min: int = 15, age_max: int = 70) -> None:
        my_random = random.Random(seed)
        self.seed: float = seed

        self.race: Person.Race = Person.Race.ASIAN
        rnd: float = my_random.random()
        if rnd > 0.9:
            self.race = Person.Race.BLACK
        elif rnd > 0.6:
            self.race = Person.Race.WHITE

        self.gender_group = Person.GenderGroup.MALE
        rnd = my_random.random()
        if rnd > 0.55:  # sue me :D
            self.gender_group = Person.GenderGroup.FEMALE

        # All these can change later: mixed heritage, gender-fluid...
        language = 'chinese' if self.race == Person.Race.ASIAN else 'english'
        gender = self.gender_group.name.lower()

        self.name: str = _pick_name(my_random, f'{language}_{gender}_names.txt')
        self.surname: str = _pick_name(my_random, f'{language}_{gender}_surnames.txt')
        self.reputation: float = 5 * social_factor * my_random.gauss(1.0, 0.3)

        self.empathy100: float = my_random.random() * 100
        self.sociability100: float = my_random.random() * 100
        self.loyalty100: float = my_random.random() * 100
        self._adjust_loyalty(self.reputation - 5)
        self.sympathy100: float = 50.0

        seconds_after_birth: float = (my_random.random() * (age_max - age_min) + age_min) * 365.2425 * 24 * 60 * 60
        self.dob = gem.current_environment.date_time + timedelta(seconds=-seconds_after_birth)

        self.residency: Any = residency
        self.last_communication_at: Optional[datetime] = None

        self.icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self.portrait = self._load_portrait(my_random)

        self.interactions: dict = {}
        # Where the player first talked to this person, e.g. "Consequential Task, planet Iuief, Aqakhaceia System"
        # (see meet). None until then, also for a person already in `persons` (see ensure).
        self.first_met_at: Optional[str] = None
        self.comment: str = ''  # what the player wrote about this person (see set_comment)
        if self.seed in gem.current_environment.persons:
            # Apply alterations.
            my_alterations = gem.current_environment.persons[self.seed]
            self.first_met_at = my_alterations['first_met_at']
            self.comment = my_alterations.get('comment', '')
            if 'last_communication_at' in my_alterations and my_alterations.get('last_communication_at'):
                self.last_communication_at = datetime.fromisoformat(my_alterations['last_communication_at'])
            if 'sympathy' in my_alterations:
                self.sympathy100 = my_alterations['sympathy']
            if 'interactions' in my_alterations:
                for dt_str, lines in my_alterations['interactions'].items():
                    dt = datetime.fromisoformat(dt_str)
                    self.interactions[dt] = lines
            self.log_update()

    def _load_portrait(self, my_random: random.Random) -> Optional[str]:
        age: int = int((gem.current_environment.date_time - self.dob).total_seconds() / (365.2425 * 24 * 60 * 60))
        age_group: str = 'young' if age < 30\
            else 'adult' if age < 45\
            else 'mature' if age < 65\
            else 'old'

        from galaxies.outpost import Outpost
        occupation: str = 'outpost.com' if isinstance(self.residency, Outpost)\
            else 'generic'

        filename_prefix: str = occupation + "." + str(self.race.name).lower() + "." + age_group + "." + str(self.gender_group.name).lower()
        portraits_dir = resource_path('portraits')
        try:
            names = os.listdir(portraits_dir)
        except OSError:
            names = []

        # Sorted, so the same seed always picks the same portrait whatever order the OS lists the files in.
        candidates = sorted(name for name in names if name.startswith(filename_prefix))
        if not candidates:
            print(f"Warning: No person portrait starting with {filename_prefix} in {portraits_dir}")
            return None
        filename: str = my_random.choice(candidates)

        icon_path = os.path.join(portraits_dir, filename)
        try:
            self.icon = pygame.image.load(icon_path)
        except Exception as e:
            print(f"Warning: Could not load person entity icon {filename}: {e}")
            return None

        return icon_path

    def description_fields(self) -> list[tuple[str, str]]:
        """The person's characteristics as (label, value): what the log and the people dialog show. The label is empty
        for the gender and race, which are shown as a plain line."""
        age: int = int((gem.current_environment.date_time - self.dob).total_seconds() / (365.2425 * 24 * 60 * 60))
        last_time_met: Optional[datetime] = next(reversed(self.interactions.keys()), None)
        ltm_str = last_time_met.strftime('%Y-%m-%d') if last_time_met else "Not met yet" if self.first_met_at is None else "Don't remember."
        result: list[tuple[str, str]] = [
            ('ID', f"{self.seed}."),
            ('', f"{self.gender_group.name.capitalize()}, {self.race.name.capitalize()}"),
            ('D.O.B.', f"{self.dob.strftime('%Y-%m-%d')} ({age} y.o.)"),
            ('Last time met', f"{ltm_str}"),
        ]

        from galaxies.outpost import Outpost
        if isinstance(self.residency, Outpost):
            result.append((
                'Residency',
                f"Outpost {self.residency.name}, planet {self.residency.planet.name}"
                f", {self.residency.planet.parent_orbit.parent_stellar_system.name}"
            ))
        return result

    def log_update(self) -> Person:
        """Logs the person's characteristics, one ' - ' line each."""
        description = ''.join(f" - {label}: {value}\n" if label else f" - {value}\n" for label, value in self.description_fields())
        logger.info(
            f"PERSON UPDATE: {self.get_full_name()}"
            f"\n{description}"
            f"\n - Sympathy: {self.sympathy100}" # Not told to player.
            )
        return self

    def serialize(self) -> dict:
        interactions_dict: dict = {
            int_date_time.strftime("%Y-%m-%d %H:%M:%S"): int_lines for int_date_time, int_lines in self.interactions.items()
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

    def set_comment(self, text: str) -> Person:
        """The player's comment on this person, saved with the person (in `persons`) at once."""
        self.comment = text
        return self.ensure()

    def ensure(self) -> Person:
        """Writes this person into `persons` as they are now: makes the record, or updates it. Call it after anything about
        the person changes. A person the player has not met is kept too, with `first_met_at` None (`meet` fills it in)."""
        gem.current_environment.persons[self.seed] = self.serialize()
        return self

    def meet(self) -> Person:
        """The player talks to this person (a Conversation starts): from now on they are in `persons`, with the place
        they were first met at, which is written once. For now the residence is always an outpost (on a planet, or a moon
        with its planet): a person with any other residence has no place yet."""
        if self.first_met_at is None:
            from galaxies.outpost import Outpost
            self.first_met_at = self.residency.address() if isinstance(self.residency, Outpost) else ''
            self.ensure()
        return self

    def get_player_title(self, player: Player) -> str:
        value_adjusted = player.those_who_share.reputation * (self.sympathy100 * 2) / 100
        return political_entity.THOSE_WHO_SHARE.title_for(value_adjusted)

    def get_title(self) -> str:
        # Find out where this person is... as for now, guess Those-Who-Share
        return political_entity.THOSE_WHO_SHARE.title_for(self.reputation)

    def get_full_name(self) -> str:
        return f"{self.get_title()} {self.name} {self.surname}"  # No Chinese exception. Intentional.

    # 'Personality' traits change slower the more they approach the extremes of 0 and 100
    def _adjust_loyalty(self, change: float) -> Person:
        self.loyalty100 += change / (1 + abs(self.loyalty100 - 50))
        self.loyalty100 = max(0, min(100, self.loyalty100))

    def adjust_sympathy(self, change: float) -> Person:
        """Changes the sympathy and saves it (see ensure)."""
        self.sympathy100 += change / (1 + abs(self.sympathy100 - 50))
        self.sympathy100 = max(0, min(100, self.sympathy100))
        return self.ensure()
