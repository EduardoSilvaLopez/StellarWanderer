from __future__ import annotations
import os
import random
import pygame
from typing import Optional


class PoliticalEntity:
    def __init__(self, name: str, color: tuple, icon_filename: str, titles: dict, names_1: dict, names_2: dict) -> None:
        self.name: str = name
        self.color: tuple = color
        self.icon: Optional[pygame.Surface] = None
        self._load_icon(icon_filename)
        self.titles = titles
        self.settlement_names_1 = names_1
        self.settlement_names_2 = names_2

    def title_for(self, reputation: float) -> str:
        for k in sorted(self.titles, reverse=True):
            if reputation >= k:
                return self.titles[k]

    def _load_icon(self, icon_filename: str) -> None:
        """Load the icon image from Resources/textures."""
        icon_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Resources', 'textures', icon_filename)
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
            float('-inf'): 'Prisioner',
            -100: 'Dependent',
            -10: 'Student',
            0: 'Citizen',
            10: 'Comrade',
            100: 'Speaker',
            1000: 'Champion',
            10000: 'Premier'
        },
        [
            'Hard', 'Necessary', 'Tough', 'Realistic', 'Iron', 'Complex', 'Vital', 'Important', 'Relevant'
        ],
        [
            'Hope', 'Reality', 'Task', 'Work', 'Duty', 'Plan', 'Issue'
        ]
    )