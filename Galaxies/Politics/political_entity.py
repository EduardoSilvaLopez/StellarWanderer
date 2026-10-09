from __future__ import annotations
import os
import pygame
from typing import Optional


class PoliticalEntity:
    def __init__(self, name: str, color: tuple, icon_filename: str) -> None:
        self.name: str = name
        self.color: tuple = color
        self.icon: Optional[pygame.Surface] = None
        self._load_icon(icon_filename)
        self.titles = {
            float('-inf'): 'Prisioner',
            -100: 'Dependent',
            -10: 'Student',
            0: 'Citizen',
            10: 'Comrade',
            100: 'Speaker',
            1000: 'Champion',
            10000: 'Premier'
        }

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

THOSE_WHO_SHARE: PoliticalEntity = PoliticalEntity(
        "Those-Who-Share",
        (192, 0, 0),
        "PoliticalEntity.1.png"
    )