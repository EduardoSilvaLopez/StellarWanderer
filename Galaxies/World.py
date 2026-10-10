from __future__ import annotations

import copy
import math
import random
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

import logging
import Galaxies.constants
from Galaxies.km2 import Km2
from Galaxies.rock import Rock
from Vector3 import Vector3

if TYPE_CHECKING:
    from Galaxies.orbit import Orbit
    from Player import Player

logger = logging.getLogger(__name__)

class World:
    '''The generation is full of heuristic but playtested, hopefully realistic, factors.'''

    WORLD_MIN_RADIUS = 300000 # Spherical celestial object.
    SURROUNDINGS_RADIUS = 2 * Km2.SIZE
    GRAVITATIONAL_CONSTANT = 6.674e-11  # m^3 kg^-1 s^-2
    EARTH_DENSITY = 5514.0  # kg/m^3, assumed for every world (planets and moons alike)

    def __init__(self, parent_orbit: Orbit = None, parent_planet: World = None, saved_alterations: dict = None) -> None:

        # No parent_planet? Well, then it is a big moon.
        if parent_planet:
            self.parent_planet: World = parent_planet
            self.parent_orbit: Orbit = parent_planet.parent_orbit
            self.index = len(self.parent_planet.moons)
            seed_origin: int = self.parent_planet.seed
        else:
            self.parent_planet: World = None
            self.parent_orbit: Orbit = parent_orbit
            self.index = len(self.parent_orbit.planets)
            seed_origin: int = self.parent_orbit.seed

        self.seed: int = (seed_origin * (self.index + 1) + 1) % Galaxies.constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.name: str =\
            self.generate_moon_name(my_random)\
            if self.parent_planet\
            else self.generate_planet_name(my_random)

        self.radius: float = 0.0
        while self.radius < self.WORLD_MIN_RADIUS:
            if self.parent_planet:
                self.radius = self.generate_radius_of_big_moon(my_random)
            else:
                self.radius = self.generate_radius_of_earthlike(my_random)

        if self.parent_planet:
            self.distance_to_parent: int = self.generate_orbital_distance_of_big_moon(my_random)
        else:
            self.distance_to_parent: int = int(parent_orbit.distance_from_star)
        
        self.initial_degrees_in_orbit: float = my_random.random() * 360.0
        
        self.mass: float = 4.0 / 3.0 * math.pi * self.radius ** 3 * World.EARTH_DENSITY

        # Kepler's third law around the parent, a planet or the star (two-body: both masses count).
        parent_mass: float = \
            self.parent_planet.mass if self.parent_planet else self.parent_orbit.parent_stellar_system.mass
        self.orbital_period: float = math.tau * math.sqrt(
            self.distance_to_parent ** 3 / (World.GRAVITATIONAL_CONSTANT * (parent_mass + self.mass))
        )

        self.rotation_period: int = self.generate_rotation_period(my_random)

        self.rocks_prevalence: float = my_random.random()
        self.ore_prevalence: float = (1.0 - Rock.ORE_RICH_THRESHOLD) ** 2 * my_random.random()
        if self.parent_planet is not None and self.parent_planet.is_initial_planet():
            # Why were you sent here...? :D
            self.rocks_prevalence = 0.5 + 0.5 * my_random.random()
            self.ore_prevalence = (1.0 - Rock.ORE_RICH_THRESHOLD) * my_random.random()

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

        # Children:
        self.moons: List[World] = []
        if not self.parent_planet:
            moons_count = -1
            while moons_count < 0:
                moons_count = int(my_random.gauss(2.0, 1.0))
            # Initial moon's clause.
            if not moons_count and self.is_initial_planet():
                moons_count = 1
            for moonIdx in range(0, moons_count):
                new_moon: World = \
                    World(parent_orbit=None, parent_planet=self, saved_alterations=self.saved_alterations)
                self.moons.append(new_moon)

        self.km2s: List[Km2] = []
        self.log_creation()

    def is_initial_planet(self) -> bool:
        from Galaxies.stellar_system import StellarSystem
        return self.parent_planet is None\
            and self.parent_orbit.number == 3.0\
            and self.parent_orbit.parent_stellar_system.x == 26000\
            and self.parent_orbit.parent_stellar_system.y == 0\
            and self.parent_orbit.parent_stellar_system.z == 0


    def generate_planet_name(self, my_random: random.Random) -> str:
        """Generate a random name for the world."""
        vocals = "aeiouaeio" # repeating the most common.
        consonants = "bcdfghjklmnpqrstvwxyzbcdfgjlmnprst"
        name = ""
        for sylIdx in range(1, my_random.randint(3, 6)):
            if (my_random.random() < 0.5):
                name += my_random.choice(consonants)
            name += my_random.choice(vocals)
            if (my_random.random() < 0.5):
                name += my_random.choice(consonants)
        
        return name.capitalize()

    def generate_moon_name(self, my_random: random.Random) -> str:
        result: str = self.parent_planet.name + "-" + str(self.index + 1)
        return result.capitalize()

    def generate_orbital_distance_of_big_moon(self, my_random: random.Random) -> int:
        result = 0.0
        while result < 3 * self.parent_planet.radius:
            result = int(my_random.gauss(3, 1) * 250.0 * self.radius)
        return result

    def generate_radius_of_earthlike(self, my_random: random.Random) -> int:
        result: float = 0.0
        while result < World.WORLD_MIN_RADIUS:
            result = my_random.gauss(5000000, 1000000)
        return int(result)

    def generate_radius_of_big_moon(self, my_random: random.Random) -> int:
        result: float = 0.0
        while result < World.WORLD_MIN_RADIUS:
            result = 2 ** my_random.gauss(1.0, 1.0) * self.parent_planet.radius / 100.0
        return int(result)

    def generate_rotation_period(self, my_random: random.Random) -> int:
        result: float = 0.0
        if self.parent_planet:
            result = 1 / my_random.gauss(1.0 / (60 * 60 * 24 * 28), 0.2 / (60 * 60 * 24 * 28))
        else:
            result = 1 / my_random.gauss(1.0 / (60 * 60 * 24), 0.2 / (60 * 60 * 24))
        return int(result)

    def log_creation(self) -> World:
        if self.parent_planet:
            logger.info(f"NEW MOON CREATED")
        else:
            logger.info(f"NEW PLANET CREATED")

        logger.info(f" - Orbit(Index): {int(self.parent_orbit.number)} ({self.index})")
        logger.info(f" - Name: {self.name}")
        logger.info(f" - Distance to parent: {'{:,}'.format(int(self.distance_to_parent))}")
        logger.info(f" - Radius: {'{:,}'.format(int(self.radius))}")
        logger.info(f" - Ore Prevalence: {self.ore_prevalence}")
        return self

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

        result: Optional[dict] = dict()

        # Km2 objects only exist near the player, so start from the alterations loaded from the
        # savefile (Km2s not in memory must survive the next save), then overlay the live Km2s.
        km2_alterations: dict = dict()
        if self.saved_alterations is not None and self.saved_alterations.get('Km2s') is not None:
            km2_alterations = copy.deepcopy(self.saved_alterations['Km2s'])
        for km2 in self.km2s:
            if km2.is_altered:
                one_km2_alterations: Optional[dict] = km2.get_alterations()
                if one_km2_alterations is None:
                    km2_alterations.pop(km2.get_alterations_key(), None)
                else:
                    km2_alterations[km2.get_alterations_key()] = one_km2_alterations
        if len(km2_alterations):
            result['Km2s'] = km2_alterations

        moon_alterations: dict = dict()
        for moon in self.moons:
            one_moon_alterations: Optional[dict] = moon.get_alterations()
            if one_moon_alterations is not None:
                moon_alterations[moon.get_alterations_key()] = one_moon_alterations
        if len(moon_alterations):
            result['moons'] = moon_alterations

        if not len(result):
            return None
        return result

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

        if (center_alt <= World.SURROUNDINGS_RADIUS):
            surrounding_chunks = World.SURROUNDINGS_RADIUS // Km2.SIZE
            for lon_delta in range(-surrounding_chunks, surrounding_chunks + 1):
                for lat_delta in range(-surrounding_chunks, surrounding_chunks + 1):
                    target_longitude = longitude + lon_delta * Km2.SIZE
                    target_latitude = latitude + lat_delta * Km2.SIZE
                    tgt_Km2 = next(
                        (km2 for km2 in self.km2s if km2.longitude == target_longitude and km2.latitude == target_latitude),
                        None
                        )
                    if tgt_Km2 is None:
                        new_Km2 = Km2(self, target_longitude, target_latitude, self.saved_alterations)
                        self.km2s.append(new_Km2)
                        continue
                    else:
                        to_stop_updating.remove(tgt_Km2)
                    if not tgt_Km2.is_altered: continue
                    tgt_Km2.start_updating(game_date_time)

        for tgt_Km2 in to_stop_updating:
            if tgt_Km2.is_altered:
                tgt_Km2.stop_updating()
            else:
                self.km2s.remove(tgt_Km2)

        if count_before != len(self.km2s):
            logger.debug(f"The world has now {len(self.km2s)} Km2 loaded.")

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        """Position of this world relative to its star, in the orbital frame (meters).

        x is the reference direction of the orbital angle (the world is at its
        initial_degrees_in_orbit from it at EPOCH), y lies in the orbital plane in the
        direction of motion, and z is perpendicular to the plane, positive when the orbit
        is clockwise seen from above. A moon is its planet's position plus its own offset
        around the planet, in the same plane.
        """
        orbital_angle = self._orbital_angle_rad(current_datetime)
        distance = self.distance_to_parent
        offset = Vector3(distance * math.cos(orbital_angle), distance * math.sin(orbital_angle), 0.0)
        if self.parent_planet:
            return self.parent_planet.calculate_stellar_position(current_datetime) + offset
        return offset

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        """Velocity of this world relative to its star (meters per second), in the frame of calculate_stellar_position.

        Assumes a circular orbit. The vector is tangent to the orbit; its length is the orbital speed.
        A moon's velocity is its planet's velocity plus its own orbital velocity around the planet.
        """
        orbital_angle = self._orbital_angle_rad(current_datetime)
        angular_speed = math.tau / self.orbital_period
        speed = self.distance_to_parent * angular_speed
        own_velocity = Vector3(-speed * math.sin(orbital_angle), speed * math.cos(orbital_angle), 0.0)
        if self.parent_planet:
            return self.parent_planet.calculate_stellar_velocity(current_datetime) + own_velocity
        return own_velocity

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

    def surface_vector_to_stellar_with_basis(self, vector: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        """Cheap half of surface_vector_to_stellar: apply an already-computed basis."""
        east_hat, up_hat, north_hat = basis
        star_basis = vector[0] * east_hat + vector[1] * up_hat + vector[2] * north_hat
        return Vector3(star_basis.x, -star_basis.y, star_basis.z)

    def surface_vector_to_stellar(self, vector: Vector3, longitude: float, latitude: float, current_datetime: datetime) -> Vector3:
        """Express a direction given in surface (east, up, north) components in stellar coordinates."""
        basis = self.surface_basis(longitude, latitude, current_datetime)
        return self.surface_vector_to_stellar_with_basis(vector, basis)

    def stellar_vector_to_surface_with_basis(self, vector: Vector3, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        """Cheap half of stellar_vector_to_surface: apply an already-computed basis."""
        east_hat, up_hat, north_hat = basis
        star_basis = Vector3(vector[0], -vector[1], vector[2])
        return Vector3(star_basis.dot(east_hat), star_basis.dot(up_hat), star_basis.dot(north_hat))

    def stellar_vector_to_surface(self, vector: Vector3, longitude: float, latitude: float, current_datetime: datetime) -> Vector3:
        """Express a stellar direction in surface (east, up, north) components."""
        basis = self.surface_basis(longitude, latitude, current_datetime)
        return self.stellar_vector_to_surface_with_basis(vector, basis)

    def calculate_star_position(self, player: Player, current_datetime: datetime) -> Vector3:
        """Position of this world's star relative to `player`, in the player's local
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

        east_hat, up_hat, north_hat = self.surface_basis(player.position.x, player.position.z, current_datetime)

        player_position = world_center + up_hat * (self.radius + player.position.y)
        relative = -player_position

        return Vector3(relative.dot(east_hat), relative.dot(up_hat), relative.dot(north_hat))

    def stellar_to_surface_position(self, stellar_pos: Vector3, current_datetime: datetime) -> Vector3:
        """Inverse of Player.calculate_stellar_position: (longitude, altitude, latitude) for a stellar position."""
        stellar_x, stellar_y, stellar_z = self.calculate_stellar_position(current_datetime)
        relative = Vector3(stellar_pos[0] - stellar_x, -stellar_pos[1] + stellar_y, stellar_pos[2] - stellar_z)

        distance = relative.length()
        up_hat = relative.normalized()
        latitude_angle = math.atan2(up_hat.z, math.hypot(up_hat.x, up_hat.y))
        total_azimuth = math.atan2(up_hat.y, -up_hat.x)

        spin_angle = self._spin_angle_rad(current_datetime)
        longitude = self.radius * ((total_azimuth - spin_angle + math.pi) % math.tau - math.pi)
        return Vector3(longitude, distance - self.radius, self.radius * latitude_angle)

    def spin_speed_at(self, altitude: float, latitude: float) -> float:
        """Eastward ground speed (m/s) from this world's rotation, at the given
        altitude above the surface and latitude (surface arc-length coordinate, meters)."""
        latitude_angle = latitude / self.radius
        return math.tau / self.rotation_period * (self.radius + altitude) * math.cos(latitude_angle)

    def stellar_to_surface_velocity_with_basis(
            self, stellar_vel: Vector3, altitude: float, latitude: float,
            current_datetime: datetime, basis: Tuple[Vector3, Vector3, Vector3]) -> Vector3:
        """Cheap half of stellar_to_surface_velocity: apply an already-computed basis."""
        east_hat, up_hat, north_hat = basis
        world_vel = self.calculate_stellar_velocity(current_datetime)
        relative = Vector3(stellar_vel[0] - world_vel.x, -stellar_vel[1] + world_vel.y, stellar_vel[2] - world_vel.z)
        spin_speed = self.spin_speed_at(altitude, latitude)
        return Vector3(relative.dot(east_hat) - spin_speed, relative.dot(up_hat), relative.dot(north_hat))

    def stellar_to_surface_velocity(self, stellar_vel: Vector3, longitude: float, altitude: float, latitude: float, current_datetime: datetime) -> Vector3:
        """Inverse of Player.calculate_stellar_velocity: (east, up, north) velocity for a stellar velocity."""
        basis = self.surface_basis(longitude, latitude, current_datetime)
        return self.stellar_to_surface_velocity_with_basis(stellar_vel, altitude, latitude, current_datetime, basis)

    def local_year_fraction(self, current_datetime: datetime) -> float:
        """Fraction of this world's orbit completed since EPOCH, in [0, 1)."""
        elapsed_seconds = self._elapsed_seconds(current_datetime)
        return (elapsed_seconds % self.orbital_period) / self.orbital_period

    def local_day_fraction(self, current_datetime: datetime) -> float:
        """Fraction of the local solar day at longitude 0, in [0, 1): 0 at local noon, 0.5 at midnight.

        It depends on the direction to the star, so the world's initial_degrees_in_orbit sets
        the time of day at EPOCH; the game's date and time are not affected."""
        position = self.calculate_stellar_position(current_datetime)
        angle_to_star = math.atan2(position.y, position.x)
        return ((self._spin_angle_rad(current_datetime) - angle_to_star) / math.tau) % 1.0

    def _spin_fraction(self, current_datetime: datetime) -> float:
        """Fraction of this world's current spin (sidereal day) completed, in [0, 1)."""
        elapsed_seconds = self._elapsed_seconds(current_datetime)
        return (elapsed_seconds % self.rotation_period) / self.rotation_period

    def _orbital_angle_rad(self, current_datetime: datetime) -> float:
        return math.radians(self.initial_degrees_in_orbit) + math.tau * self.local_year_fraction(current_datetime)

    def _spin_angle_rad(self, current_datetime: datetime) -> float:
        return math.tau * self._spin_fraction(current_datetime)

    @staticmethod
    def _elapsed_seconds(current_datetime: datetime) -> float:
        from GameEnvironment import GameEnvironment
        return (current_datetime - GameEnvironment.EPOCH).total_seconds()
