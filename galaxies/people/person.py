from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from functools import cache
import logging
import math
import os
import random
from typing import TYPE_CHECKING, Any, Optional, Tuple

import pygame

if TYPE_CHECKING:
    from galaxies.people.player import Player
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

class Ethnicity(Enum):
    ASIAN = 1
    BLACK = 2
    WHITE = 3
    LATIN = 4

class Person:

    class GenderGroup(Enum):  # aesthetically speaking, identification can be done later.
        MALE = 1
        FEMALE = 2

    # region Generation
    def __init__(self, seed: int, residency: Any, social_factor: float, role: Role, age_min: int = 15,
                 age_max: int = 70) -> None:
        my_random = random.Random(seed)
        self.seed: int = seed
        self.role: Role = role

        self.race: Ethnicity = Ethnicity.ASIAN
        rnd: float = my_random.random()
        if rnd > 0.93:
            self.race = Ethnicity.BLACK
        elif rnd > 0.82:
            self.race = Ethnicity.LATIN
        elif rnd > 0.53:
            self.race = Ethnicity.WHITE

        self.gender_group = Person.GenderGroup.MALE
        rnd = my_random.random()
        if rnd > 0.55:  # sue me :D
            self.gender_group = Person.GenderGroup.FEMALE

        # All these can change later: mixed heritage, gender-fluid, french, german
        language = 'chinese' if self.race == Ethnicity.ASIAN \
            else 'english' if self.race in (Ethnicity.WHITE, Ethnicity.BLACK) \
            else 'spanish'
        gender = self.gender_group.name.lower()

        self.name: str = _pick_name(my_random, f'{language}_{gender}_names.txt')
        self.surname: str = _pick_name(my_random, f'{language}_{gender}_surnames.txt')
        if role.reputation_bonus >= 0:
            self.reputation: float = 5 * social_factor * my_random.gauss(1.0, 0.3) + role.reputation_bonus
        else:
            self.reputation: float = 5 * social_factor * my_random.gauss(1.0, 0.3) * -role.reputation_bonus

        self.empathy100: float = my_random.random() * 100
        self.sociability100: float = my_random.random() * 100

        self.loyalty100: float = my_random.random() * 100
        self.loyalty100 = _nudged(self.loyalty100, math.sqrt(self.reputation))
        self.loyalty100 = _nudged(self.loyalty100, role.loyalty_bonus)

        self.sympathy100: float = 50.0

        seconds_after_birth: float = (my_random.random() * (age_max - age_min) + age_min) * 365.2425 * 24 * 60 * 60
        self.dob: datetime = gem.current_environment.date_time + timedelta(seconds=-seconds_after_birth)
        self.planet_of_birth, self.place_of_birth = self._generate_place_of_birth(my_random)
        self.childhood: str = self._generate_childhood(my_random)
        self.hobby: str = self._generate_hobby(my_random)
        for _ in range(1, 10): # Space for further characteristics.
            my_random.random()

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

    def _generate_place_of_birth(self, my_random: random.Random) -> tuple:
        """Chooses a place of birth according to ethnicity, or just 'some place'."""
        matching: list[str] = [name for name, ethnicity in political_entity.THOSE_WHO_SHARE.settlements
                               if ethnicity == self.race]
        planet: str = my_random.choice(political_entity.THOSE_WHO_SHARE.planets)
        if matching and my_random.random() < 0.8:
            return planet, my_random.choice(matching)
        return planet, ('a small city' if my_random.random() < 2 / 3 else 'a town') + ", " + planet

    def _generate_childhood(self, my_random: random.Random) -> str:
        return my_random.choice((
            'a happy childhood',
            'a quiet childhood',
            'a lonely childhood',
            'a hard childhood',
            'a problematic childhood',
            'a sheltered childhood',
            'a hard but happy childhood',
            'a turbulent childhood',
            'a carefree childhood',
            'an uneventful childhood',
            'a strict, disciplined childhood',
            'a busy, tiring childhood',
            'a lively, noisy childhood',
            'a restless, curious childhood',
            'a difficult, unstable childhood',
            'a warm, loving childhood',
            'a cold, distant childhood',
            'a privileged, comfortable childhood',
            'a dull childhood',
        ))

    def _generate_hobby(self, my_random: random.Random) -> str:
        return my_random.choice((
            "I like to walk in the parks.",
            "I enjoy people-watching in the transit hubs. Don't tell anyone.",
            "I often visit the dome's botanical galleries.",
            "I like to try new foods in the market arcades.",
            "I spend time listening to street musicians.",
            "I enjoy reading old novels in the public lounges.",
            "I like to practice meditation under the dome lights.",
            "I enjoy attending small theater plays.",
            "I like to collect vintage printed magazines.",
            "I enjoy cooking with imported ingredients, you know, from the Throne. I know.",
            "I like to volunteer in community gardens.",
            "I enjoy playing board games with friends.",
            "I like to take long walks along the dome's perimeter paths.",
            "I enjoy watching the weather cycles. Those guys have some creativity in my place.",
            "I like to sketch the architecture.",
            "I enjoy visiting the art exhibits.",
            "I like to practice indoor climbing.",
            "I enjoy swimming in the municipal reservoirs.",
            "I enjoy watching PreDis movies.",
            "I like to fly micro-drones in the recreation halls.",
            "I enjoy tinkering with old household electronics.",
            "I like to explore PreDis virtual landscapes.",
            "I enjoy watching shuttle departures from the observation decks.",
            "I like to practice gravity aerobics when the gym offers it.",
            "I enjoy restoring antique star maps.",
            "I like to attend debate nights in the civic forum.",
            "I enjoy participating in collaborative mural projects.",
            "I like to join the weekly storytelling circles.",
            "I enjoy dancing during the dome's festival nights.",
            "I like to help organize neighborhood events.",
        ))

    def _load_icon(self, my_random: random.Random) -> None:
        """The portrait, into `icon`: one of the pictures for the person's occupation, race, age and gender, by the
        seed."""
        age_group: str = 'young' if self.age < 30\
            else 'adult' if self.age < 45\
            else 'mature' if self.age < 65\
            else 'old'

        from galaxies.settlement import Settlement
        occupation: str = 'outpost' if isinstance(self.residency, Settlement)\
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

    def work_hours_text(self) -> str:
        """When the person works in their outpost, as a phrase for the chat: "all the time" for the Coordinator,
        "from time to time" for the substitute, else the shift as "from 16 to 24" (the hours of the day)."""
        from galaxies.outpost import SHIFT_HOURS
        if self.role.shifts == 1 and self.role.vacation == 0:
            return "24/7, as usual"
        shift: int = self.residency.shift_of(self)
        if shift == self.role.shifts:
            return "from time to time"
        start: int = shift * SHIFT_HOURS
        return f"from {start} to {start + SHIFT_HOURS}"

    def description_fields(self) -> list[tuple[str, str]]:
        """The person's characteristics as (label, value): what the log and the people dialog show. The label is empty
        for the gender and race, which are shown as a plain line."""
        result: list[tuple[str, str]] = [
            ('ID', f"{self.seed}."),
            ('', f"{self.gender_group.name.capitalize()}, {self.race.name.capitalize()}"),
            ('D.O.B.', f"{self.dob.strftime('%Y-%m-%d')} ({self.age} y.o.)"),
            ('Role', self.role.name),
            ('Last time met', self.last_time_met_text()),
        ]

        from galaxies.settlement import Settlement
        if isinstance(self.residency, Settlement):
            result.append(('Residency', self.residency.residency_line()))
        return result

    def matches_search(self, query: str, labels: Optional[Tuple[str, ...]] = None) -> bool:
        """Whether the search text is in the value of one of the person's description fields, in their name or in their
        comment, ignoring case and the spaces at the ends of the text (the labels do not count). `labels` limits the
        fields to those shown with these labels (None: all of them). An empty search matches everyone."""
        query = query.strip().casefold()
        if not query:
            return True
        texts = [value for label, value in self.description_fields() if labels is None or label in labels]
        texts += [self.get_full_name(), self.comment]
        return any(query in text.casefold() for text in texts)

    def log_description(self) -> Person:
        """Logs the person's characteristics, one ' - ' line each."""
        description = ''.join(f" - {label}: {value}\n" if label else f" - {value}\n" for label,
                              value in self.description_fields())
        logger.info(
            f"PERSON UPDATE: {self.get_full_name()}"
            f"\n{description}"
            f"- Sympathy: {self.sympathy100}" # Not told to player.
            )
        return self

    def get_title(self) -> str:
        # Find out where this person is... as for now, guess Those-Who-Share
        return political_entity.THOSE_WHO_SHARE.title_for(self.reputation)

    def get_player_title(self) -> str:
        # Subjective.
        import galaxies.people.player as gpp
        player_rep = gpp.current_player.those_who_share.reputation
        mood_mod = random.gauss(0.5, 0.01)
        final_rep = player_rep * mood_mod * (self.sympathy100 + 50)/100
        return political_entity.THOSE_WHO_SHARE.title_for(final_rep)

    def address(self, player: Player, to_player: bool) -> str:
        """How the pilot and this person address each other once they have met, by their relative reputation: the
        form this person uses for the pilot (`to_player`), or the one the pilot uses for this person.
        Whoever is more than twice above the speaker is addressed with respect ("Pilot Surname", "Role Surname"); then
        the person's sympathy decides: a low one only gets the title, a middle one the title and the name unless the
        addressee is far below the speaker, a high one the name alone."""
        if to_player:
            addressee_reputation, speaker_reputation = player.those_who_share.reputation, self.reputation
            respectful, title, name = f"Pilot {player.surname}", player.get_title(), player.first_name
        else:
            addressee_reputation, speaker_reputation = self.reputation, player.those_who_share.reputation
            respectful, title, name = f"{self.role.name} {self.surname}", self.get_title(), self.name

        if addressee_reputation > 2 * speaker_reputation:
            return respectful
        elif self.sympathy100 < 20:
            return title
        elif self.sympathy100 < 80 and addressee_reputation * 2 > speaker_reputation:
            return f"{title} {name}"
        return name  # Friends, or far below.

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
            from galaxies.settlement import Settlement
            self.first_met_at = self.residency.address() if isinstance(self.residency, Settlement) else ''
            self.record()
        return self

    def adjust_sympathy(self, change: float) -> Person:
        """Changes the sympathy and saves it (see record)."""
        self.sympathy100 = _nudged(self.sympathy100, change)
        logger.debug(f"Sympathy of {self.get_full_name()} changed to {self.sympathy100:.2f}")
        return self.record()
    # endregion
