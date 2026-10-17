from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
import logging
import os
import random
from typing import TYPE_CHECKING, Any, Optional, Tuple

import pygame

from common.game_logging import ALMANACK_IMAGE_WIDTH, append_person_almanack, relative_path_from_almanack
from galaxies.politics import political_entity
import game_environment as gem
from common.paths import resource_path

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.people.player import Player

PEOPLE_DIR = resource_path('people')

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
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
        self.sympathy_altered: bool = False

        seconds_after_birth: float = (my_random.random() * (age_max - age_min) + age_min) * 365.2425 * 24 * 60 * 60
        self.dob = gem.current_environment.date_time + timedelta(seconds=-seconds_after_birth)

        self.residency: Any = residency
        self.last_communication_at: Optional[datetime] = None

        self.icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self.portrait = self._load_portrait(my_random)

        self.interactions: dict = {}
        # Where the player first talked to this person, e.g. "Consequential Task, planet Iuief, Aqakhaceia System"
        # (see meet). None until then; a person is in `persons` only from that moment on.
        self.first_met_at: Optional[str] = None
        if self.seed in gem.current_environment.persons:
            # Apply alterations.
            my_alterations = gem.current_environment.persons[self.seed]
            self.first_met_at = my_alterations['first_met_at']
            if 'last_communication_at' in my_alterations and my_alterations.get('last_communication_at'):
                self.last_communication_at = datetime.fromisoformat(my_alterations['last_communication_at'])
            if 'sympathy' in my_alterations:
                self.sympathy100 = my_alterations['sympathy']
                self.sympathy_altered = True
            if 'interactions' in my_alterations:
                for dt_str, lines in my_alterations['interactions'].items():
                    dt = datetime.fromisoformat(dt_str)
                    self.interactions[dt] = lines

        self.log_update()
        append_person_almanack(self)

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
        """The person's characteristics as (label, value): what the log, the almanack and the people dialog show. The
        label is empty for the gender and race, which are shown as a plain line."""
        age: int = int((gem.current_environment.date_time - self.dob).total_seconds() / (365.2425 * 24 * 60 * 60))
        result: list[tuple[str, str]] = [
            ('ID', f"{self.seed}."),
            ('', f"{self.gender_group.name.capitalize()}, {self.race.name.capitalize()}"),
            ('D.O.B.', f"{self.dob.strftime('%Y-%m-%d')} ({age} y.o.)"),
            ('Reputation', f"{self.reputation:.2f}%"),
            ('Empathy', f"{self.empathy100:.2f}%"),
            ('Sociability', f"{self.sociability100:.2f}%"),
            ('Loyalty', f"{self.loyalty100:.2f}%"),
            ('Sympathy for the player', f"{self.sympathy100:.2f}%"),
        ]

        from galaxies.outpost import Outpost
        if isinstance(self.residency, Outpost):
            result.append((
                'Residency',
                f"Outpost {self.residency.name}, planet {self.residency.planet.name}"
                f", {self.residency.planet.parent_orbit.parent_stellar_system.name}"
            ))
        return result

    def _describe(self) -> str:
        """The person's characteristics, one ' - ' line each: what the log and the almanack show."""
        return ''.join(f" - {label}: {value}\n" if label else f" - {value}\n" for label, value in self.description_fields())

    def log_update(self) -> Person:
        logger.info(f"PERSON UPDATE: {self.get_full_name()}\n{self._describe()}")
        return self

    def almanack(self) -> str:
        """Markdown entry for the people's almanack: name, portrait (if any) and characteristics."""
        image = ''
        if self.portrait:
            image = f'<img src="{relative_path_from_almanack(self.portrait)}" width="{ALMANACK_IMAGE_WIDTH}">\n\n'
        return f"# {self.get_full_name()}\n\n{image}{self._describe()}\n"

    def serialize(self) -> dict:
        interactions_dict: dict = {
            int_date_time.strftime("%Y-%m-%d %H:%M:%S"): int_lines for int_date_time, int_lines in self.interactions.items()
        }

        result: dict = {'seed': self.seed, 'first_met_at': self.first_met_at}
        if self.last_communication_at:
            result['last_communication_at'] = str(self.last_communication_at)
        if self.sympathy_altered:
            result['sympathy'] = self.sympathy100
        if len(interactions_dict):
            result['interactions'] = interactions_dict

        return result

    def _place(self) -> str:
        """Where this person is: their residence with its moon (if any), planet and star system. For now the residence is
        always an outpost, on a planet; a person with any other residence has no place yet."""
        from galaxies.outpost import Outpost
        if not isinstance(self.residency, Outpost):
            return ''
        world = self.residency.planet
        place: str = f"{self.residency.name}, "
        if world.parent_planet:
            place += f"moon {world.name}, planet {world.parent_planet.name}"
        else:
            place += f"planet {world.name}"
        return f"{place}, {world.parent_orbit.parent_stellar_system.name}"

    def meet(self) -> Person:
        """The player talks to this person (a Conversation starts): from now on they are in `persons`, with the place
        they were first met at, which is written once."""
        if self.first_met_at is None:
            self.first_met_at = self._place()
            gem.current_environment.persons[self.seed] = self.serialize()
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
        self.sympathy100 += change / (1 + abs(self.sympathy100 - 50))
        self.sympathy100 = max(0, min(100, self.sympathy100))
        self.sympathy_altered = True

    def communicate_from(self, outpost: Outpost) -> Person:
        from .conversation import Conversation
        Conversation.generate(self)
