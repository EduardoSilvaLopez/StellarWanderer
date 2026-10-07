from __future__ import annotations

import logging; logger = logging.getLogger(__name__)

import math
import random
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

import Galaxies.Constants

if TYPE_CHECKING:
    from Galaxies.Orbit import Orbit
    from Player import Player

from Galaxies.Km2 import Km2
from Vector3 import Vector3

class World:

    EARTHLIKE_RADIUS_AVERAGE = 5000000
    EARTHLIKE_RADIUS_SIGMA = 1000000
    EARTHLIKE_ROTATION_AVERAGE_F = 1.0 / (60 * 60 * 24)
    EARTHLIKE_ROTATION_SIGMA_F = 0.2 / (60 * 60 * 24)
    SURROUNDINGS_RADIUS = 2 * Km2.SIZE

    def __init__(self, parent_orbit: Orbit, initial_degrees_in_orbit: int, saved_alterations: dict) -> None:
        self.parent_orbit: Orbit = parent_orbit
        self.initial_degrees_in_orbit: int = initial_degrees_in_orbit
        self.seed: int = (self.initial_degrees_in_orbit + self.parent_orbit.seed) % Galaxies.Constants.SEEDS_SCALING
        my_random: random.Random = random.Random(self.seed)

        self.radius: float = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        while self.radius <= 0:
            self.radius = my_random.gauss(World.EARTHLIKE_RADIUS_AVERAGE, World.EARTHLIKE_RADIUS_SIGMA)
        self.rotation_period: float = 1 / my_random.gauss(World.EARTHLIKE_ROTATION_AVERAGE_F, World.EARTHLIKE_ROTATION_SIGMA_F)
        # Cached because it only depends on distance_from_star, which never changes.
        self.year_duration_seconds: float = 365.2425 * 24 * 60 * 60 * (self.parent_orbit.distance_from_star / 1.496e11) ** (3 / 2)
        self.km2s: List[Km2] = []

        self.is_altered: bool = False
        self.saved_alterations: Optional[dict] = None
        alterations_key: str = self.get_alterations_key()
        if saved_alterations is not None and alterations_key in saved_alterations:
            self.is_altered = True
            self.saved_alterations = saved_alterations.get(alterations_key)
            self.saved_alterations['date_time'] = saved_alterations['date_time']

        self.name: str = self.generate_name(my_random)

    def set_altered(self) -> World:
        self.is_altered = True
        if not self.parent_orbit.is_altered:
            self.parent_orbit.set_altered()
        return self

    def get_alterations_key(self) -> str:
        return str(self.initial_degrees_in_orbit)

    def get_alterations(self) -> Optional[dict]:
        alterations: Optional[dict] = dict()
        if self.is_altered:
            for km2 in self.km2s:
                if km2.is_altered:
                    alterations[km2.get_alterations_key()] = km2.get_alterations()
        if alterations == {}:
            return None
        return alterations                    

    def generate_name(self, my_random: random.Random) -> str:
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

        x points from the star towards the world at EPOCH, y lies in the orbital plane
        in the direction of motion at EPOCH, and z is perpendicular to the plane, positive
        when the orbit is clockwise seen from above.
        """
        orbital_angle = self._orbital_angle_rad(current_datetime)
        distance = self.parent_orbit.distance_from_star
        return Vector3(distance * math.cos(orbital_angle), distance * math.sin(orbital_angle), 0.0)

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        """Velocity of this world relative to its star (meters per second), in the frame of calculate_stellar_position.

        Assumes a circular orbit. The vector is tangent to the orbit; its length is the orbital speed.
        """
        orbital_angle = self._orbital_angle_rad(current_datetime)
        angular_speed = math.tau / self.year_duration_seconds
        speed = self.parent_orbit.distance_from_star * angular_speed
        return Vector3(-speed * math.sin(orbital_angle), speed * math.cos(orbital_angle), 0.0)

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
        return (elapsed_seconds % self.year_duration_seconds) / self.year_duration_seconds

    def local_day_fraction(self, current_datetime: datetime) -> float:
        """Fraction of this world's current spin (day) completed, in [0, 1)."""
        elapsed_seconds = self._elapsed_seconds(current_datetime)
        return (elapsed_seconds % self.rotation_period) / self.rotation_period

    def _orbital_angle_rad(self, current_datetime: datetime) -> float:
        return math.tau * self.local_year_fraction(current_datetime)

    def _spin_angle_rad(self, current_datetime: datetime) -> float:
        return math.tau * self.local_day_fraction(current_datetime)

    @staticmethod
    def _elapsed_seconds(current_datetime: datetime) -> float:
        from GameEnvironment import GameEnvironment
        return (current_datetime - GameEnvironment.EPOCH).total_seconds()
