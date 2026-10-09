from __future__ import annotations

import logging
import random
logger = logging.getLogger(__name__)

from Galaxies.ore_mine import OreMine

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from Galaxies.km2 import Km2
    from Galaxies.rock import Rock

class OreField:
    EXTRACTION_PER_SECOND: float = 1 / 3600 # One Kg per hour, later depends on mine.

    def __init__(self):
        from Galaxies.ore_mine import OreMine
        self.parent_km2: Km2 = None
        self.longitude: int = 0
        self.latitude: int = 0
        self.radius: float = 0.0
        self.initial_ore: int = 0
        self.remaining_ore: int = 0
        self.initial_color: tuple = (0, 0, 0)
        self.color: tuple = (0, 0, 0)
        self.orientation: float = 0.0
        self.mines: List[OreMine] = list()

    @staticmethod
    def generate_new(original_rock: Rock):
        result = OreField()
        result.parent_km2 = original_rock.parent_km2
        result.longitude = original_rock.longitude
        result.latitude = original_rock.latitude
        result.radius = 0.5 * original_rock.size**1.5
        result.initial_ore = result.remaining_ore = int(original_rock.ore_per_m3() * original_rock.size**3)
        result.color = result.initial_color = tuple(min(255, value + 50) for value in original_rock.initial_color)

        my_random = random.Random(original_rock.parent_km2.seed + original_rock.latitude + original_rock.longitude + result.radius)
        result.orientation = my_random.random() * 360.0
        
        return result

    @staticmethod
    def generate_loaded(parent_km2: Km2, serialized_dict: dict) -> OreField:
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

        list_of_mines = serialized_dict.get('mines')
        result.mines = [OreMine(result, saved_attributes=mine_dict) for mine_dict in list_of_mines]
                
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

    def extract(self, amount: int) -> int:
        result = min(self.remaining_ore, amount)
        self.remaining_ore -= result
        return result