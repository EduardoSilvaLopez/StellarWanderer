'''The whole galaxy. We won't have more than one. Its history (universe/society/politics) settles the stars up to the
game date and picks the initial star, where the game starts; the stars are made from the galaxy seed when they are
asked for (fixed_stars.py).'''

from __future__ import annotations
import copy
import logging
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from universe.structure.constants import EPOCH, SECTOR_RADIUS, SECTOR_SIZE
from universe.structure.fixed_stars import region_of, stellar_position
from universe.society.politics.expansion_history import ExpansionHistory, SystemHistory
from universe.society.politics.tidings import Tidings
from universe.bodies.star import Star, cell_of
from universe.structure.stellar_system import StellarSystem

if TYPE_CHECKING:
    from universe.artifacts.settlements.outpost import Outpost
    from universe.artifacts.settlements.settlement import Settlement

logger = logging.getLogger(__name__)


class Galaxy:

    def __init__(self, user_given_seed: int, saved_alterations: dict, date_time: datetime) -> None:
        self.seed: int = user_given_seed
        self.history: ExpansionHistory = ExpansionHistory(user_given_seed, date_time)
        self.history.log_results()
        # The history picks the initial star: the star of the system the game starts in (it gives the system its entity
        # and its settlements; the other systems are only what the history says).
        self.initial_history: SystemHistory = self.history.initial_system(EPOCH)
        self.initial_star: Star = self.initial_history.star
        self.initial_cell: tuple[int, int, int] = self.initial_star.cell
        logger.info(f"Initial star of galaxy {user_given_seed}: {self.initial_star.name} at "
                    f"{self.initial_star.position} ly.")
        self.stars = self.history.stars
        self.tidings: Tidings = Tidings(self.history)
        # The sky of each system visited, by its star's cell (see fixed_star_positions)
        self._fixed_star_positions: dict[tuple[int, int, int], list[tuple[Star, tuple[float, float, float]]]] = {}
        self.stellar_systems: List[StellarSystem] = []
        self.saved_alterations: Optional[dict] = saved_alterations
        self.is_altered: bool = saved_alterations is not None and saved_alterations != {}

    # region Stellar systems
    def add_stellar_system(self, star: Star) -> StellarSystem:
        """The stellar system of a star. The star is given, not generated; a system is only ever added once per cell."""
        existing: Optional[StellarSystem] = next((s for s in self.stellar_systems if s.star.cell == star.cell), None)
        if existing is not None:
            return existing
        if self.saved_alterations is None:
            new_system = StellarSystem(self, star, {})
        else:
            new_system = StellarSystem(self, star, self.saved_alterations)
        self.stellar_systems.append(new_system)
        return new_system

    def history_of(self, cell: tuple[int, int, int]) -> Optional[SystemHistory]:
        """The history of the system of a star's cell, or None if the history does not settle that star by the game
        date. The system makes its own portal base and outposts from it."""
        return self.history.system_at(cell)

    def existing_system_of_key(self, key: str) -> Optional[StellarSystem]:
        """The stellar system with that alterations key if it has been generated, else None (nothing is generated)."""
        return next((s for s in self.stellar_systems if s.get_alterations_key() == key), None)

    def system_of_key(self, key: str) -> Optional[StellarSystem]:
        """The stellar system with that alterations key (its star's cell, "26010 10 10"), generated if it was not yet.
        None if no star is there."""
        existing = self.existing_system_of_key(key)
        if existing is not None:
            return existing
        cell_x, cell_y, cell_z = (int(c) for c in key.split())
        star: Optional[Star] = self.stars.star_at((cell_x, cell_y, cell_z))
        return self.add_stellar_system(star) if star is not None else None

    def settlement_of(self, full_keys: str) -> Settlement:
        """The settlement with these keys: a portal base (its system's key and 'portal_base'), or an outpost."""
        if full_keys.endswith('|portal_base'):
            system = self.system_of_key(full_keys.partition('|')[0])
            if system is None:
                raise KeyError(f"No stellar system {full_keys} in this galaxy.")
            if system.portal_base is None:
                raise KeyError(f"No portal base in stellar system {full_keys}.")
            return system.portal_base
        return self.outpost_of(full_keys)

    def outpost_of(self, full_keys: str) -> Outpost:
        """The outpost with these full keys (see Outpost.full_keys): system, orbit, planet, then its moon if it is on one,
        and the outpost's own key."""
        system_key, orbit_key, planet_key, *rest = full_keys.split('|')
        system = self.system_of_key(system_key)
        if system is None:
            raise KeyError(f"No stellar system {system_key} in this galaxy.")
        orbit = system.get_orbit(float(orbit_key))
        if orbit is None:
            raise KeyError(f"No orbit {orbit_key} in stellar system {system_key}.")
        world = next(p for p in orbit.planets if p.get_alterations_key() == planet_key)
        if len(rest) == 2:
            moon_key, outpost_key = rest
            world = next(m for m in world.moons if m.get_alterations_key() == moon_key)
        else:
            (outpost_key,) = rest
        return world.outposts[outpost_key]
    # endregion

    # region Fixed stars
    def fixed_star_at(self, position: tuple[float, float, float]) -> Star:
        """The fixed star in the cell that contains the galactic position (in ly)."""
        star: Optional[Star] = self.stars.star_at(cell_of(position))
        if star is None:
            raise ValueError(f"No star at galactic position {position}.")
        return star

    def fixed_star_positions(self, origin: Star) -> list[tuple[Star, tuple[float, float, float]]]:
        """Each star of the sky of the system of `origin` (the sectors around it) except `origin` itself, with its
        position in that system's stellar frame, in meters. The stars do not move, so the list is worked out once for
        each system, and it is the same list every time (its identity says the sky has not changed)."""
        positions = self._fixed_star_positions.get(origin.cell)
        if positions is None:
            centre = region_of(origin.position, SECTOR_SIZE)
            positions = self._fixed_star_positions[origin.cell] = [
                (star, stellar_position(star.position, origin.position))
                for star in self.stars.stars_around(centre, SECTOR_RADIUS)
                if star.cell != origin.cell
            ]
        return positions
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
