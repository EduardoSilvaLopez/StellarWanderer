from __future__ import annotations
import random
import pygame
from typing import Optional
from common.paths import resource_path


class PoliticalEntity:
    def __init__(self, name: str, color: tuple, icon_filename: str, titles: dict, names_1: list, names_2: list) -> None:
        self.name: str = name
        self.color: tuple = color
        self.icon: Optional[pygame.Surface] = None
        self._load_icon(icon_filename)
        self.titles = titles
        self.settlement_names_1 = names_1
        self.settlement_names_2 = names_2

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
        return my_random.choice(self.settlement_names_1) + " " + my_random.choice(self.settlement_names_2)


THOSE_WHO_SHARE: PoliticalEntity = PoliticalEntity(
        "Those-Who-Share",
        (192, 0, 0),
        "PoliticalEntity.1.png",
        {
         float('-inf'): 'Prisioner',
            -30: 'Dependent',
            -10: 'Student',
            0: 'Citizen',
            10: 'Comrade',
            100: 'Speaker',
            1000: 'Champion',
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
        ]
    )
