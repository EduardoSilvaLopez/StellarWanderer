from __future__ import annotations
from typing import Optional

import random
import pygame

from common.paths import resource_path
import logging

logger = logging.getLogger(__name__)

class PoliticalEntity:
    def __init__(
            self, name: str,
            color: tuple,
            icon_filename: str,
            titles: dict,
            names_1: dict,
            names_2: dict,
            exchange_reputation_changes: dict
            ) -> None:
        self.name: str = name
        self.color: tuple = color
        self.icon: Optional[pygame.Surface] = None
        self._load_icon(icon_filename)
        self.titles = titles
        self.settlement_names_1 = names_1
        self.settlement_names_2 = names_2
        self.exchange_reputation_changes: dict = exchange_reputation_changes

    def title_for(self, reputation: float) -> Optional[str]:
        return next((self.titles[k] for k in sorted(self.titles, reverse=True) if reputation >= k), None)

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
        "Those-Who-Share",
        (192, 0, 0),
        "PoliticalEntity.1.png",
        {
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
        [
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
        [
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
        {
            "maintenance": 24.0,
            "energy": 5e-13,
            "credits": 100.0,
            "air": 0.0006,
            "water": 0.0003,
            "food": 0.0006,
            "mines": 5.0,
            "ore": 0.005,
        }
    )
