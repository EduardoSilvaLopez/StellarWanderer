from __future__ import annotations

from typing import TYPE_CHECKING

from enum import Enum
import os
from typing import Optional
import pygame
import random

from Dialogs import show_message

if TYPE_CHECKING:
    from Galaxies.outpost import Outpost

class Person:
    class Race(Enum):
        ASIAN = 1
        BLACK = 2
        WHITE = 3

    class GenderGroup(Enum): # aesthetically speaking, identification can be done later.
        MALE = 1
        FEMALE = 2

    def __init__(self, seed: float):
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

        self.icon: Optional[pygame.Surface] = None  # stays None if the portrait cannot be loaded
        self.portrait = self.load_portrait(my_random)

    def load_portrait(self, my_random: random.Random) -> Person:
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

    def communicate_from(self, outpost: Outpost) -> Person:
        from Galaxies.People.player import current_player as player
        from Spaceships.cargo_hold import CargoHold
        cargo_hold: CargoHold = player.ship.cargo_hold

        #[outpost: start, came back]
        if cargo_hold.content[CargoHold.CargoElement.ORE] == 0:
            show_message(
                'outpost_start_no_ore',
                title=player.get_title(),
                on_result=self.com_outpost_no_ore
                )
        else:
            show_message(
                'outpost_start_ore',
                title=player.get_title(),
                on_result=self.com_outpost_ore
                )

        return self

    def com_outpost_no_ore(self, button_index: int):
        if button_index == 1:
            from Galaxies.People.player import current_player as player
            from Galaxies.Politics import political_entity

            player.political_status[political_entity.THOSE_WHO_SHARE].reputation -= 0.1
        return

    def com_outpost_ore(self, button_index: int):
        if button_index == 2:
            from Galaxies.People.player import current_player as player

            show_message(
                'outpost_ore_payment_requested',
                title=player.get_title()
                )
