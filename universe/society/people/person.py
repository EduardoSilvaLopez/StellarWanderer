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
    from universe.society.people.player import Player
    from universe.artifacts.settlements.settlement import Settlement

from universe.society.politics import political_entity
from universe.society.people.role import (RETIREMENT_AGE_MAX, RETIREMENT_AGE_MIN, STAFF_AGE_MAX, STAFF_AGE_MIN, Role)
import game_environment as gem
from common.paths import resource_path

PEOPLE_DIR = resource_path('people')
SECONDS_PER_YEAR = 365.2425 * 24 * 60 * 60
MAX_ICON_ZOOM = 0.10  # of the portrait, see Person._varied
MAX_ICON_DARKENING = 0.15
SOCIAL_FACTOR = 5  # of the staff: scales the reputation

logger = logging.getLogger(__name__)

IMPRISONED = 'imprisoned'  # a kind of status change


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
    """
    A 'personality' trait (0 to 100) after `change`: if it moves to the extremes, it moves slower the nearer
    it is to them.

    Why a ruler: the rate is dv/dc = 2**(-|v - 50| / 10), so a trait halves its speed for every
    10 points away from 50. A change must not be applied at the rate of the starting value, or a
    big change jumps past the curve (50 + 50 would give 100 at once, and two changes of 25 would
    not give the same as one of 50). Instead the change is walked along the curve: each point v
    has a position c(v) = integral from 50 to v of 2**(|x - 50| / 10) dx, the change is added to
    that position, and the result is the point that has that position. Splitting a change then
    gives the same result as applying it at once, and the rate is exact for any size of change.

    With c(v) = sign(v - 50) * (10 / ln 2) * (2**(|v - 50| / 10) - 1), the inverse is
    v = 50 + sign(c) * 10 * log2(1 + |c| * ln 2 / 10). Near 50 the ruler is almost a straight
    line, so small changes move as before. The ends 0 and 100 lie 447 units away, so the clamp
    to 0..100 only acts for changes beyond that.

    Examples (from 50, the old formula in brackets):
        _nudged(50, 50)  -> 71.6  (100): one big change no longer jumps to the end
        _nudged(50, 25)  -> 64.5, then _nudged(64.5, 25) -> 71.6: same as one change of 50
        _nudged(50, -50) -> 28.4  (0)
        _nudged(90, 10)  -> 90.6  (90.6): near an extreme, both formulas agree
    """

    # First take away the "towards the middle" part:
    apply_directly = 0
    if (value <= 50 and change > 0) or (value > 50 and change <= 0):
        max_apply_now = abs(value - 50)
        apply_directly = min(max_apply_now, change) if change >= 0 else -min(max_apply_now, -change)
        change += -apply_directly if change >= 0 else +apply_directly
    offset: float = value - 50
    ruler: float = math.copysign((10 / math.log(2)) * (2 ** (abs(offset) / 10) - 1), offset)
    ruler += change
    offset = math.copysign(10 * math.log2(1 + abs(ruler) * math.log(2) / 10), ruler)
    return apply_directly + max(0, min(100, 50 + offset))

# The curves of physiology and attraction (see _skewed): at 20 or 80, a bump with a tail to the far end, lifted at both
# ends by a straight floor (a pure Beta would be zero there); at 50, a gauss.
SKEW_BUMP_WEIGHT = 0.354  # the share of the bump in the mix, the rest being the floor
SKEW_FLOOR_TILT = 0.62  # the floor falls from 1 at 0 to 1 - SKEW_FLOOR_TILT at 1
SKEW_MAX_DENSITY = 1.5  # above the highest point of the mix, for the rejection sampling
SKEW_GAUSS_SPREAD = 20.0


def _skewed(centre: float, my_random: random.Random) -> float:
    """A value from 0 to 100 that is most likely at `centre` (20, 50 or 80). Those at 80 mirror those at 20."""
    if centre == 50:
        while True:
            value: float = my_random.gauss(50, SKEW_GAUSS_SPREAD)
            if 0 <= value <= 100:
                return value
    while True:
        x: float = my_random.random()
        bump: float = 30 * x * (1 - x) ** 4  # the Beta(2, 5) density, peak at 0.2
        density: float = SKEW_BUMP_WEIGHT * bump + (1 - SKEW_BUMP_WEIGHT) * (1 - SKEW_FLOOR_TILT * x)
        if my_random.random() * SKEW_MAX_DENSITY < density:
            return 100 * (1 - x if centre > 50 else x)


class Ethnicity(Enum):
    ASIAN = 1
    BLACK = 2
    WHITE = 3
    LATIN = 4
    ARAB = 5
    INDIAN = 6
    SIKH = 7
    INDONESIAN = 8


ETHNICITY_SHARES: dict[Ethnicity, float] = {
    Ethnicity.ASIAN: 0.477, Ethnicity.WHITE: 0.261, Ethnicity.LATIN: 0.099, Ethnicity.BLACK: 0.063,
    Ethnicity.ARAB: 0.04, Ethnicity.INDIAN: 0.04, Ethnicity.INDONESIAN: 0.01, Ethnicity.SIKH: 0.01,
}
# The ethnicities with no portraits yet show those of a look-alike one.
PORTRAIT_FALLBACKS: dict[Ethnicity, Ethnicity] = {
    Ethnicity.ARAB: Ethnicity.LATIN, Ethnicity.INDIAN: Ethnicity.ASIAN, Ethnicity.SIKH: Ethnicity.ASIAN,
    Ethnicity.INDONESIAN: Ethnicity.ASIAN,
}
# The languages a name takes after the ethnicity, with their shares; the rest of the time it takes any other.
NATIVE_LANGUAGES: dict[Ethnicity, dict[str, float]] = {
    Ethnicity.ASIAN: {'chinese': 0.8}, Ethnicity.WHITE: {'english': 0.8}, Ethnicity.LATIN: {'spanish': 0.8},
    Ethnicity.BLACK: {'english': 0.4, 'french': 0.2, 'swahili': 0.2}, Ethnicity.ARAB: {'arab': 0.8},
    Ethnicity.INDIAN: {'indian': 0.8}, Ethnicity.SIKH: {'sikh': 0.8}, Ethnicity.INDONESIAN: {'indonesian': 0.8},
}
# Every language of names (files in common/resources/people), with its weight when it is not the native one.
LANGUAGE_WEIGHTS: dict[str, float] = {
    'chinese': 1, 'english': 1, 'spanish': 1, 'arab': 2, 'indian': 2, 'sikh': 1, 'japanese': 1, 'indonesian': 1,
    'swahili': 1, 'german': 2, 'french': 2, 'italian': 1, 'russian': 1, 'ukrainian': 1,
}
INDONESIAN_HOME = 'Singapa, Tón-lǐ-xīn'
INDONESIAN_HOME_SHARE = 0.6

class Person:

    class Pronoun(Enum):  # chosen by the pilot (PilotIdentityDialog), drawn for the people; not a gender
        SHE = 1
        THEY = 2
        HE = 3

    # The pronoun sets the physiology (the centre of its curve) and the attraction (the mirror one), as for the pilot.
    PHYSIOLOGY_CENTRE: dict = {Pronoun.SHE: 20, Pronoun.THEY: 50, Pronoun.HE: 80}
    ATTRACTION_CENTRE: dict = {Pronoun.SHE: 80, Pronoun.THEY: 50, Pronoun.HE: 20}

    # region Generation
    def __init__(self, seed: int, residency: Settlement, role: Role, hired_at: datetime) -> None:
        """A person as they were when hired for `role` at `hired_at`: the role shapes their age, reputation and traits
        once, here, and they keep them if they change role. They leave at `departure_at`."""
        my_random = random.Random(seed)
        social_factor: float = SOCIAL_FACTOR
        age_min: int = STAFF_AGE_MIN + role.age_raise
        age_max: int = STAFF_AGE_MAX + role.age_raise
        self.seed: int = seed
        self.role: Role = role
        self.hired_at: datetime = hired_at

        entity: political_entity.PoliticalEntity | None = residency.stellar_system.political_entity
        assert entity is not None, "Settlements, and so their staff, exist only in systems with a political entity"
        self.entity: political_entity.PoliticalEntity = entity

        self.race: Ethnicity = my_random.choices(list(ETHNICITY_SHARES), weights=list(ETHNICITY_SHARES.values()))[0]

        rnd: float = my_random.random()
        self.pronoun: Person.Pronoun = Person.Pronoun.SHE if rnd < 0.45 else Person.Pronoun.THEY if rnd < 0.55 \
            else Person.Pronoun.HE
        self.physiology: float = _skewed(Person.PHYSIOLOGY_CENTRE[self.pronoun], my_random)
        self.attracted_to: float = _skewed(Person.ATTRACTION_CENTRE[self.pronoun], my_random)

        # Each name has its own language, kept for the relatives that will be generated from them. The pronoun gives
        # the list of names; they take the side of the physiology, where over 50 is male.
        name_is_male: bool = self.pronoun == Person.Pronoun.HE \
            or (self.pronoun == Person.Pronoun.THEY and self.physiology > 50)
        gender: str = 'male' if name_is_male else 'female'
        self.name_language: str = self._roll_language(my_random)
        self.surname_language: str = self._roll_language(my_random)

        self.name: str = _pick_name(my_random, f'{self.name_language}_{gender}_names.txt')
        self.surname: str = _pick_name(my_random, f'{self.surname_language}_{gender}_surnames.txt')
        if role.reputation_bonus >= 0:
            self.reputation: float = 5 * social_factor * my_random.gauss(1.0, 0.3) + role.reputation_bonus
        else:
            self.reputation: float = 5 * social_factor * my_random.gauss(1.0, 0.3) * -role.reputation_bonus
        # Never below 0: a Student (a polischool departure, a status of the staffing history) is not made by chance.
        # Generation is for a role for now; a future kind of generation (children, for one) may start lower.
        self.reputation = max(self.reputation, 0.0)

        self.empathy100: float = my_random.random() * 100
        self.empathy100 = _nudged(self.empathy100, role.personality_bonus[1])

        self.sociability100: float = my_random.random() * 100
        self.sociability100 = _nudged(self.sociability100, role.personality_bonus[2])

        self.loyalty100: float = my_random.random() * 100
        self.loyalty100 = _nudged(self.loyalty100, math.sqrt(self.reputation)) if self.reputation >= 0 else \
            _nudged(self.loyalty100, self.reputation)
        self.loyalty100 = _nudged(self.loyalty100, role.personality_bonus[0])

        self.sympathy100: float = 50.0

        seconds_after_birth: float = (my_random.random() * (age_max - age_min) + age_min) * 365.2425 * 24 * 60 * 60
        self.dob: datetime = hired_at - timedelta(seconds=seconds_after_birth)
        self.planet_of_birth, self.place_of_birth = self._generate_place_of_birth(my_random)
        self.childhood: str = self._generate_childhood(my_random)
        self.hobby: str = self._generate_hobby(my_random)
        self.ideal_role_dimensions: tuple = (
            self.loyalty100 + my_random.gauss(0, 10),
            self.empathy100 + my_random.gauss(0, 10),
            self.sociability100 + my_random.gauss(0, 10)
            )
        self.perception: float = my_random.uniform(0, 100)
        self.education: float = my_random.uniform(0, 100)
        self.sexuality: float = my_random.uniform(0, 100)
        self.ideology: float = my_random.random()  # a placeholder: the ideologies of the entity will read it
        self.longevity: float = my_random.random()  # read later, to work out when they die
        my_random.random()  # Space for further characteristics.
        retirement_age: float = my_random.uniform(RETIREMENT_AGE_MIN, RETIREMENT_AGE_MAX) + max(0, role.age_raise)
        self.retirement_at: datetime = self.dob + timedelta(seconds=retirement_age * SECONDS_PER_YEAR)
        self._icon_seed: int = my_random.getrandbits(63)

        self.residency: Any = residency
        self.last_communication_at: Optional[datetime] = None

        self._icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self._icon_loaded: bool = False

        self.interactions: dict = {}
        # Where the player first talked to this person, e.g. "Consequential Task, planet Iuief, Aqakhaceia System"
        # (see meet). None until then, also for a person already in `persons` (see record).
        self.first_met_at: Optional[str] = None
        self.comment: str = ''  # what the player wrote about this person (see set_comment)
        # What happened to the person because of the pilot, with its date: (date, 'imprisoned'). Retirement is not
        # here: it comes from the seed.
        self.status_changes: list[tuple[datetime, str]] = []
        if self.seed in gem.current_environment.persons:
            # Apply alterations.
            my_alterations = gem.current_environment.persons[self.seed]
            self.first_met_at = my_alterations['first_met_at']
            self.comment = my_alterations.get('comment', '')
            if my_alterations.get('last_communication_at'):
                self.last_communication_at = datetime.fromisoformat(my_alterations['last_communication_at'])
            self.status_changes = [(datetime.fromisoformat(when), kind)
                                   for when, kind in my_alterations.get('status_changes', [])]
            if 'sympathy' in my_alterations:
                self.sympathy100 = my_alterations['sympathy']
            if 'interactions' in my_alterations:
                for dt_str, lines in my_alterations['interactions'].items():
                    dt = datetime.fromisoformat(dt_str)
                    self.interactions[dt] = lines
            self.log_description()

    def _roll_language(self, my_random: random.Random) -> str:
        """The language of one name: one of the ethnicity's own by their shares, else any other by its weight."""
        native: dict[str, float] = NATIVE_LANGUAGES[self.race]
        rnd: float = my_random.random()
        for language, share in native.items():
            if rnd < share:
                return language
            rnd -= share
        others: list[str] = [language for language in LANGUAGE_WEIGHTS if language not in native]
        return my_random.choices(others, weights=[LANGUAGE_WEIGHTS[language] for language in others])[0]

    def _generate_place_of_birth(self, my_random: random.Random) -> tuple:
        """Chooses a place of birth according to ethnicity, or just 'some place'. An ethnicity with no settlement of
        its own comes from any of them, and the Indonesians often from their home. The planet is the place's own,
        so the two never disagree."""
        settlements: list[tuple[str, Ethnicity]] = political_entity.THOSE_WHO_SHARE.settlements
        matching: list[str] = [name for name, ethnicity in settlements if ethnicity == self.race]\
            or [name for name, _ in settlements]
        if self.race == Ethnicity.INDONESIAN and my_random.random() < INDONESIAN_HOME_SHARE:
            place = INDONESIAN_HOME
        elif matching and my_random.random() < 0.8:
            place = my_random.choice(matching)
        else:
            planet: str = my_random.choice(political_entity.THOSE_WHO_SHARE.planets)
            place = ('a small city' if my_random.random() < 2 / 3 else 'a town') + ", " + planet
        return place.rsplit(', ', 1)[-1], place

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
        """A hobby from the entity's lists: the asocial ones below 20 sociability, else the sociable ones."""
        if self.sociability100 < 20:
            return my_random.choice(self.entity.hobbies_asocial)
        return my_random.choice(self.entity.hobbies_sociable)

    @property
    def icon(self) -> Optional[pygame.Surface]:
        """The portrait, loaded the first time it is asked for: the people of the staff history who are never shown
        cost no picture."""
        if not self._icon_loaded:
            self._icon_loaded = True
            self._load_icon(random.Random(self._icon_seed))
        return self._icon

    def _load_icon(self, my_random: random.Random) -> None:
        """The portrait, into `_icon`: one of the pictures for the person's occupation, race, age and gender, by the
        seed. In a settlement the occupation is the role's `portrait`, or 'uniform' when the role has none for them."""
        age_group: str = 'young' if self.age < 30\
            else 'adult' if self.age < 45\
            else 'mature' if self.age < 65\
            else 'old'

        from universe.artifacts.settlements.settlement import Settlement
        occupations: list[str] = [self.role.portrait, 'uniform'] if isinstance(self.residency, Settlement)\
            else ['generic']
        ethnicities: list[Ethnicity] = [self.race] + ([PORTRAIT_FALLBACKS[self.race]]
                                                       if self.race in PORTRAIT_FALLBACKS else [])
        portraits_dir = resource_path('portraits')
        try:
            names = os.listdir(portraits_dir)
        except OSError:
            names = []

        # Sorted, so the same seed always picks the same portrait whatever order the OS lists the files in. The
        # person's own ethnicity comes before their occupation.
        candidates: list[str] = []
        sex: str = 'male' if self.physiology > 50 else 'female'
        prefixes: list[str] = [f"{occupation}.{ethnicity.name.lower()}.{age_group}.{sex}"
                               for ethnicity in ethnicities for occupation in occupations]
        for prefix in prefixes:
            candidates = sorted(name for name in names if name.startswith(prefix))
            if candidates:
                break
        if not candidates:
            print(f"Warning: No person portrait starting with {prefixes[0]} in {portraits_dir}")
            return
        filename: str = my_random.choice(candidates)

        icon_path = os.path.join(portraits_dir, filename)
        try:
            picture: pygame.Surface = pygame.image.load(icon_path)
        except Exception as e:
            print(f"Warning: Could not load person entity icon {filename}: {e}")
            return
        self._icon = self._varied(picture, my_random)

    @staticmethod
    def _varied(picture: pygame.Surface, my_random: random.Random) -> pygame.Surface:
        """The picture a little zoomed, off-centre and darker, so that people sharing a picture do not look identical.
        The draws come last of the person's, after the choice of the picture, and the size stays the same."""
        zoom: float = 1 + my_random.random() * MAX_ICON_ZOOM
        x_share: float = my_random.random()
        y_share: float = my_random.random()
        brightness: float = 1 - my_random.random() * MAX_ICON_DARKENING

        width, height = picture.get_size()
        crop_width, crop_height = round(width / zoom), round(height / zoom)
        crop = pygame.Rect(round((width - crop_width) * x_share), round((height - crop_height) * y_share),
                           crop_width, crop_height)
        varied: pygame.Surface = pygame.transform.smoothscale(picture.subsurface(crop), (width, height))
        shade: int = round(255 * brightness)
        varied.fill((shade, shade, shade), special_flags=pygame.BLEND_RGB_MULT)
        return varied
    # endregion

    # region Presence
    @property
    def departure_at(self) -> datetime:
        """When they leave the staff: at retirement, or earlier when the pilot had them arrested."""
        return min([self.retirement_at] + [when for when, kind in self.status_changes if kind == IMPRISONED])

    def is_present(self, when: datetime) -> bool:
        """Whether they are working in their settlement at `when`: hired, and not yet retired or arrested."""
        return self.hired_at <= when < self.departure_at
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
        from universe.artifacts.settlements.outpost import SHIFT_HOURS
        if self.role.shifts == 1 and self.role.vacation == 0:
            return "24/7, as usual"
        shift: Optional[int] = self.residency.shift_of(self)
        if shift is None:
            return "nowhere anymore"
        if shift == self.role.shifts:
            return "from time to time"
        start: int = shift * SHIFT_HOURS
        return f"from {start} to {start + SHIFT_HOURS}"

    def description_fields(self) -> list[tuple[str, str]]:
        """The person's characteristics as (label, value): what the log and the people dialog show. The label is empty
        for the gender and race, which are shown as a plain line."""
        result: list[tuple[str, str]] = [
            ('ID', f"{self.seed}."),
            ('', f"{self.pronoun.name.capitalize()}, {self.race.name.capitalize()}"),
            ('D.O.B.', f"{self.dob.strftime('%Y-%m-%d')} ({self.age} y.o.)"),
            ('Role', self.role.name),
            ('Last time met', self.last_time_met_text()),
        ]

        from universe.artifacts.settlements.settlement import Settlement
        if isinstance(self.residency, Settlement):
            result.append(('Residency', self.residency.residency_line()))
        return result

    def how_happy_with_role(self) -> int:
        '''Returns 0, 1 or 2 for not happy, content, really happy.'''
        HAPPY_MAX_DIST: float = 25
        CONTENT_MAX_DIST: float = 50

        dist: float = math.sqrt(
            (self.role.ideal_for[0] - self.ideal_role_dimensions[0])**2 + \
            (self.role.ideal_for[1] - self.ideal_role_dimensions[1])**2 + \
            (self.role.ideal_for[2] - self.ideal_role_dimensions[2])**2
            )

        return 2 if dist < HAPPY_MAX_DIST else 1 if dist < CONTENT_MAX_DIST else 0

    def main_problem_with_role(self) -> str:
        '''Return + or - loy, soc or emp: they wish for something with...
        Example: ideal for loy = 0. NPC has loy = 100 (a bit randomly modified). The result will be +loy, "something
        which required more loy".
        '''
        diff_loy: float = self.ideal_role_dimensions[0] - self.role.ideal_for[0]
        diff_emp: float = self.ideal_role_dimensions[1] - self.role.ideal_for[1]
        diff_soc: float = self.ideal_role_dimensions[2] - self.role.ideal_for[2]
        dimension: str = ''
        if abs(diff_loy) > abs(diff_emp) and abs(diff_loy) > abs(diff_soc):
            dimension = "loy"
        elif abs(diff_emp) > abs(diff_soc):
            dimension = "emp"
        else:
            dimension = "soc"
        diff = diff_loy if dimension == "loy" else diff_emp if dimension == "emp" else diff_soc
        return ("+" if diff>= 0 else "-") + dimension

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
            f"- Loyalty: {self.loyalty100}" # Not told to player.
            f"\n- Sympathy: {self.sympathy100}" # Not told to player.
            )
        return self

    def get_title(self) -> str:
        # Find out where this person is... as for now, guess Those-Who-Share
        return political_entity.THOSE_WHO_SHARE.title_for(self.reputation)

    def get_player_title(self) -> Optional[str]:
        # Subjective.
        import universe.society.people.player as gpp
        player_rep = gpp.current_player.reputation
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
            addressee_reputation, speaker_reputation = player.reputation, self.reputation
            respectful, title, name = f"Pilot {player.surname}", player.get_title(), player.first_name
        else:
            addressee_reputation, speaker_reputation = self.reputation, player.reputation
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

        # The name is written for whoever reads the savefile: loading generates it again from the seed and ignores it.
        result: dict = {'seed': self.seed, 'name': self.get_full_name(), 'first_met_at': self.first_met_at}
        if self.comment:
            result['comment'] = self.comment
        if self.last_communication_at:
            result['last_communication_at'] = str(self.last_communication_at)
        result['sympathy'] = self.sympathy100
        if self.status_changes:
            result['status_changes'] = [[str(when), kind] for when, kind in self.status_changes]
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
            from universe.artifacts.settlements.settlement import Settlement
            self.first_met_at = self.residency.address() if isinstance(self.residency, Settlement) else ''
            self.record()
        return self

    def adjust_sympathy(self, change: float) -> Person:
        """Changes the sympathy and saves it (see record)."""
        self.sympathy100 = _nudged(self.sympathy100, change)
        logger.debug(f"Sympathy of {self.get_full_name()} changed to {self.sympathy100:.2f}")
        return self.record()
    # endregion
