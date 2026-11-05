from __future__ import annotations
import copy
import random
import math
import logging
from typing import TYPE_CHECKING, Dict, Optional

from common.vector3 import Vector3

from galaxies import seeds
from galaxies.outpost_solid import OutpostSolid, Part
from galaxies.people.role import KOMISAR, STEVEDORE, Role
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

    Outposts belong to rocky worlds (`RockyWorld.outposts`, keyed by "lon lat"). They are the settlements of the history
    of their system (galaxies/politics) after the portal base; `StellarSystem._place_settlements` makes them, so only
    the initial system has any so far.
    `surface_point_stellar` on the planet gives their surface position, and `stellar_position(t)` moves them with
    the planet. Rocks are not generated within `clearing_radius` of an outpost's centre (Km2), which grows with the
    size. From PAD_FROM_SIZE the outpost has a concrete square and a landing pad on the ground (drawn by
    graphics/outposts.py). From ANNEX_FROM_SIZE the pad is a lift platform (the same place and radius) and a newer,
    bigger block, the annex, stands behind the building and reaches ANNEX_OVERLAP into it, on bare ground: the pad's
    square does not extend under it, and the annex has no door of its own.

    Labels, the sky dot and the world map show outposts (see ObjectLabels, OutpostMarkers, WorldMap). The scanner
    can target them (`Scanner._outpost_entry`, the building box with the door on local +z, so `orientation`
    is the heading the door faces), but the beam does nothing to them yet, and neither the laser nor the ground
    affects them yet. A ship cannot fly through the building (`solid`).

    What happens inside (the staff, the repairs, the mission board) is the settlement's (galaxies/settlement.py).
    """

    kind = SettlementKind.OUTPOST
    HEIGHT = 6.0
    WIDTH = 24.0
    DEPTH = 12.0
    CLEARED_RADIUS = max(HEIGHT, WIDTH, DEPTH)  # the clearing of size 1
    CLEARED_RADIUS_WITH_PAD = 100.0  # m, the clearing from PAD_FROM_SIZE on
    CLEARED_RADIUS_WITH_ANNEX = 150.0  # m, the clearing from ANNEX_FROM_SIZE on
    PAD_FROM_SIZE = 2
    PAD_SQUARE = 50.0  # m, the side of the square; the building stands in one of its corners, PAD_MARGIN from each edge
    PAD_MARGIN = 5.0  # m
    PAD_CENTRE = (35.0, 35.0)  # m, the pad's centre from the square's corner, along the width and the door axis
    PAD_RADIUS = 10.0  # m, to the middle of the painted ring
    PAD_LINE = 0.5  # m, the ring's thickness
    ANNEX_FROM_SIZE = 3
    ANNEX_WIDTH = 30.0  # m, along local x, centred on the building
    ANNEX_DEPTH = 30.0  # m, behind the building (local -z), sharing its back wall's plane
    ANNEX_HEIGHT = 15.0  # m, half the side
    ANNEX_OVERLAP = 2.0  # m, how far the annex reaches into the building from its back wall
    ANNEX_CENTRE_Z = -DEPTH / 2.0 + ANNEX_OVERLAP - ANNEX_DEPTH / 2.0  # m, along local z
    # The teams each size adds to the staff, from that size on: a size 2 outpost has one team of stevedores, a size 3
    # one more and a Komisar (a leader on duty all the time, as at the portal base; the coordinator still decides when
    # a pilot may leave).
    SIZE_TEAMS: Dict[int, Dict[Role, int]] = {2: {STEVEDORE: 1}, 3: {STEVEDORE: 1, KOMISAR: 1}}

    def __init__(self, planet: RockyWorld, saved_alterations: Optional[dict],
                 enlargement_dates: list[datetime]) -> None:
        self.planet = planet
        self.index = len(planet.outposts)
        seed = seeds.derive(planet.seed, 'outpost', self.index)
        super().__init__(seed, enlargement_dates)
        self.my_random: random.Random = random.Random(self.seed)

        entity = self.planet.parent_orbit.parent_stellar_system.political_entity
        self.name: str = entity.generate_outpost_name(self.my_random)
        self.longitude: int = \
            0 if self.index == 0 else \
            self.my_random.randint(int(-self.planet.radius*math.pi), int(self.planet.radius*math.pi))
        self.latitude: int = self.my_random.randint(int(-self.planet.radius*math.pi/2),
                                                    int(self.planet.radius*math.pi/2))

        self.orientation: float = self.my_random.random() * 360
        building: Part = (self.WIDTH, self.HEIGHT, self.DEPTH, 0.0)
        annex: Part = (self.ANNEX_WIDTH, self.ANNEX_HEIGHT, self.ANNEX_DEPTH, self.ANNEX_CENTRE_Z)
        self._building_solid: OutpostSolid = OutpostSolid([building], self.orientation)
        self._structure_solid: OutpostSolid = OutpostSolid([building, annex], self.orientation)

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

    def get_max_maintenance(self) -> float:
        return 0.8

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

    # region Size
    @property
    def clearing_radius(self) -> float:
        """How far from its centre the ground is cleared of rocks: it grows with the pad and the annex."""
        if self.has_annex:
            return self.CLEARED_RADIUS_WITH_ANNEX
        return self.CLEARED_RADIUS_WITH_PAD if self.has_pad else self.CLEARED_RADIUS

    @property
    def has_pad(self) -> bool:
        return self.size >= self.PAD_FROM_SIZE

    @property
    def has_annex(self) -> bool:
        """Whether the annex stands behind the building. The pad is then a lift platform."""
        return self.size >= self.ANNEX_FROM_SIZE

    @property
    def solid(self) -> OutpostSolid:
        """What a ship cannot fly through, which grows with the annex."""
        return self._structure_solid if self.has_annex else self._building_solid

    def teams_now(self) -> Dict[Role, int]:
        teams = dict(self.roles)
        for size, added in self.SIZE_TEAMS.items():
            if self.size >= size:
                for role, count in added.items():
                    teams[role] = teams.get(role, 0) + count
        return teams
    # endregion

    # region Place
    def stellar_position(self, current_datetime: datetime) -> Vector3:
        """Where the outpost is, in the stellar frame, moving with its planet."""
        return self.planet.surface_point_stellar(self.longitude, self.latitude, current_datetime)

    def full_keys(self) -> str:
        """The keys that find this outpost from the galaxy: system, orbit, planet, then its moon if it is on one, and its
        own, joined by '|'."""
        orbit = self.planet.parent_orbit
        keys = [orbit.parent_stellar_system.get_alterations_key(), orbit.get_alterations_key()]
        if self.planet.parent_planet:
            keys += [self.planet.parent_planet.get_alterations_key()]
        keys += [self.planet.get_alterations_key(), self.get_alterations_key()]
        return '|'.join(keys)

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
