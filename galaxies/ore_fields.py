from __future__ import annotations

import logging
import random

from galaxies import seeds
from galaxies.ore_mine import OreMine

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from galaxies.km2 import Km2
    from galaxies.rock import Rock

logger = logging.getLogger(__name__)

class OreField:
    EXTRACTION_PER_SECOND: float = 1 / 3600  # One Kg per hour, later depends on mine.

    def __init__(self) -> None:
        self.parent_km2: Km2 = None
        self.longitude: int = 0
        self.latitude: int = 0
        self.radius: float = 0.0
        self.initial_ore: int = 0
        self.remaining_ore: int = 0
        self.initial_color: tuple = (0, 0, 0)
        self.color: tuple = (0, 0, 0)
        self.orientation: float = 0.0
        self.mines: List[OreMine] = []

    @staticmethod
    def from_rock(original_rock: Rock) -> OreField:
        """The field a molten ore-rich rock leaves."""
        result = OreField()
        result.parent_km2 = original_rock.parent_km2
        result.longitude = original_rock.longitude
        result.latitude = original_rock.latitude
        result.radius = original_rock.size**1.5
        result.initial_ore = result.remaining_ore = int(original_rock.ore_per_m3() * original_rock.size**3)
        result.color = result.initial_color = tuple(min(255, value + 50) for value in original_rock.initial_color)

        my_random = random.Random(
            seeds.derive(original_rock.parent_km2.seed, 'ore_field', original_rock.longitude, original_rock.latitude))
        result.orientation = my_random.random() * 360.0
        result.parent_km2.set_altered()  # Any ore field is an alteration by definition.

        return result

    @staticmethod
    def deserialize(parent_km2: Km2, serialized_dict: dict) -> OreField:
        result = OreField()
        result.parent_km2 = parent_km2
        result.longitude = serialized_dict['longitude']
        result.latitude = serialized_dict['latitude']
        result.radius = serialized_dict['radius']
        result.initial_ore = serialized_dict['initial_ore']
        result.remaining_ore = serialized_dict['remaining_ore']
        result.initial_color = tuple(serialized_dict['initial_color'])
        result.color = tuple(serialized_dict['color'])
        result.orientation = serialized_dict['orientation']
        result.mines = [OreMine(result, saved_attributes=mine_dict) for mine_dict in serialized_dict['mines']]
        return result

    def serialize(self) -> dict:
        return {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'radius': self.radius,
            'initial_ore': self.initial_ore,
            'remaining_ore': self.remaining_ore,
            'initial_color': self.initial_color,
            'color': self.color,
            'orientation': self.orientation,
            'mines': [m.serialize() for m in self.mines]
            }

    def extract(self, extraction_power: int, max_extracted: int) -> int:
        ''' The field aspects: more extraction with more remaining per area'''
        prevalence_factor = self.remaining_ore / self.radius**2
        result = min(self.remaining_ore, prevalence_factor * extraction_power, max_extracted)
        if result > 0:
            self.remaining_ore -= result
        return result
