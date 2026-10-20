from __future__ import annotations

import copy
import math
import numpy as np
import random
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

import logging
from common.units import format_compact_distance
import galaxies.constants
import knowledge
from galaxies.body import Body
from galaxies.km2 import Km2
from galaxies.rock import Rock
from galaxies.world_surface import SurfaceType, equilibrium_temperature, generate_surface
from common.vector3 import Vector3

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.orbit import Orbit
    from galaxies.stellar_system import StellarSystem
    from spaceships.ship import Ship

logger = logging.getLogger(__name__)


class World(Body):
    '''The generation is full of heuristic but playtested, hopefully realistic, factors.

    Orbits: every orbital period follows Kepler's third law around the parent's mass: a moon around its planet
    (`mass`, from the radius and EARTH_DENSITY), a planet around its star (`StellarSystem.mass`, estimated from the
    star's radius). Each orbit is an ellipse whose semi-major axis is `distance_to_parent`, with an `eccentricity`, an
    `inclination` to the reference plane, a longitude of the ascending node and an argument of periapsis. These four
    are drawn after the other values in the constructor, so adding them changed no earlier value. Every world starts
    `initial_degrees_in_orbit` from the periapsis direction at EPOCH, as a mean anomaly (the true angle for a circular
    orbit). The spin axis stays on the reference z axis, so the inclination of a planet's orbit is its axial tilt
    (seasons); a moon's inclination is relative to its planet's equator. A planet's moons orbit inside the stable part of
    its Hill sphere (`moon_limit`, see `moon_limit_in_radii`), and a planet too close to its star has none. A world whose
    spin the tides have tied to its orbit (`is_tidally_locked`: every moon, and the close planets) either turns once per orbit
    and keeps the same side to its parent, or, if `is_resonant`, turns three times for two orbits. `local_day_fraction` is the solar day at longitude 0 (0 = noon); the game's date and time
    always start at EPOCH 00:00:00.

    Surface: `equilibrium_temperature` (K) from the star's light and the distance, then `surface_type` and `surface_colour`
    from it and the seed (see world_surface.py); they are drawn last, after the orbit's values. The colour is what the
    graphics light (LitWorlds, SurfaceLight); the type and the temperature are in the knowledge base (`markdown`).

    A world's position and velocity are pure functions of the date, memoised for the date of the last call only (one
    entry each), so everything drawn or computed in a frame shares one evaluation per world.
    '''

    is_world = True

    WORLD_MIN_RADIUS = 300000  # Spherical celestial object.
    SURROUNDINGS_RADIUS = 2 * Km2.SIZE
    GRAVITATIONAL_CONSTANT = 6.674e-11  # m^3 kg^-1 s^-2
    EARTH_DENSITY = 5514.0  # kg/m^3, assumed for every world (planets and moons alike)

    # Orbit shape and tilt: |N(0, sigma)|, capped. A moon's distance is never below 3 planet radii, so with the
    # eccentricity capped at 0.3 its periapsis stays above 2.1 planet radii.
    ECCENTRICITY_SIGMA = 0.1
    MAX_ECCENTRICITY = 0.3
    PLANET_INCLINATION_SIGMA_DEGREES = 10.0
    PLANET_MAX_INCLINATION_DEGREES = 30.0
    MOON_INCLINATION_SIGMA_DEGREES = 5.0
    MOON_MAX_INCLINATION_DEGREES = 20.0

    # Moons: the closest is MOON_MIN_DISTANCE_RADII planet radii away (outside the Roche limit, 2.44 radii for worlds of
    # one density, and clear of the planet's bind zone). The farthest is inside the planet's Hill sphere: the region
    # around it, of radius a (m / 3M)^(1/3) (a: its distance to its star, m: its mass, M: the star's), where its pull wins
    # over the star's. A prograde moon orbit stays stable out to about half of it (Domingos et al. 2006).
    MOON_MIN_DISTANCE_RADII = 3.0
    MOON_STABLE_HILL_FRACTION = 0.5
    # A planet has moons only if their stable region reaches at least this far, planet radii: a band wider than the
    # minimum distance, or its moons would crowd at one distance.
    MOON_MIN_ROOM_RADII = 6.0

    # Tidal locking: the parent's tides slow a world's spin until it is tied to its orbit. The time is the standard
    # estimate (Gladman et al. 1996) for a world of EARTH_DENSITY, from its drawn spin, with these constants. A world is
    # tied if that time is within TIDAL_LOCK_TIME_LIMIT (a few billion years). It is tied to a 1:1 lock (one turn per
    # orbit, the same side to its parent), or, for a planet of an eccentric orbit, sometimes to a 3:2 resonance (three
    # turns for two orbits, as Mercury): the tides capture it there (Goldreich and Peale 1966).
    MOMENT_OF_INERTIA_FACTOR = 0.33  # moment of inertia = this times m R^2
    TIDAL_QUALITY_FACTOR = 100.0
    TIDAL_LOVE_NUMBER = 0.3
    TIDAL_LOCK_TIME_LIMIT = 1.5e17  # s: a few billion years
    RESONANCE_MIN_ECCENTRICITY = 0.1  # a planet less eccentric than this stays in the 1:1 lock
    RESONANCE_CHANCE = 0.5  # of a planet at least this eccentric being caught in the 3:2 resonance rather than the lock
    RESONANCE_TURNS_PER_ORBIT = 1.5  # the 3:2 resonance: three turns for two orbits

    # Eccentric anomalies, in radians, either side of the world's own: where orbit_points adds points to follow the curve closely.
    ORBIT_NEAR_ANOMALIES = (1e-4, 2.5e-4, 6e-4, 1.5e-3, 4e-3, 1e-2, 2.5e-2, 6e-2)

    # region Generation
    @staticmethod
    def moon_limit_in_radii(distance_to_star: float, star_mass: float) -> float:
        """The farthest a moon's orbit (semi-major axis) can be from a planet, in planet radii, when it is
        `distance_to_star` metres from a star of `star_mass` kilograms: MOON_STABLE_HILL_FRACTION of its Hill sphere.
        The sphere is taken at the planet's periapsis and the moon's apoapsis at the largest eccentricities
        (MAX_ECCENTRICITY), as neither is known yet. Every world has EARTH_DENSITY, so a planet's mass grows with
        its radius cubed, and the Hill sphere in planet radii does not depend on its size: the limit is linear in the distance."""
        hill_in_radii = distance_to_star * (1.0 - World.MAX_ECCENTRICITY) \
            * (4.0 * math.pi * World.EARTH_DENSITY / (9.0 * star_mass)) ** (1.0 / 3.0)
        return World.MOON_STABLE_HILL_FRACTION * hill_in_radii / (1.0 + World.MAX_ECCENTRICITY)

    def __init__(self, parent_orbit: Orbit = None, parent_planet: World = None, saved_alterations: dict = None) -> None:
        self._position_cache: Optional[Tuple[datetime, Vector3]] = None
        self._velocity_cache: Optional[Tuple[datetime, Vector3]] = None

        # A parent_planet? Then it is a moon.
        if parent_planet:
            self.parent_planet: World = parent_planet
            self.parent_orbit: Orbit = parent_planet.parent_orbit
            self.index = len(self.parent_planet.moons)
            seed_origin: float = self.parent_planet.seed
        else:
            self.parent_planet: World = None
            self.parent_orbit: Orbit = parent_orbit
            self.index = len(self.parent_orbit.planets)
            seed_origin: float = self.parent_orbit.seed

        self.seed: float = (seed_origin + self.index + 1) % galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.name: str =\
            (self.parent_planet.name + "-" + str(self.index + 1)).capitalize()\
            if self.parent_planet\
            else self._generate_planet_name(my_random)

        self.radius: float =\
            self._generate_moon_radius(my_random)\
            if self.parent_planet\
            else self._generate_planet_radius(my_random)

        if self.parent_planet:
            self.distance_to_parent: int = self._generate_moon_distance(my_random)
        else:
            self.distance_to_parent: int = int(parent_orbit.distance_from_star)

        self.initial_degrees_in_orbit: float = my_random.random() * 360.0

        self.mass: float = 4.0 / 3.0 * math.pi * self.radius ** 3 * World.EARTH_DENSITY

        # Kepler's third law around the parent, a planet or the star (two-body: both masses count).
        parent_mass: float = self.parent_planet.mass if self.parent_planet else self.stellar_system.star.mass
        self.orbital_period: float = math.tau * math.sqrt(
            self.distance_to_parent ** 3 / (World.GRAVITATIONAL_CONSTANT * (parent_mass + self.mass))
        )

        # The farthest a moon's orbit can be from this planet: inside its Hill sphere (see moon_limit_in_radii).
        self.moon_limit: float = 0.0
        if not self.parent_planet:
            self.moon_limit = World.moon_limit_in_radii(self.distance_to_parent, self.stellar_system.star.mass) * self.radius

        self.rotation_period: float = self._generate_rotation_period(my_random)
        self.is_tidally_locked: bool = self._is_tidally_locked(parent_mass)
        if self.is_tidally_locked:
            self.rotation_period = self.orbital_period  # the 1:1 lock, unless the resonance is drawn below

        self.rocks_prevalence: float = my_random.random()
        self.ore_prevalence: float = (1.0 - Rock.ORE_RICH_THRESHOLD) * my_random.random()
        if self.parent_planet is not None and self.parent_planet._is_initial_planet():
            # Why were you sent here...? :D
            self.rocks_prevalence = 0.5 + 0.5 * my_random.random()
            self.ore_prevalence = (1.0 - Rock.ORE_RICH_THRESHOLD) ** 0.66 * my_random.random()

        # Alterations:
        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()

        own_alterations: Optional[dict] = None
        if saved_alterations is not None and alterations_key in saved_alterations:
            # come from an orbit
            own_alterations = saved_alterations.get(alterations_key)
        elif saved_alterations is not None and 'moons' in saved_alterations:
            # come from a planet
            own_alterations = saved_alterations['moons'].get(alterations_key)

        if own_alterations is not None:
            self.is_altered = True
            self.saved_alterations = own_alterations
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        # Outposts (planets only): one is generated at least on the initial planet.
        from galaxies.outpost import Outpost
        self.outposts: dict = {}
        if not self.parent_planet:
            outposts_count = int(abs(my_random.gauss(1.5, 0.5)))
            if self._is_initial_planet() and outposts_count <= 0:
                outposts_count = 1

            all_outposts_alterations = self.saved_alterations.get('outposts')\
                if self.saved_alterations else None

            for _ in range(outposts_count):
                # Added one by one, so each outpost sees the previous ones when it takes its index.
                outpost = Outpost(self, all_outposts_alterations)
                self.outposts[outpost.get_alterations_key()] = outpost  # May overwrite, it is intentional.

        # Register mines in its Km2:
        self.registered_mines: List[tuple] = []
        if self.saved_alterations and 'Km2s' in self.saved_alterations:
            self.registered_mines.extend(
                (mine_dict['longitude'], mine_dict['latitude'])
                for km2_alt in self.saved_alterations['Km2s'].values() if 'ore_fields' in km2_alt
                for field_dict in km2_alt['ore_fields'] if 'mines' in field_dict
                for mine_dict in field_dict['mines'])

        # Moons:
        self.moons: List[World] = []
        if not self.parent_planet:
            moons_count = -1
            while moons_count < 0:
                moons_count = int(my_random.gauss(2.0, 1.0))
            # Initial moon's clause.
            if not moons_count and self._is_initial_planet():
                moons_count = 1
            # A planet too close to its star has no room for a stable moon: it has none. (The layout of the initial
            # system leaves room for the initial planet's moon.)
            if not self._is_initial_planet() and self.moon_limit < World.MOON_MIN_ROOM_RADII * self.radius:
                moons_count = 0
            for _ in range(moons_count):
                self.moons.append(World(parent_orbit=None, parent_planet=self, saved_alterations=self.saved_alterations))

        self._generate_orbit_orientation(my_random)  # no value drawn above depends on it

        # Drawn after the orbit, so adding them changed no earlier value. A moon is as far from the star as its planet.
        planet = self.parent_planet if self.parent_planet else self
        self.equilibrium_temperature: float = equilibrium_temperature(self.stellar_system.star, planet.distance_to_parent)
        self.surface_type: SurfaceType
        self.surface_colour: Tuple[int, int, int]
        self.surface_type, self.surface_colour = generate_surface(my_random, self.equilibrium_temperature)

        # Drawn last, so no value above changed: a tied planet may be in the 3:2 resonance instead of the 1:1 lock.
        self.is_resonant: bool = self._is_resonant(my_random)
        if self.is_resonant:
            self.rotation_period = self.orbital_period / World.RESONANCE_TURNS_PER_ORBIT

        self.km2s: List[Km2] = []
        self._learn()
        self._log_creation()

    @property
    def stellar_system(self) -> StellarSystem:
        return self.parent_orbit.parent_stellar_system

    def _learn(self) -> None:
        """Adds this world to the player's knowledge (see knowledge.py): a planet with its (so far empty) moons, a moon in its planet."""
        system_key: str = self.stellar_system.get_alterations_key()
        orbit_key: str = self.parent_orbit.get_alterations_key()
        if self.parent_planet:
            knowledge.current_knowledge.learn_moon(system_key, orbit_key, self.parent_planet.get_alterations_key(), self.get_alterations_key())
        else:
            knowledge.current_knowledge.learn_planet(system_key, orbit_key, self.get_alterations_key())

    def _is_initial_planet(self) -> bool:
        return self.parent_planet is None\
            and self.parent_orbit.number == 3.0\
            and (self.stellar_system.x, self.stellar_system.y, self.stellar_system.z) == galaxies.constants.INITIAL_STAR_POSITION

    def _generate_planet_name(self, my_random: random.Random) -> str:
        """Generate a random name for the world."""
        vocals = "aeiouaeio"  # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for _ in range(1, my_random.randint(2, 5)):
            if my_random.random() < 0.5:
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if my_random.random() < 0.5:
                name += my_random.choice(consonants)

        return name.capitalize()

    def _generate_planet_radius(self, my_random: random.Random) -> int:
        result: float = 0.0
        while result < World.WORLD_MIN_RADIUS:
            result = my_random.gauss(5000000, 1000000)
        return int(result)

    def _generate_moon_radius(self, my_random: random.Random) -> int:
        result: float = 0.0
        while result < World.WORLD_MIN_RADIUS:
            result = 2 ** my_random.gauss(1.0, 1.0) * self.parent_planet.radius / 100.0
        return int(result)

    def _generate_moon_distance(self, my_random: random.Random) -> int:
        """The moon's distance to its planet: a draw of a few hundred moon radii, never under MOON_MIN_DISTANCE_RADII planet
        radii and never beyond the planet's moon_limit (its Hill sphere). A draw beyond the limit is placed inside the
        stable region with the fractional part of the same draw, so no draw is added and every later value of the
        moon stays what it was, and moons do not pile up at the limit."""
        lowest = World.MOON_MIN_DISTANCE_RADII * self.parent_planet.radius
        highest = self.parent_planet.moon_limit
        result = 0.0
        draw = 0.0
        while result < lowest:
            draw = my_random.gauss(3, 1)
            result = int(draw * 250.0 * self.radius)
        if result > highest:
            # (If the stable region is narrower than the minimum, only the initial planet gets here: it gets the minimum.)
            share = draw - math.floor(draw)
            result = int(lowest + max(0.0, highest - lowest) * (0.3 + 0.7 * share))
        return result

    def _generate_rotation_period(self, my_random: random.Random) -> float:
        """The spin before tidal locking (see _is_tidally_locked): about a day, or a month for a moon."""
        result: float = 0.0
        if self.parent_planet:
            result = 1 / my_random.gauss(1.0 / (60 * 60 * 24 * 28), 0.2 / (60 * 60 * 24 * 28))
        else:
            result = 1 / my_random.gauss(1.0 / (60 * 60 * 24), 0.2 / (60 * 60 * 24))
        return int(result)

    def _is_tidally_locked(self, parent_mass: float) -> bool:
        """True if the parent's tides would have slowed the spin (the drawn rotation_period) to the orbit's within
        TIDAL_LOCK_TIME_LIMIT. The time grows with the sixth power of the distance, so close planets and every moon are
        locked, and far ones are not."""
        initial_spin: float = math.tau / self.rotation_period
        density_term: float = 4.0 / 3.0 * math.pi * World.EARTH_DENSITY  # m / R^3, the same for every world
        lock_time: float = (
            World.MOMENT_OF_INERTIA_FACTOR * initial_spin * self.distance_to_parent ** 6 * density_term
            * World.TIDAL_QUALITY_FACTOR
            / (3.0 * World.GRAVITATIONAL_CONSTANT * parent_mass ** 2 * World.TIDAL_LOVE_NUMBER)
        )
        return lock_time < World.TIDAL_LOCK_TIME_LIMIT

    def _is_resonant(self, my_random: random.Random) -> bool:
        """True if a tied planet is caught in the 3:2 resonance rather than the 1:1 lock: only a planet (not a moon) of an
        eccentric enough orbit (RESONANCE_MIN_ECCENTRICITY), and then with RESONANCE_CHANCE. Drawn only in those cases."""
        if not self.is_tidally_locked or self.parent_planet or self.eccentricity < World.RESONANCE_MIN_ECCENTRICITY:
            return False
        return my_random.random() < World.RESONANCE_CHANCE

    def _generate_orbit_orientation(self, my_random: random.Random) -> None:
        """Eccentricity, inclination, node longitude and periapsis argument of the orbit around the parent."""
        if self.parent_planet:
            sigma, limit = World.MOON_INCLINATION_SIGMA_DEGREES, World.MOON_MAX_INCLINATION_DEGREES
        else:
            sigma, limit = World.PLANET_INCLINATION_SIGMA_DEGREES, World.PLANET_MAX_INCLINATION_DEGREES
        self.eccentricity: float = min(abs(my_random.gauss(0.0, World.ECCENTRICITY_SIGMA)), World.MAX_ECCENTRICITY)
        self.inclination: float = math.radians(min(abs(my_random.gauss(0.0, sigma)), limit))
        self.node_longitude: float = my_random.random() * math.tau
        self.periapsis_argument: float = my_random.random() * math.tau
        self._set_orbit_axes()

    def _set_orbit_axes(self) -> None:
        """The orbit's two in-plane axes in the reference frame: towards the periapsis, and a quarter turn on."""
        cos_node, sin_node = math.cos(self.node_longitude), math.sin(self.node_longitude)
        cos_incl, sin_incl = math.cos(self.inclination), math.sin(self.inclination)
        cos_peri, sin_peri = math.cos(self.periapsis_argument), math.sin(self.periapsis_argument)
        self._periapsis_axis: Tuple[float, float, float] = (
            cos_node * cos_peri - sin_node * sin_peri * cos_incl,
            sin_node * cos_peri + cos_node * sin_peri * cos_incl,
            sin_peri * sin_incl,
        )
        self._quarter_axis: Tuple[float, float, float] = (
            -cos_node * sin_peri - sin_node * cos_peri * cos_incl,
            -sin_node * sin_peri + cos_node * cos_peri * cos_incl,
            cos_peri * sin_incl,
        )
    # endregion

    # region Alterations
    def set_altered(self) -> World:
        self.is_altered = True
        if self.parent_planet and not self.parent_planet.is_altered:
            self.parent_planet.set_altered()
        elif not self.parent_planet and not self.parent_orbit.is_altered:
            self.parent_orbit.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.index)

    def get_alterations(self) -> Optional[dict]:
        if not self.is_altered:
            return None

        logger.debug(f"get_alterations() Called for {self.name}.")
        result: Optional[dict] = {}

        # Km2 objects only exist near the player, so start from the alterations loaded from the
        # savefile (Km2s not in memory must survive the next save), then overlay the live Km2s.
        km2_alterations: dict = {}
        if self.saved_alterations is not None and self.saved_alterations.get('Km2s') is not None:
            km2_alterations = copy.deepcopy(self.saved_alterations['Km2s'])
        for km2 in self.km2s:
            if km2.is_altered:  # There is no "no longer altered"
                km2_alt = km2.get_alterations()
                if km2_alt:
                    km2_alterations[km2.get_alterations_key()] = km2_alt
        if km2_alterations:
            result['Km2s'] = km2_alterations

        moon_alterations: dict = {}
        for moon in self.moons:
            one_moon_alterations: Optional[dict] = moon.get_alterations()
            if one_moon_alterations:
                moon_alterations[moon.get_alterations_key()] = one_moon_alterations
        if moon_alterations:
            result['moons'] = moon_alterations

        all_outposts_alterations: dict = {}
        for alt_key, outpost in self.outposts.items():
            outpost_alterations: Optional[dict] = outpost.get_alterations()
            if outpost_alterations:
                all_outposts_alterations[alt_key] = outpost_alterations
        if all_outposts_alterations:
            result['outposts'] = all_outposts_alterations

        if not result:
            return None
        return result
    # endregion

    # region Km2s and outposts
    def get_km2_at(self, longitude: float, latitude: float) -> Optional[Km2]:
        """Find the right Km2 for a given point... if it exists."""
        new_longitude = (longitude // Km2.SIZE) * Km2.SIZE
        new_latitude = (latitude // Km2.SIZE) * Km2.SIZE
        return next(
            (km2 for km2 in self.km2s if km2.longitude == new_longitude and km2.latitude == new_latitude),
            None
            )

    def update_surroundings(self, center_alt: float, center_lon: float, center_lat: float, game_date_time: datetime) -> None:
        """
        1. Ensure the surroundings of a point exist and are updated.
        2. Ensure everything else loaded is *not longer* updated.
        """
        count_before = len(self.km2s)

        longitude: int = int((center_lon // Km2.SIZE) * Km2.SIZE)
        latitude: int = int((center_lat // Km2.SIZE) * Km2.SIZE)

        to_stop_updating: List[Km2] = self.km2s.copy()

        if center_alt <= World.SURROUNDINGS_RADIUS:
            surrounding_chunks = World.SURROUNDINGS_RADIUS // Km2.SIZE
            for lon_delta in range(-surrounding_chunks, surrounding_chunks + 1):
                for lat_delta in range(-surrounding_chunks, surrounding_chunks + 1):
                    target_longitude = longitude + lon_delta * Km2.SIZE
                    target_latitude = latitude + lat_delta * Km2.SIZE
                    target_km2 = self.get_km2_at(target_longitude, target_latitude)
                    if target_km2 is None:
                        self.km2s.append(Km2(self, target_longitude, target_latitude, self.saved_alterations))
                        continue
                    to_stop_updating.remove(target_km2)
                    if target_km2.is_altered:
                        target_km2.start_updating(game_date_time)

        for target_km2 in to_stop_updating:
            if target_km2.is_altered:
                target_km2.stop_updating()
            else:
                self.km2s.remove(target_km2)

        if count_before != len(self.km2s):
            logger.debug(f"The world has now {len(self.km2s)} Km2 loaded.")

    def get_outpost_for(self, km2: Km2) -> Optional[Outpost]:
        for outpost in self.outposts.values():
            if int(outpost.longitude // Km2.SIZE) == int(km2.longitude // Km2.SIZE)\
                    and int(outpost.latitude // Km2.SIZE) == int(km2.latitude // Km2.SIZE):
                return outpost
        return None
    # endregion

    # region Orbit
    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        """Position of this world relative to its star, in the reference frame (meters).

        The reference frame has its z axis along the spin axes, and x, y in the reference plane. The world follows
        its elliptical orbit (see the class docstring); a moon is its planet's position plus its own offset around
        the planet. Memoised for the date of the last call.
        """
        cached = self._position_cache
        if cached is not None and cached[0] == current_datetime:
            return cached[1]

        anomaly = self._eccentric_anomaly(self._mean_anomaly_rad(current_datetime))
        a, e = self.distance_to_parent, self.eccentricity
        x = a * (math.cos(anomaly) - e)
        y = a * math.sqrt(1.0 - e * e) * math.sin(anomaly)
        p, q = self._periapsis_axis, self._quarter_axis
        result = Vector3(x * p[0] + y * q[0], x * p[1] + y * q[1], x * p[2] + y * q[2])
        if self.parent_planet:
            result = self.parent_planet.calculate_stellar_position(current_datetime) + result

        self._position_cache = (current_datetime, result)
        return result

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        """Velocity of this world relative to its star (meters per second), in the frame of calculate_stellar_position.

        Tangent to the orbit, and faster near the periapsis. A moon's velocity is its planet's velocity plus its own
        orbital velocity around the planet. Memoised for the date of the last call.
        """
        cached = self._velocity_cache
        if cached is not None and cached[0] == current_datetime:
            return cached[1]

        anomaly = self._eccentric_anomaly(self._mean_anomaly_rad(current_datetime))
        a, e = self.distance_to_parent, self.eccentricity
        rate = math.tau / self.orbital_period / (1.0 - e * math.cos(anomaly))  # d(anomaly)/dt
        vx = -a * math.sin(anomaly) * rate
        vy = a * math.sqrt(1.0 - e * e) * math.cos(anomaly) * rate
        p, q = self._periapsis_axis, self._quarter_axis
        result = Vector3(vx * p[0] + vy * q[0], vx * p[1] + vy * q[1], vx * p[2] + vy * q[2])
        if self.parent_planet:
            result = self.parent_planet.calculate_stellar_velocity(current_datetime) + result

        self._velocity_cache = (current_datetime, result)
        return result

    def orbit_points(self, current_datetime: datetime, steps: int) -> np.ndarray:
        """The orbit as an (n, 3) array of points in order round the ellipse, relative to what it orbits (the star, or the planet
        of a moon), in the frame of calculate_stellar_position: `steps` evenly spread, plus some close to the world's own place
        at the date, which is one of them, so that a line through them passes exactly through the world."""
        own = self._eccentric_anomaly(self._mean_anomaly_rad(current_datetime))
        near = np.array([0.0, *World.ORBIT_NEAR_ANOMALIES, *(-a for a in World.ORBIT_NEAR_ANOMALIES)]) + own
        anomalies = np.sort(np.mod(np.concatenate([math.tau * np.arange(steps) / steps, near]), math.tau))
        a, e = self.distance_to_parent, self.eccentricity
        x = a * (np.cos(anomalies) - e)
        y = a * math.sqrt(1.0 - e * e) * np.sin(anomalies)
        return x[:, None] * np.array(self._periapsis_axis) + y[:, None] * np.array(self._quarter_axis)

    def _eccentric_anomaly(self, mean_anomaly: float) -> float:
        """Solves Kepler's equation, E - e sin E = M, for E by Newton's method."""
        e = self.eccentricity
        if e == 0.0:
            return mean_anomaly
        anomaly = mean_anomaly + e * math.sin(mean_anomaly)
        for _ in range(20):
            step = (anomaly - e * math.sin(anomaly) - mean_anomaly) / (1.0 - e * math.cos(anomaly))
            anomaly -= step
            if abs(step) < 1e-12:
                break
        return anomaly

    def _mean_anomaly_rad(self, current_datetime: datetime) -> float:
        return math.radians(self.initial_degrees_in_orbit) + math.tau * self.local_year_fraction(current_datetime)

    def local_year_fraction(self, current_datetime: datetime) -> float:
        """Fraction of this world's orbit completed since EPOCH, in [0, 1)."""
        elapsed_seconds = self._elapsed_seconds(current_datetime)
        return (elapsed_seconds % self.orbital_period) / self.orbital_period
    # endregion

    # region Surface frame
    def surface_basis(self, longitude: float, latitude: float, current_datetime: datetime) -> Tuple[Vector3, Vector3, Vector3]:
        """East, up and north unit vectors at a surface point, in the star-centered basis."""
        total_azimuth = self._spin_angle_rad(current_datetime) + longitude / self.radius
        latitude_angle = latitude / self.radius

        azimuthal_direction = Vector3(-math.cos(total_azimuth), math.sin(total_azimuth), 0.0)
        up_hat = azimuthal_direction * math.cos(latitude_angle) + Vector3(0.0, 0.0, 1.0) * math.sin(latitude_angle)
        east_hat = Vector3(math.sin(total_azimuth), math.cos(total_azimuth), 0.0)
        north_hat = Vector3(
            math.sin(latitude_angle) * math.cos(total_azimuth),
            -math.sin(latitude_angle) * math.sin(total_azimuth),
            math.cos(latitude_angle),
        )
        return east_hat, up_hat, north_hat

    def surface_point_stellar(self, longitude: float, latitude: float, current_datetime: datetime) -> Vector3:
        """Stellar position (metres) of a point on this world's surface, given in surface coordinates.
        Same convention as Navigation._stellar_position_from_surface, with altitude 0."""
        _, up_hat, _ = self.surface_basis(longitude, latitude, current_datetime)
        centre = self.calculate_stellar_position(current_datetime)
        offset = up_hat * self.radius
        # The star-centred basis has Y opposite to the orbital motion, so Y is negated.
        return Vector3(centre.x + offset.x, centre.y - offset.y, centre.z + offset.z)

    def surface_vector_to_stellar(self, vector: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        """A direction given in surface (east, up, north) components, in stellar coordinates. `basis` is the
        surface_basis of the point."""
        east_hat, up_hat, north_hat = basis
        star_basis = vector[0] * east_hat + vector[1] * up_hat + vector[2] * north_hat
        return Vector3(star_basis.x, -star_basis.y, star_basis.z)

    def stellar_vector_to_surface(self, vector: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        """A stellar direction in surface (east, up, north) components. `basis` is the surface_basis of the point."""
        east_hat, up_hat, north_hat = basis
        star_basis = Vector3(vector[0], -vector[1], vector[2])
        return Vector3(star_basis.dot(east_hat), star_basis.dot(up_hat), star_basis.dot(north_hat))

    def stellar_to_surface_position(self, stellar_pos: Vector3, current_datetime: datetime) -> Vector3:
        """Inverse of Navigation._stellar_position_from_surface: (longitude, altitude, latitude) for a stellar position."""
        stellar_x, stellar_y, stellar_z = self.calculate_stellar_position(current_datetime)
        relative = Vector3(stellar_pos[0] - stellar_x, -stellar_pos[1] + stellar_y, stellar_pos[2] - stellar_z)

        distance = relative.length()
        up_hat = relative.normalized()
        latitude_angle = math.atan2(up_hat.z, math.hypot(up_hat.x, up_hat.y))
        total_azimuth = math.atan2(up_hat.y, -up_hat.x)

        spin_angle = self._spin_angle_rad(current_datetime)
        longitude = self.radius * ((total_azimuth - spin_angle + math.pi) % math.tau - math.pi)
        return Vector3(longitude, distance - self.radius, self.radius * latitude_angle)

    def stellar_to_surface_velocity(
            self, stellar_vel: Vector3, altitude: float, latitude: float,
            current_datetime: datetime, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        """Inverse of Navigation._stellar_velocity_from_surface: (east, up, north) velocity for a stellar velocity. `basis`
        is the surface_basis of the point."""
        east_hat, up_hat, north_hat = basis
        world_vel = self.calculate_stellar_velocity(current_datetime)
        relative = Vector3(stellar_vel[0] - world_vel.x, -stellar_vel[1] + world_vel.y, stellar_vel[2] - world_vel.z)
        spin_speed = self.spin_speed_at(altitude, latitude)
        return Vector3(relative.dot(east_hat) - spin_speed, relative.dot(up_hat), relative.dot(north_hat))

    def star_offset_from_ship(self, ship: Ship, current_datetime: datetime) -> Vector3:
        """Position of this world's star relative to `ship`, in the ship's local
        east/up/north tangent-plane frame (meters), before any heading rotation.

        Works in a free-standing, star-centered basis X=(1,0,0), Y=(0,1,0), Z=(0,0,1),
        where Z is the world's rotation axis (no axial tilt) and X is the direction from
        the star to the world at GameEnvironment.EPOCH. Y is opposite to the orbital motion
        at EPOCH, the sign convention of this local basis. Orbital motion and the world's own
        spin are both clockwise as seen from +Z ("north"); longitude increasing (east)
        follows the same rotational sense as spin.
        """
        stellar_x, stellar_y, stellar_z = self.calculate_stellar_position(current_datetime)
        world_center = Vector3(stellar_x, -stellar_y, stellar_z)

        east_hat, up_hat, north_hat = self.surface_basis(ship.position.x, ship.position.z, current_datetime)

        ship_position = world_center + up_hat * (self.radius + ship.position.y)
        relative = -ship_position

        return Vector3(relative.dot(east_hat), relative.dot(up_hat), relative.dot(north_hat))

    def spin_speed_at(self, altitude: float, latitude: float) -> float:
        """Eastward ground speed (m/s) from this world's rotation, at the given
        altitude above the surface and latitude (surface arc-length coordinate, meters)."""
        latitude_angle = latitude / self.radius
        return math.tau / self.rotation_period * (self.radius + altitude) * math.cos(latitude_angle)

    def local_day_fraction(self, current_datetime: datetime) -> float:
        """Fraction of the local solar day at longitude 0, in [0, 1): 0 at local noon, 0.5 at midnight.

        It depends on the direction to the star, so the world's initial_degrees_in_orbit sets
        the time of day at EPOCH; the game's date and time are not affected."""
        position = self.calculate_stellar_position(current_datetime)
        angle_to_star = math.atan2(position.y, position.x)
        return ((self._spin_angle_rad(current_datetime) - angle_to_star) / math.tau) % 1.0

    def _spin_angle_rad(self, current_datetime: datetime) -> float:
        if self.is_tidally_locked and not self.is_resonant:
            return self._locked_spin_angle_rad(current_datetime)
        # The share of the current spin (sidereal day) completed.
        elapsed_seconds = self._elapsed_seconds(current_datetime)
        return math.tau * ((elapsed_seconds % self.rotation_period) / self.rotation_period)

    def _locked_spin_angle_rad(self, current_datetime: datetime) -> float:
        """The spin angle of a locked world: the direction of its place from its parent (its star, or its planet for a
        moon), so that the same side always faces the parent. The spin is then the orbit's, not a separate turn."""
        offset: Vector3 = self.calculate_stellar_position(current_datetime)
        if self.parent_planet:
            offset = offset - self.parent_planet.calculate_stellar_position(current_datetime)
        return math.atan2(offset.y, offset.x)

    @staticmethod
    def _elapsed_seconds(current_datetime: datetime) -> float:
        from game_environment import GameEnvironment
        return (current_datetime - GameEnvironment.EPOCH).total_seconds()
    # endregion

    # region Almanack and log
    def markdown(self) -> str:
        '''Markdown of this world.'''
        AU: float = 1.496e11
        heading: str = '####' if self.parent_planet else '###'
        kind: str = 'Moon' if self.parent_planet else 'Planet'
        parent_info: str = (
                f"* Distance from the planet: {format_compact_distance(self.distance_to_parent)}\n"
                f"* Month: {(self.orbital_period / (24 * 60 * 60)):.2f} Earth days\n"
                ) if self.parent_planet else (
                f"* Distance from the star: {self.parent_orbit.distance_from_star/AU:.2f} AU\n"
                f"* Year: {(self.orbital_period / (365.2425 * 24 * 60 * 60)):.2f} Earth years\n"
                )
        orbit_shape: str = (
                f"* Eccentricity: {self.eccentricity:.3f}\n"
                f"* Inclination: {math.degrees(self.inclination):.1f}°\n"
                )
        outposts:str = ', '.join(f"'{o.name}'" for o in self.outposts.values()) if self.outposts else "None"
        if self.is_resonant:
            day: str = "* Day: three turns for every two orbits (3:2 resonance)\n"
        elif self.is_tidally_locked:
            day = "* Day: tidally locked, one turn per orbit\n"
        else:
            day = f"* Day: {self.rotation_period / (60 * 60):.2f} hours\n"
        text: str = (
            f"{heading} {kind} {self.name}\n"
            f"{parent_info}"
            f"{orbit_shape}"
            f"* Radius: {int(self.radius/1000)} Km\n"
            f"{day}"
            f"* Surface: {self.surface_type.label}\n"
            f"* Average temperature: {self.equilibrium_temperature - 273.15:.0f} °C\n"
            f"* 1e-4 Ore prevalence: {1e4*self.ore_prevalence:.2f}\n"
            f"* Outposts: {outposts}\n"
            f"\n"
            )
        text += ''.join(moon.markdown() for moon in self.moons)
        return text

    def _log_creation(self) -> World:
        if self.parent_planet:
            logger.info("NEW MOON CREATED")
        else:
            logger.info("NEW PLANET CREATED")

        logger.info(f" - Orbit(Index): {int(self.parent_orbit.number)} ({self.index})")
        logger.info(f" - Name: {self.name}, Seed: {self.seed}")
        logger.info(f" - Distance to parent: {f'{int(self.distance_to_parent):,}'}")
        if not self.parent_planet:
            logger.info(f" - Farthest stable moon orbit (Hill sphere): {f'{int(self.moon_limit):,}'}")
        logger.info(f" - Radius: {f'{int(self.radius):,}'}")
        spin_state: str = "3:2 resonance" if self.is_resonant else ("1:1 tidal lock" if self.is_tidally_locked else "free")
        logger.info(f" - Spin: {spin_state}, rotation period {self.rotation_period:.3g} s")
        logger.info(f" - Surface: {self.surface_type.label} {self.surface_colour}, {self.equilibrium_temperature:.0f} K")
        logger.info(f" - Ore Prevalence: {self.ore_prevalence}")
        return self
    # endregion
