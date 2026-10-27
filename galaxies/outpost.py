from __future__ import annotations
import copy
import random
import math
import logging
from typing import TYPE_CHECKING, Optional

from common.vector3 import Vector3

from galaxies import seeds
from galaxies.rocky_world import RockyWorld
from galaxies.settlement_kind import SettlementKind
from galaxies.world_surface import SurfaceType
from galaxies.settlement import (  # re-exported: the outposts' staff rota (SHIFT_HOURS) is read from here too
    DATE_FORMAT, SHIFT_HOURS, Settlement,
)

if TYPE_CHECKING:
    from datetime import datetime

    from galaxies.body import Body
    from galaxies.stellar_system import StellarSystem

__all__ = ['Outpost', 'DATE_FORMAT', 'SHIFT_HOURS']

logger = logging.getLogger(__name__)


class Outpost(Settlement):
    """A two-level building on a planet's surface (24 m x 12 m x 6 m, two levels of 3 m).

    Outposts belong to planets (`RockyWorld.outposts`, keyed by "lon lat"; the initial planet always has at least one).
    `surface_point_stellar` on the planet gives their surface position, and `stellar_position(t)` moves them with
    the planet. Rocks are not generated within CLEARED_RADIUS of an outpost's centre (Km2).

    Labels, the sky dot and the world map show outposts (see ObjectLabels, OutpostMarkers, WorldMap). The scanner
    can target them (`Scanner._outpost_entry`, the building box with the door on local +z, so `orientation`
    is the heading the door faces), but the beam does nothing to them yet, and neither the laser nor the ground
    affects them yet.

    What happens inside (the staff, the repairs, the mission board) is the settlement's (galaxies/settlement.py).
    """

    kind = SettlementKind.OUTPOST
    HEIGHT = 6.0
    WIDTH = 24.0
    DEPTH = 12.0
    CLEARED_RADIUS = max(HEIGHT, WIDTH, DEPTH)

    def __init__(self, planet: RockyWorld, saved_alterations: dict) -> None:
        self.planet = planet
        self.index = len(planet.outposts)
        seed = seeds.derive(planet.seed, 'outpost', self.index)
        super().__init__(seed)
        self.my_random: random.Random = random.Random(self.seed)

        entity = self.planet.parent_orbit.parent_stellar_system.political_entity
        self.name: str = entity.generate_outpost_name(self.my_random)
        self.longitude: int = \
            0 if self.index == 0 else \
            self.my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = self.my_random.randint(int(-self.planet.radius*math.pi/2),
                                                    int(self.planet.radius*math.pi/2))

        self.orientation: float = self.my_random.random() * 360

        self.saved_alterations: Optional[dict] = None
        if saved_alterations:
            my_alterations = saved_alterations.get(self.get_alterations_key())
            if my_alterations:
                self.saved_alterations = copy.deepcopy(my_alterations)
                self._read_alterations(self.saved_alterations)
                self.set_altered()
        self._log_generation()

    def _log_generation(self) -> Outpost:
        logger.info("OUTPOST created")
        logger.info(f"- Index {self.index}, Lon: {self.longitude}, Lat: {self.latitude}")
        logger.info(f"- Seed {self.seed}")
        return self

    # region Alterations
    def get_alterations_key(self) -> str:
        return str(self.longitude) + " " + str(self.latitude)

    def get_alterations(self) -> dict:
        alterations: dict = {}
        self._alterations_of_visits(alterations)
        if self.last_visited is not None:
            # Nobody on duty yet when the ship has not been near since the load: the saved list is kept.
            on_duty = [person.seed for person in self.on_duty_list()]
            if not on_duty:
                on_duty = (self.saved_alterations or {}).get('staff_on_duty', [])
            if on_duty:
                alterations['staff_on_duty'] = on_duty
        if not alterations:
            return None
        return alterations

    def _parent_altered(self) -> None:
        self.planet.set_altered()
    # endregion

    # region Screen and saves
    def inside_key(self) -> str:
        return self.full_keys()

    @property
    def stellar_system(self) -> StellarSystem:
        return self.planet.parent_orbit.parent_stellar_system

    @property
    def body(self) -> Body:
        return self.planet

    def stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return self.planet.calculate_stellar_velocity(current_datetime)

    @property
    def plane_distance(self) -> float:
        return self.planet.parent_orbit.distance_from_star

    def needs_water(self) -> bool:
        return self.planet.surface_type is not SurfaceType.ICE

    def residency_line(self) -> str:
        return (f"Outpost {self.name}, planet {self.planet.name}"
                f", {self.planet.parent_orbit.parent_stellar_system.name}")

    def place_details(self) -> list[str]:
        system = self.planet.parent_orbit.parent_stellar_system
        return [self.planet.name, system.star.name, system.political_entity.name]
    # endregion

    # region Place
    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the outpost is, in the stellar frame, moving with its planet."""
        return self.planet.surface_point_stellar(self.longitude, self.latitude, current_datetime)

    def full_keys(self) -> str:
        """The keys that find this outpost from the galaxy: system, orbit, planet and its own, joined by '|'."""
        orbit = self.planet.parent_orbit
        return '|'.join((orbit.parent_stellar_system.get_alterations_key(), orbit.get_alterations_key(),
                         self.planet.get_alterations_key(), self.get_alterations_key()))

    def address(self) -> str:
        """User-friendly address of the outpost."""
        world = self.planet
        place: str = f"{self.name}, "
        if world.parent_planet:
            place += f"moon {world.name}, planet {world.parent_planet.name}"
        else:
            place += f"planet {world.name}"
        return f"{place}, {world.parent_orbit.parent_stellar_system.name}"
    # endregion
