from __future__ import annotations

import copy
import math
import random
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

import logging
from common.units import format_compact_distance
import galaxies.constants
from galaxies import seeds
from galaxies.km2 import Km2
from galaxies.rock import Rock
from galaxies.world import World
from galaxies.world_surface import SurfaceType, equilibrium_temperature, generate_surface

if TYPE_CHECKING:
    from galaxies.outpost import Outpost
    from galaxies.orbit import Orbit

logger = logging.getLogger(__name__)


class RockyWorld(World):
    '''A world with a surface the ship can land on: an earthlike planet or a moon. The generation is full of
    heuristic but playtested, hopefully realistic, factors. The orbits, the spin and the frames are the `World`'s (see
    world.py); the four values of the orbit's shape are drawn after the other values in the constructor, so adding them
    changed no earlier value. Every rocky world has EARTH_DENSITY, so its `mass` follows from its radius, and a moon
    orbits around its planet's mass. A planet's moons orbit inside the stable part of its Hill sphere (`moon_limit`,
    see `moon_limit_in_radii`), and a planet too close to its star has none. The tides tie the spin of every moon, and
    of the close planets, to the orbit (`is_tidally_locked`, see World).

    Surface: `equilibrium_temperature` (K) from the star's light and the distance, then `surface_type` and
    `surface_colour` from it and the seed (see world_surface.py); they are drawn last, after the orbit's values. The
    colour is what the graphics light (LitWorlds, SurfaceLight); the type and the temperature are in the knowledge base
    (`markdown`).
    '''

    SURROUNDINGS_RADIUS = 2 * Km2.SIZE
    EARTH_DENSITY = 5514.0  # kg/m^3, assumed for every rocky world (planets and moons alike)

    # Orbit tilt: |N(0, sigma)|, capped. A moon's distance is never below 3 planet radii, so with the eccentricity
    # capped at 0.3 its periapsis stays above 2.1 planet radii.
    PLANET_INCLINATION_SIGMA_DEGREES = 10.0
    PLANET_MAX_INCLINATION_DEGREES = 30.0
    MOON_INCLINATION_SIGMA_DEGREES = 5.0
    MOON_MAX_INCLINATION_DEGREES = 20.0

    # Moons: the closest is MOON_MIN_DISTANCE_RADII planet radii away (outside the Roche limit, 2.44 radii for worlds of
    # one density, and clear of the planet's bind zone). The farthest is inside the planet's Hill sphere: the region
    # around it, of radius a (m / 3M)^(1/3) (a: its distance to its star, m: its mass, M: the star's), where its pull
    # wins over the star's. A prograde moon orbit stays stable out to about half of it (Domingos et al. 2006).
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

    # region Generation
    @staticmethod
    def moon_limit_in_radii(distance_to_star: float, star_mass: float) -> float:
        """The farthest a moon's orbit (semi-major axis) can be from a planet, in planet radii, when it is
        `distance_to_star` metres from a star of `star_mass` kilograms: MOON_STABLE_HILL_FRACTION of its Hill sphere.
        The sphere is taken at the planet's periapsis and the moon's apoapsis at the largest eccentricities
        (MAX_ECCENTRICITY), as neither is known yet. Every world has EARTH_DENSITY, so a planet's mass grows with
        its radius cubed, and the Hill sphere in planet radii does not depend on its size: the limit is linear in the
        distance."""
        hill_in_radii = distance_to_star * (1.0 - RockyWorld.MAX_ECCENTRICITY) \
            * (4.0 * math.pi * RockyWorld.EARTH_DENSITY / (9.0 * star_mass)) ** (1.0 / 3.0)
        return RockyWorld.MOON_STABLE_HILL_FRACTION * hill_in_radii / (1.0 + RockyWorld.MAX_ECCENTRICITY)

    def __init__(self, parent_orbit: Orbit = None, parent_planet: World = None, saved_alterations: dict = None) -> None:
        super().__init__()

        # A parent_planet? Then it is a moon.
        if parent_planet:
            self.parent_planet = parent_planet
            self.parent_orbit = parent_planet.parent_orbit
            self.index = len(self.parent_planet.moons)
            self.seed = seeds.derive(self.parent_planet.seed, 'moon', self.index)
        else:
            self.parent_planet = None
            self.parent_orbit = parent_orbit
            self.index = len(self.parent_orbit.planets)
            self.seed = seeds.derive(self.parent_orbit.seed, 'planet', self.index)
        my_random: random.Random = random.Random(self.seed)

        self.name =\
            (self.parent_planet.name + "-" + str(self.index + 1)).capitalize()\
            if self.parent_planet\
            else self._generate_planet_name(my_random)

        self.radius =\
            self._generate_moon_radius(my_random)\
            if self.parent_planet\
            else self._generate_planet_radius(my_random)

        if self.parent_planet:
            self.distance_to_parent = self._generate_moon_distance(my_random)
        else:
            self.distance_to_parent = int(parent_orbit.distance_from_star)

        self.initial_degrees_in_orbit = my_random.random() * 360.0

        self.mass = 4.0 / 3.0 * math.pi * self.radius ** 3 * RockyWorld.EARTH_DENSITY

        # Kepler's third law around the parent, a planet or the star (two-body: both masses count).
        parent_mass: float = self.parent_planet.mass if self.parent_planet else self.stellar_system.star.mass
        self.orbital_period = math.tau * math.sqrt(
            self.distance_to_parent ** 3 / (RockyWorld.GRAVITATIONAL_CONSTANT * (parent_mass + self.mass))
        )

        # The farthest a moon's orbit can be from this planet: inside its Hill sphere (see moon_limit_in_radii).
        self.moon_limit: float = 0.0
        if not self.parent_planet:
            self.moon_limit = RockyWorld.moon_limit_in_radii(self.distance_to_parent,
                                                             self.stellar_system.star.mass) * self.radius

        self.rotation_period = self._generate_rotation_period(my_random)
        self.is_tidally_locked = self._is_tidally_locked(parent_mass)
        if self.is_tidally_locked:
            self.rotation_period = self.orbital_period  # the 1:1 lock, unless the resonance is drawn below

        self.rocks_prevalence: float = my_random.random()
        self.ore_prevalence: float = (1.0 - Rock.ORE_RICH_THRESHOLD) * my_random.random()
        if self.parent_planet is not None and self.parent_planet._is_initial_planet():
            # Why were you sent here...? :D
            self.rocks_prevalence = 0.5 + 0.5 * my_random.random()
            self.ore_prevalence = (1.0 - Rock.ORE_RICH_THRESHOLD) ** 0.68 * my_random.random()

        # Alterations:
        self.is_altered = False
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
        if not self.parent_planet:
            moons_count = -1
            while moons_count < 0:
                moons_count = int(my_random.gauss(2.0, 1.0))
            # Initial moon's clause.
            if not moons_count and self._is_initial_planet():
                moons_count = 1
            # A planet too close to its star has no room for a stable moon: it has none. (The layout of the initial
            # system leaves room for the initial planet's moon.)
            if not self._is_initial_planet() and self.moon_limit < RockyWorld.MOON_MIN_ROOM_RADII * self.radius:
                moons_count = 0
            for _ in range(moons_count):
                self.moons.append(RockyWorld(parent_orbit=None, parent_planet=self,
                                        saved_alterations=self.saved_alterations))

        if self.parent_planet:
            sigma, limit = RockyWorld.MOON_INCLINATION_SIGMA_DEGREES, RockyWorld.MOON_MAX_INCLINATION_DEGREES
        else:
            sigma, limit = RockyWorld.PLANET_INCLINATION_SIGMA_DEGREES, RockyWorld.PLANET_MAX_INCLINATION_DEGREES
        self._generate_orbit_orientation(my_random, sigma, limit)  # no value drawn above depends on it

        # Drawn after the orbit, so adding them changed no earlier value. A moon is as far from the star as its planet.
        planet = self.parent_planet if self.parent_planet else self
        self.equilibrium_temperature = equilibrium_temperature(self.stellar_system.star,
                                                               planet.distance_to_parent)
        self.surface_type: SurfaceType
        self.surface_colour: Tuple[int, int, int]
        self.surface_type, self.surface_colour = generate_surface(my_random, self.equilibrium_temperature)

        # Drawn last, so no value above changed: a tied planet may be in the 3:2 resonance instead of the 1:1 lock.
        self.is_resonant = self._is_resonant(my_random)
        if self.is_resonant:
            self.rotation_period = self.orbital_period / RockyWorld.RESONANCE_TURNS_PER_ORBIT

        self.km2s: List[Km2] = []
        self._learn()
        self._log_creation()

    def _is_initial_planet(self) -> bool:
        return self.parent_planet is None\
            and self.parent_orbit.number == 3.0\
            and (self.stellar_system.x, self.stellar_system.y,
                 self.stellar_system.z) == galaxies.constants.INITIAL_STAR_POSITION

    def _generate_planet_radius(self, my_random: random.Random) -> int:
        result: float = 0.0
        while result < RockyWorld.WORLD_MIN_RADIUS:
            result = my_random.gauss(5000000, 1000000)
        return int(result)

    def _generate_moon_radius(self, my_random: random.Random) -> int:
        result: float = 0.0
        while result < RockyWorld.WORLD_MIN_RADIUS:
            result = 2 ** my_random.gauss(1.0, 1.0) * self.parent_planet.radius / 100.0
        return int(result)

    def _generate_moon_distance(self, my_random: random.Random) -> int:
        """The moon's distance to its planet: a draw of a few hundred moon radii, never under MOON_MIN_DISTANCE_RADII
        planet radii and never beyond the planet's moon_limit (its Hill sphere). A draw beyond the limit is placed
        inside the stable region with the fractional part of the same draw, so no draw is added and every later value of
        the moon stays what it was, and moons do not pile up at the limit."""
        lowest = RockyWorld.MOON_MIN_DISTANCE_RADII * self.parent_planet.radius
        highest = self.parent_planet.moon_limit
        result = 0.0
        draw = 0.0
        while result < lowest:
            draw = my_random.gauss(3, 1)
            result = int(draw * 250.0 * self.radius)
        if result > highest:
            # (If the stable region is narrower than the minimum, only the initial planet gets here: it gets the
            # minimum.)
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
        density_term: float = 4.0 / 3.0 * math.pi * RockyWorld.EARTH_DENSITY  # m / R^3, the same for every world
        lock_time: float = (
            RockyWorld.MOMENT_OF_INERTIA_FACTOR * initial_spin * self.distance_to_parent ** 6 * density_term
            * RockyWorld.TIDAL_QUALITY_FACTOR
            / (3.0 * RockyWorld.GRAVITATIONAL_CONSTANT * parent_mass ** 2 * RockyWorld.TIDAL_LOVE_NUMBER)
        )
        return lock_time < RockyWorld.TIDAL_LOCK_TIME_LIMIT

    def _is_resonant(self, my_random: random.Random) -> bool:
        """True if a tied planet is caught in the 3:2 resonance rather than the 1:1 lock: only a planet (not a moon) of
        an eccentric enough orbit (RESONANCE_MIN_ECCENTRICITY), and then with RESONANCE_CHANCE. Drawn only in those
        cases."""
        if not self.is_tidally_locked or self.parent_planet \
                or self.eccentricity < RockyWorld.RESONANCE_MIN_ECCENTRICITY:
            return False
        return my_random.random() < RockyWorld.RESONANCE_CHANCE


    # region Alterations
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

    def update_surroundings(self, center_alt: float, center_lon: float, center_lat: float,
                            game_date_time: datetime) -> None:
        """
        1. Ensure the surroundings of a point exist and are updated.
        2. Ensure everything else loaded is *not longer* updated.
        """
        count_before = len(self.km2s)

        longitude: int = int((center_lon // Km2.SIZE) * Km2.SIZE)
        latitude: int = int((center_lat // Km2.SIZE) * Km2.SIZE)

        to_stop_updating: List[Km2] = self.km2s.copy()

        if center_alt <= RockyWorld.SURROUNDINGS_RADIUS:
            surrounding_chunks = RockyWorld.SURROUNDINGS_RADIUS // Km2.SIZE
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

    def _log_creation(self) -> RockyWorld:
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
        spin_state: str = "3:2 resonance" if self.is_resonant \
            else ("1:1 tidal lock" if self.is_tidally_locked else "free")
        logger.info(f" - Spin: {spin_state}, rotation period {self.rotation_period:.3g} s")
        logger.info(f" - Surface: {self.surface_type.label} {self.surface_colour}, {self.equilibrium_temperature:.0f} "
        f"K")
        logger.info(f" - Ore Prevalence: {self.ore_prevalence}")
        return self
    # endregion
