"""The world: a planet or a moon, whatever it is made of. What the rocky and the jovian worlds have in common."""

from __future__ import annotations

import math
import numpy as np
import random
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

from galaxies.body import Body
from galaxies.people import knowledge
from common.vector3 import Vector3

if TYPE_CHECKING:
    from galaxies.km2 import Km2
    from galaxies.orbit import Orbit
    from galaxies.stellar_system import StellarSystem
    from spaceships.ship import Ship


class World(Body):
    '''Orbits: every orbital period follows Kepler's third law around the parent's mass: a moon around its planet, a
    planet around its star (`StellarSystem.mass`, estimated from the star's radius). Each orbit is an ellipse whose
    semi-major axis is `distance_to_parent`, with an `eccentricity`, an `inclination` to the reference plane, a
    longitude of the ascending node and an argument of periapsis (`_generate_orbit_orientation`). Every world starts
    `initial_degrees_in_orbit` from the periapsis direction at EPOCH, as a mean anomaly (the true angle for a circular
    orbit). The spin axis stays on the reference z axis, so the inclination of a planet's orbit is its axial tilt
    (seasons); a moon's inclination is relative to its planet's equator. A world whose spin the tides have tied to
    its orbit (`is_tidally_locked`) either turns once per orbit and keeps the same side to its parent, or, if
    `is_resonant`, turns three times for two orbits. `local_day_fraction` is the solar day at longitude 0 (0 = noon);
    the game's date and time always start at EPOCH 00:00:00.

    A world's position and velocity are pure functions of the date, memoised for the date of the last call only (one
    entry each), so everything drawn or computed in a frame shares one evaluation per world.

    The kinds of world are `RockyWorld` (rocky_world.py: a surface, Km2s, outposts, moons) and `JovianWorld`
    (jovian_world.py). The subclass draws the values, in its own order, and sets the attributes declared here. A world
    answers for its ground as one with none: no Km2s, no outposts, no mines (`get_km2_at`, `update_surroundings`); only
    a `RockyWorld` has them. `surface_colour` is what the graphics light.
    '''

    is_world = True

    WORLD_MIN_RADIUS = 300000  # Spherical celestial object.
    GRAVITATIONAL_CONSTANT = 6.674e-11  # m^3 kg^-1 s^-2

    # Orbit shape: |N(0, sigma)|, capped.
    ECCENTRICITY_SIGMA = 0.1
    MAX_ECCENTRICITY = 0.3

    # Eccentric anomalies, in radians, either side of the world's own: where orbit_points adds points to follow the
    # curve closely.
    ORBIT_NEAR_ANOMALIES = (1e-4, 2.5e-4, 6e-4, 1.5e-3, 4e-3, 1e-2, 2.5e-2, 6e-2)

    def __init__(self) -> None:
        self._position_cache: Optional[Tuple[datetime, Vector3]] = None
        self._velocity_cache: Optional[Tuple[datetime, Vector3]] = None
        self._surface_basis_cache: Optional[Tuple[tuple, Tuple[Vector3, Vector3, Vector3]]] = None

        self.parent_planet: Optional[World] = None  # a moon's planet
        self.parent_orbit: Orbit
        self.index: int
        self.seed: int
        self.name: str
        self.radius: float
        self.mass: float
        self.distance_to_parent: float
        self.initial_degrees_in_orbit: float
        self.orbital_period: float
        self.rotation_period: float
        self.is_tidally_locked: bool = False
        self.is_resonant: bool = False
        self.equilibrium_temperature: float
        self.eccentricity: float
        self.inclination: float
        self.node_longitude: float
        self.periapsis_argument: float
        self.moons: List[World] = []
        self.surface_colour: Tuple[int, int, int]
        self.is_altered: bool = False
        self.km2s: List[Km2] = []
        self.outposts: dict = {}
        self.registered_mines: List[tuple] = []

    @property
    def stellar_system(self) -> StellarSystem:
        return self.parent_orbit.parent_stellar_system

    # region Generation
    def _learn(self) -> None:
        """Adds this world to the player's knowledge (see knowledge.py): a planet with its (so far empty) moons, a moon
        in its planet."""
        system_key: str = self.stellar_system.get_alterations_key()
        orbit_key: str = self.parent_orbit.get_alterations_key()
        if self.parent_planet:
            knowledge.current_knowledge.learn_moon(system_key, orbit_key, self.parent_planet.get_alterations_key(),
                                                   self.get_alterations_key())
        else:
            knowledge.current_knowledge.learn_planet(system_key, orbit_key, self.get_alterations_key())

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

    def _generate_orbit_orientation(self, my_random: random.Random, inclination_sigma_degrees: float,
                                    max_inclination_degrees: float) -> None:
        """Eccentricity, inclination (|N(0, sigma)|, capped), node longitude and periapsis argument of the orbit around
        the parent."""
        self.eccentricity = min(abs(my_random.gauss(0.0, World.ECCENTRICITY_SIGMA)), World.MAX_ECCENTRICITY)
        self.inclination = math.radians(min(abs(my_random.gauss(0.0, inclination_sigma_degrees)),
                                            max_inclination_degrees))
        self.node_longitude = my_random.random() * math.tau
        self.periapsis_argument = my_random.random() * math.tau
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

    # region Ground
    def get_km2_at(self, longitude: float, latitude: float) -> Optional[Km2]:
        """The Km2 of a point of the ground, if it is loaded: a world without ground has none."""
        return None

    def update_surroundings(self, center_alt: float, center_lon: float, center_lat: float,
                            game_date_time: datetime) -> None:
        """Loads the Km2s around a point of the ground and stops those left behind: nothing to do without ground."""
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
        """What the player changed in this world; None for a world that can not be changed."""
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
        """The orbit as an (n, 3) array of points in order round the ellipse, relative to what it orbits (the star, or
        the planet of a moon), in the frame of calculate_stellar_position: `steps` evenly spread, plus some close to the
        world's own place at the date, which is one of them, so that a line through them passes exactly through the
        world."""
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
    def surface_basis(self, longitude: float, latitude: float,
                      current_datetime: datetime) -> Tuple[Vector3, Vector3, Vector3]:
        """East, up and north unit vectors at a surface point, in the star-centered basis. Memoised for the last call's
        arguments: a frame asks for the same point once per star."""
        key = (longitude, latitude, current_datetime)
        cached = self._surface_basis_cache
        if cached is not None and cached[0] == key:
            return cached[1]

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
        result = (east_hat, up_hat, north_hat)
        self._surface_basis_cache = (key, result)
        return result

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
        """Inverse of Navigation._stellar_position_from_surface: (longitude, altitude, latitude) for a stellar
        position."""
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
        """Inverse of Navigation._stellar_velocity_from_surface: (east, up, north) velocity for a stellar velocity.
        `basis` is the surface_basis of the point."""
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
        '''Markdown of this world and its moons, for the knowledge base.'''
        raise NotImplementedError
    # endregion

