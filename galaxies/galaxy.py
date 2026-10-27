'''The whole galaxy. We won't have more than one.'''

from __future__ import annotations
import copy
from typing import TYPE_CHECKING, List, Optional

from galaxies import fixed_stars
from galaxies.constants import INITIAL_STAR_POSITION
from galaxies.star import Star, cell_of
from galaxies.stellar_system import StellarSystem

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.settlement import Settlement


class Galaxy:

    def __init__(self, user_given_seed: int, saved_alterations: dict) -> None:
        self.seed: int = user_given_seed
        # The fixed stars of the region around the initial star, keyed by their integer cell. Generated from the seed.
        self.fixed_stars: dict[tuple[int, int, int], Star] = {
            cell_of(star.position): star for star in fixed_stars.generate_region(user_given_seed)
        }
        self._fixed_star_positions: Optional[list[tuple[Star, tuple[float, float, float]]]] = None
        self.stellar_systems: List[StellarSystem] = []
        self.saved_alterations: Optional[dict] = saved_alterations
        self.is_altered: bool = saved_alterations is not None and saved_alterations != {}

    # region Stellar systems
    def add_stellar_system(self, star: Star) -> StellarSystem:
        """The stellar system of a star. The star is given, not generated; a system is only ever added once per cell."""
        existing: Optional[StellarSystem] = next((s for s in self.stellar_systems if s.star.cell == star.cell), None)
        if existing is not None:
            return existing
        new_system = StellarSystem(self, star, self.saved_alterations)
        self.stellar_systems.append(new_system)
        return new_system

    def system_of_key(self, key: str) -> Optional[StellarSystem]:
        """The stellar system with that alterations key (its star's cell, "26010 10 10"), generated if it was not yet.
        None if no fixed star is there."""
        existing: Optional[StellarSystem] = next((s for s in self.stellar_systems if s.get_alterations_key() == key),
                                                 None)
        if existing is not None:
            return existing
        star: Optional[Star] = self.fixed_stars.get(tuple(int(c) for c in key.split()))
        return self.add_stellar_system(star) if star is not None else None

    def settlement_of(self, full_keys: str) -> Settlement:
        """The settlement with these keys: a portal base (its system's key and 'portal_base'), or an outpost."""
        if full_keys.endswith('|portal_base'):
            system = self.system_of_key(full_keys.partition('|')[0])
            if system is None:
                raise KeyError(f"No stellar system {full_keys} in this galaxy.")
            return system.portal_base
        return self.outpost_of(full_keys)

    def outpost_of(self, full_keys: str) -> Outpost:
        """The outpost with these full keys (see Outpost.full_keys): system, orbit, planet, then the outpost's own
        key."""
        system_key, orbit_key, planet_key, outpost_key = full_keys.split('|')
        system = self.system_of_key(system_key)
        if system is None:
            raise KeyError(f"No stellar system {system_key} in this galaxy.")
        orbit = system.get_orbit(float(orbit_key))
        planet = next(p for p in orbit.planets if p.get_alterations_key() == planet_key)
        return planet.outposts[outpost_key]
    # endregion

    # region Fixed stars
    def fixed_star_at(self, position: tuple[float, float, float]) -> Star:
        """The fixed star in the cell that contains the galactic position (in ly). Only the region has fixed stars."""
        star: Optional[Star] = self.fixed_stars.get(cell_of(position))
        if star is None:
            raise ValueError(f"No fixed star at galactic position {position}: fixed stars exist only around the "
            f"initial star.")
        return star

    def fixed_star_positions(self) -> list[tuple[Star, tuple[float, float, float]]]:
        """Each fixed star except the initial one (the sun), with its position in the stellar frame, in meters.
        The stars do not move, so the positions are worked out once."""
        if self._fixed_star_positions is None:
            self._fixed_star_positions = [
                (star, fixed_stars.stellar_position(star.position))
                for star in self.fixed_stars.values()
                if star.position != INITIAL_STAR_POSITION
            ]
        return self._fixed_star_positions
    # endregion

    # region Alterations
    def set_altered(self) -> Galaxy:
        self.is_altered = True
        return self

    def get_alterations_key(self) -> str:
        return str(self.seed)

    def get_alterations(self) -> dict:
        ''' Galaxy alterations, exceptionally, are an empty map if none.'''
        star_alterations = {}
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
                    if system_alterations:
                        star_alterations[system.get_alterations_key()] = system_alterations
                    else:
                        star_alterations.pop(system.get_alterations_key(), None)
        return star_alterations
    # endregion
