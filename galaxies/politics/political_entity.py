from __future__ import annotations
from typing import List, Optional

import random
import pygame

from common.paths import resource_path
import logging

from galaxies.people.person import Ethnicity

logger = logging.getLogger(__name__)

class PoliticalEntity:
    def __init__(
            self, name: str,
            color: tuple,
            icon_filename: str,
            titles: dict,
            names_1: dict,
            names_2: dict,
            exchange_reputation_changes: dict,
            settlements: List[(str, Ethnicity)],
            planets: List[(str)],
            ) -> None:
        self.name: str = name
        self.color: tuple = color
        self.icon: Optional[pygame.Surface] = None
        self._load_icon(icon_filename)
        self.titles = titles
        self.settlement_names_1 = names_1
        self.settlement_names_2 = names_2
        self.exchange_reputation_changes: dict = exchange_reputation_changes
        self.settlements = settlements
        self.planets = planets

    def title_for(self, reputation: float) -> Optional[str]:
        return next((self.titles[k] for k in sorted(self.titles, reverse=True) if reputation >= k), None)

    def title_floor(self, reputation: float) -> float:
        """The lowest reputation that keeps the title `reputation` gives: its threshold (-inf for the lowest one)."""
        return max((k for k in self.titles if reputation >= k), default=float('-inf'))

    def _load_icon(self, icon_filename: str) -> None:
        """Load the icon image from common/resources/textures."""
        icon_path = resource_path('textures', icon_filename)
        try:
            self.icon = pygame.image.load(icon_path)
        except Exception as e:
            print(f"Warning: Could not load political entity icon {icon_filename}: {e}")

    def generate_outpost_name(self, my_random: random.Random) -> str:
        return self.settlement_names_1[my_random.randint(0, len(self.settlement_names_1) - 1)]\
            + " " + self.settlement_names_2[my_random.randint(0, len(self.settlement_names_2) - 1)]

THOSE_WHO_SHARE: PoliticalEntity = PoliticalEntity(
        name="Those-Who-Share",
        color=(192, 0, 0),
        icon_filename="PoliticalEntity.1.png",
        titles={
         float('-inf'): 'Prisoner',
            -30: 'Dependent',
            -10: 'Student',
            0: 'Pioneer',
            10: 'Citizen',
            20: 'Comrade',
            50: 'Companion',
            100: 'Forebear',
            200: 'Guardian',
            500: 'Herald',
            1000: 'Steward', # Xi
            2000: 'Hero',
            5000: 'Champion',
            10000: 'Premier'
        },
        names_1=[
            "Arduous",
            "Beneficial",
            "Burdensome",
            "Challenging",
            "Commendable",
            "Conscientious",
            "Constructive",
            "Dutiful",
            "Edifying",
            "Exacting",
            "Enriching",
            "Formidable",
            "Laborious",
            "Laudable",
            "Pressing",
            "Purposeful",
            "Responsible",
            "Rigorous",
            "Salutary",
            "Uplifting",
            "Weighty",
            "Worthwhile"
        ],
        names_2=[
            "Aim",
            "Assignment",
            "Charge",
            "Duty",
            "End",
            "Goal",
            "Hope",
            "Issue",
            "Mission",
            "Objective",
            "Outcome",
            "Plan",
            "Project",
            "Purpose",
            "Quest",
            "Reality",
            "Requirement",
            "Responsibility",
            "Result",
            "Target",
            "Task",
            "Undertaking",
            "Work"
        ],
        exchange_reputation_changes={
            "maintenance": 24.0,
            "energy": 5e-13,
            "credits": 100.0,
            "air": 0.0006,
            "water": 0.0003,
            "food": 0.0006,
            "mines": 5.0,
            "ore": 0.008,
            "raw_water": 0.001,
        },
        settlements=[
            ('Jiùjīnshān, Ài', Ethnicity.BLACK),
            ('Niǔyuē, Shèqū', Ethnicity.BLACK),
            ('Bālí, Tón-lǐ-xīn', Ethnicity.WHITE),
            ('Bólín, Ài', Ethnicity.WHITE),
            ('Mòxīgē, Ài', Ethnicity.LATIN),
            ("Shèngbǎoluó, Xǐ'ài", Ethnicity.LATIN),
            ('Mǎdélǐ, Shèqū', Ethnicity.LATIN),
            ('Togyo, Ài', Ethnicity.ASIAN),
            ('Sel, Shèqū', Ethnicity.ASIAN),
            ('Shangha, Shèqū', Ethnicity.ASIAN),
            ('Bejing, Ài', Ethnicity.ASIAN),
            ('Chenzhen, Tón-lǐ-xīn', Ethnicity.ASIAN),
            ('Singapa, Tón-lǐ-xīn', Ethnicity.ASIAN),
            ('Guanzhou, Ài', Ethnicity.ASIAN),
            ('Xīn-xīàng, Tón-lǐ-xīn', Ethnicity.ASIAN),
            ("Pínděng, Xǐ'ài", Ethnicity.ASIAN),
            ('Tuánjié, Ài', Ethnicity.ASIAN),
            ('Lanfang-dexī, Tuánjié', Ethnicity.ASIAN),
            ('Wei-de-xīwàng, Tuánjié', Ethnicity.ASIAN),
            ('Kǎisèlín, Ài', Ethnicity.ASIAN),
            ('Àidéhuá-duō, Guānhái', Ethnicity.ASIAN),
            ('Dàshān, Guānhái', Ethnicity.ASIAN),
            ('Huǒshānkǒu, Bānzhù', Ethnicity.ASIAN),
        ]
        , planets= [
            'Ài',
            'Shèqū',
            'Tón-lǐ-xīn',
            "Xǐ'ài",
            'Tuánjié',
            'Guānhái',
            'Bānzhù',
        ]
    )
