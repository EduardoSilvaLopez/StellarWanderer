import copy
import random
from typing import List, Optional

from galaxies.stellar_system import StellarSystem

'''The whole galaxy. We won't have more than one.'''
class Galaxy():

    def __init__(self, user_given_seed: float, saved_alterations: dict) -> None:
        self.seed: float = user_given_seed
        self.stellar_systems: List[StellarSystem] = []
        self.saved_alterations: Optional[dict] = saved_alterations
        self.is_altered: bool = saved_alterations is not None and saved_alterations != {}

    def set_altered(self) -> Galaxy:
        self.is_altered = True
        return self

    def get_alterations_key(self) -> str:
        return str(self.seed)

    def get_alterations(self) -> dict:
        ''' Galaxy alterations, exceptionally, are an empty map if none.'''
        star_alterations = dict()
        if self.is_altered:
            # Stellar systems only exist once visited, so start from the alterations loaded from the
            # savefile (systems not in memory must survive the next save), then overlay the live systems.
            if self.saved_alterations is not None:
                star_alterations = {
                    key: copy.deepcopy(value) for key, value in self.saved_alterations.items() if key != 'date_time'
                }
            for system in self.stellar_systems:
                if system.is_altered:
                    system_alterations: Optional[dict] = system.get_alterations()
                    if system_alterations is not None and len(system_alterations) > 0:
                        star_alterations[system.get_alterations_key()] = system_alterations
                    else:
                        star_alterations.pop(system.get_alterations_key(), None)
        return star_alterations

    def almanack(self) -> str:
        '''Markdown almanack: A guide of the universe as generated'''
        text: str = (
            f"# ALMANACK - The galaxy {self.seed}.\n"
            f"A guide of the universe as generated.\n"
            f"\n"
            )
        for system in self.stellar_systems:
            text += system.almanack()
        return text

    def add_stellar_system(self, x: float, y: float, z: float) -> StellarSystem:
        new_system = StellarSystem(self, x, y, z, self.saved_alterations)
        self.stellar_systems.append(new_system)
        return new_system
