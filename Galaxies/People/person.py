from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
import logging
import os
import random
from typing import TYPE_CHECKING, Any, Optional, Tuple

import pygame

from Dialogs import Message, show_message
from Galaxies.Politics import political_entity
from Galaxies.Politics.personal_status import PersonalStatus
from Spaceships.cargo_hold import CargoHold
import game_environment as gem

if TYPE_CHECKING:
    from Galaxies.outpost import Outpost
    from Galaxies.People.player import Player

PEOPLE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'Resources', 'people')

logger = logging.getLogger(__name__)

@lru_cache(maxsize=None)
def _read_names(file_name: str) -> Tuple[str, ...]:
    """The non-empty lines of Resources/people/<file_name>, read once. A missing file gives no names."""
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

    class GenderGroup(Enum): # aesthetically speaking, identification can be done later.
        MALE = 1
        FEMALE = 2

    def __init__(self, seed: float, residency: Any, age_min: int = 15, age_max: int = 70):
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
        if rnd > 0.55: # sue me :D
            self.gender_group = Person.GenderGroup.FEMALE

        # All these can change later: mixed heritage, gender-fluid...
        language = 'chinese' if self.race == Person.Race.ASIAN else 'english'
        gender = self.gender_group.name.lower()

        self.name: str = _pick_name(my_random, f'{language}_{gender}_names.txt')
        self.surname: str = _pick_name(my_random, f'{language}_{gender}_surnames.txt')
        self.empathy: float = my_random.random() * 100
        self.sociability: float = my_random.random() * 100
        self.loyalty: float = my_random.random() * 100
        self.sympathy: float = 50.0
        seconds_after_birth: float = (my_random.random() * (age_max - age_min) + age_min) * 365.2425 * 24 * 60 * 60
        self.dob = gem.current_environment.date_time + timedelta(seconds = -seconds_after_birth)

        self.residency: Any = residency
        self.last_communication_at: Optional[datetime] = None
        self.the_joker_wanted_payment: bool = False # Just a PoC of individual com. status.

        self.icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self.portrait = self._load_portrait(my_random)

        gem.current_environment.persons.add(self)
        self._log_generation()

    def _load_portrait(self, my_random: random.Random) -> Person:
        age: int = int((gem.current_environment.date_time - self.dob).total_seconds() / (365.2425 * 24 * 60 * 60))
        age_group: str = 'young' if age < 30\
            else 'adult' if age < 45\
            else 'mature' if age < 65\
            else 'old'

        from Galaxies.outpost import Outpost
        occupation: str = 'outpost.com' if isinstance(self.residency, Outpost)\
            else 'generic'
        
        filename_prefix: str = occupation + "." + str(self.race.name).lower() + "." + age_group + "." + str(self.gender_group.name).lower()
        portraits_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Resources', 'portraits')
        try:
            names = os.listdir(portraits_dir)
        except OSError:
            names = []
            
        # Sorted, so the same seed always picks the same portrait whatever order the OS lists the files in.
        candidates = sorted(name for name in names if name.startswith(filename_prefix))
        if not candidates:
            print(f"Warning: No person portrait starting with {filename_prefix} in {portraits_dir}")
            return self
        filename: str = my_random.choice(candidates)

        icon_path = os.path.join(portraits_dir, filename)
        try:
            self.icon = pygame.image.load(icon_path)
        except Exception as e:
            print(f"Warning: Could not load person entity icon {filename}: {e}")

        return self

    def _log_generation(self) -> Person:
        age: int = int((gem.current_environment.date_time - self.dob).total_seconds() / (365.2425 * 24 * 60 * 60))
        logger.info(
            f"PERSON GENERATED: {self.get_full_name()}\n"
            f" - {self.gender_group.name.capitalize()}, {self.race.name.capitalize()}\n"
            f" - D.O.B.: {self.dob.strftime("%Y-%m-%d")} ({age} y.o.)\n"
            f" - Empathy: {self.empathy:.2f}%\n"
            f" - Sociability: {self.sociability:.2f}%\n"
            f" - Loyalty: {self.loyalty:.2f}%\n"
            f" - Sympathy to the player: {self.sympathy:.2f}%\n"
        )
        return self

    def serialize(self) -> dict:
        result: dict = {
            'seed': self.seed,
            'last_communication_at': str(self.last_communication_at),
            'the_joker_wanted_payment': self.the_joker_wanted_payment
        }
        return result

    def get_full_name(self) -> str:
        return 'Comrade ComOfficer ' + self.name + ' ' + self.surname # No Chinese exception. Intentional.

    def communicate_from(self, outpost: Outpost) -> Person:
        from Galaxies.People.player import current_player as player

        cargo_hold: CargoHold = player.ship.cargo_hold
        status: PersonalStatus = player.political_status[political_entity.THOSE_WHO_SHARE]

        wp: Any = self.residency
        visit_time_delta: float = 0\
            if not hasattr(wp, "last_visited")\
                or not isinstance(wp.last_visited, datetime)\
            else (gem.current_environment.date_time - wp.last_visited).total_seconds()
        wp.last_visited = gem.current_environment.date_time

        status.reputation -= 0.02 * visit_time_delta / (24*60*60) # "Maintenance, air, water and food needed."
        mines_required = 5 - cargo_hold.mines
        status.reputation -= 0.10 * mines_required # "Needs more mines."
        cargo_hold.mines += mines_required

        if 0.0 < visit_time_delta < 60 * 60 and self.the_joker_wanted_payment:
            status.reputation -= 0.01 # "Annoying joker."
            show_message(Message(
                title="Return of the Joker",
                text="Ah, the joker again. Yes...?",
                buttons=["Nevermind"],
            ))
        elif 0.0 < visit_time_delta < 60 * 60:
            status.reputation -= 0.005 # "Annoying person."
            show_message(Message(
                title="Huh?",
                text=f"Yes, {player.get_title()} Pilot...?",
                buttons=["Nevermind"],
            ))
        elif cargo_hold.ore == 0:
            show_message(Message(
                title=f"Welcome, {player.get_title()} Pilot.",
                text=(
                    f"I am {self.get_full_name()}.\n\n"
                    f"I see you bring no ore, {player.get_title()}.\n\n"
                    "We will maintain your ship and replenish your air, water and food storage, but please make "
                    "your best to bring some ore.\n\n"
                    "Long live the Community."
                ),
                buttons=["I understand, thank you for sharing", "Yeah, whatever"],
            ), on_result=self.com_outpost_no_ore)
        elif self.last_communication_at:
            show_message(Message(
                title=f"Welcome, {player.get_title()} Pilot.",
                text=(
                    f"I am {self.get_full_name()}.\n\n"
                    f"Thank you for the ore, {player.get_title()}. It helps immensely.\n\n"
                    "We will maintain your ship and replenish your needs as we speak.\n\n"
                    "Long live the Community."
                ),
                buttons=["Long live", "Thank you for sharing"],
            ), on_result=lambda button_index: self.com_outpost_ore(button_index, player))
        else:
            show_message(Message(
                title=f"Welcome, {player.get_title()} Pilot.",
                text=(
                    f"I am {self.get_full_name()}.\n\n"
                    f"Thank you for the ore, {player.get_title()}. It helps immensely.\n\n"
                    "We will maintain your ship and replenish your air, water and food storage.\n\n"
                    "Long live the Community."
                ),
                buttons=["Long live", "Thank you for sharing", "Can you just pay me for the ore, and I buy what I need?"],
            ), on_result=lambda button_index: self.com_outpost_ore(button_index, player))

        self.last_communication_at = wp.last_visited
        logger.debug(f"Reputation now: {status.reputation}")
        return self

    def com_outpost_no_ore(self, button_index: int) -> None:
        from Galaxies.People.player import current_player as player

        status: PersonalStatus = player.political_status[political_entity.THOSE_WHO_SHARE]

        if button_index == 1:
            status.reputation -= 0.1
        logger.debug(f"Reputation now: {status.reputation}")

    def com_outpost_ore(self, button_index: int, player: Player) -> None:
        cargo_hold: CargoHold = player.ship.cargo_hold
        status: PersonalStatus = player.political_status[political_entity.THOSE_WHO_SHARE]

        ore_given = cargo_hold.ore
        cargo_hold.ore = 0
        status.reputation += 0.01 * ore_given # "Ore was shared."

        if button_index == 0:
            status.reputation += 0.001 # "The right answer."
        if button_index == 2:
            self.the_joker_wanted_payment = True
            status.reputation -= 1 # "Disloyal proposal."
                #Todo: persist, this option won't be offered anymore.
            show_message(Message(
                title=f"Welcome, {player.get_title()} Pilot.",
                text=(
                    "What is 'pay'...?\n\n"
                    "Wait... you mean... like in the Shining Throne? or UniDiv?\n\n"
                    "*LAUGHS*\n\n"
                    "How many stamps you think I'd have to...!?\n\n"
                    "You... can't be serious, yes?\n\n"
                    f"Don't make such jokes, {player.get_title()}.\n\n"
                    "Really. Don't.\n\n"
                    "Long live the Community."
                ),
                buttons=["Long live. I guess."],
            ))

        logger.debug(f"Reputation now: {status.reputation}")
