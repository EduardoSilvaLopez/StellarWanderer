from __future__ import annotations

from typing import TYPE_CHECKING, Any
from enum import Enum
from functools import lru_cache
import os
from typing import Optional, Tuple
import pygame
import random

from datetime import datetime
from Dialogs import show_message
import logging

import GameEnvironment as gem

if TYPE_CHECKING:
    from Galaxies.outpost import Outpost

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

    def __init__(self, seed: float, working_place: Outpost):
        my_random = random.Random(seed)

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

        self.icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self.portrait = self._load_portrait(my_random)

        self.working_place: Any = working_place

    def _load_portrait(self, my_random: random.Random) -> Person:
        filename_prefix: str = 'outpost.com.' + str(self.race.name).lower() + "." + str(self.gender_group.name).lower() + ".mature.content"
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

    def get_full_name(self) -> str:
        return 'Comrade ComOfficer ' + self.name + ' ' + self.surname # No Chinese exception. Intentional.

    def communicate_from(self, outpost: Outpost) -> Person:
        from Galaxies.People.player import current_player as player
        from Spaceships.cargo_hold import CargoHold
        from Galaxies.Politics import political_entity
        from Galaxies.Politics.personal_status import PersonalStatus

        cargo_hold: CargoHold = player.ship.cargo_hold
        status: PersonalStatus = player.political_status[political_entity.THOSE_WHO_SHARE]

        wp: Any = self.working_place
        visit_time_delta = 0\
            if not hasattr(wp, "last_visited")\
                or not isinstance(wp.last_visited, datetime)\
            else (wp.last_visited - gem.current_environment.date_time).total_seconds()

        status.reputation -= 0.02 * visit_time_delta / (24*60*60) # "Maintenance, air, water and food needed."
        if 0 < visit_time_delta < 60 * 60:
            status.reputation -= 0.005 # "Annoying person."
            show_message(
                'outpost_start_came_back',
                player_title=player.get_title()
                )
        elif cargo_hold.content[CargoHold.CargoElement.ORE] == 0:
            show_message(
                'outpost_start_no_ore',
                full_name=self.get_full_name(),
                player_title=player.get_title(),
                on_result=self.com_outpost_no_ore
                )
        else:
            show_message(
                'outpost_start_ore',
                full_name=self.get_full_name(),
                player_title=player.get_title(),
                on_result=self.com_outpost_ore
                )

        logger.debug(f"Reputation now: {status.reputation}")
        return self

    def com_outpost_no_ore(self, button_index: int) -> None:
        from Galaxies.Politics import political_entity
        from Galaxies.People.player import current_player as player
        from Galaxies.Politics.personal_status import PersonalStatus

        status: PersonalStatus = player.political_status[political_entity.THOSE_WHO_SHARE]

        if button_index == 1:
            status.reputation -= 0.1
        logger.debug(f"Reputation now: {status.reputation}")

    def com_outpost_ore(self, button_index: int) -> None:
        from Galaxies.Politics import political_entity
        from Galaxies.People.player import current_player as player
        from Spaceships.cargo_hold import CargoHold
        from Galaxies.Politics.personal_status import PersonalStatus

        cargo_hold: CargoHold = player.ship.cargo_hold
        status: PersonalStatus = player.political_status[political_entity.THOSE_WHO_SHARE]

        ore_given = cargo_hold.content[CargoHold.CargoElement.ORE]
        cargo_hold.content[CargoHold.CargoElement.ORE] = 0
        status.reputation += 0.02 * ore_given # "Ore was shared."

        if button_index == 0:
            status.reputation += 0.001 # "The right answer."
        if button_index == 2:
            status.reputation -= 1 # "Disloyal proposal."
                #Todo: persist, this option won't be offered anymore.
            show_message(
                'outpost_ore_payment_requested',
                title=player.get_title()
                )

        logger.debug(f"Reputation now: {status.reputation}")
