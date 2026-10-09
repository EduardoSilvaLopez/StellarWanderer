from typing import List, Optional

from Galaxies.stellar_system import StellarSystem

class Galaxy():

    def __init__(self, seeds_delta: int, saved_alterations: dict) -> None:
        self.seed: int = seeds_delta # The galaxy's seed is just the seed_delta from the user.
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
        alterations = dict()
        if self.is_altered:
            for system in self.stellar_systems:
                if system.is_altered:
                    alterations[system.get_alterations_key()] = system.get_alterations()
        return alterations

    def add_stellar_system(self, x: int, y: int, z: int) -> StellarSystem:
        new_system = StellarSystem(self, x, y, z, self.saved_alterations)
        self.stellar_systems.append(new_system)
        return new_system
