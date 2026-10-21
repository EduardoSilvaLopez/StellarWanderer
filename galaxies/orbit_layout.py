"""The layout of a stellar system's orbits: how many there are, of which kind, and how far from the star.

Three kinds of orbit (`OrbitKind`): earthlike (terrestrial) planets, asteroid belts and jovian planets. Jovian planets are
only laid out, not created yet: `Orbit` gives them no planets. An asteroid belt is created as an `AsteroidBelt`
(asteroid_belt.py), which generates its asteroids. The layout is a pure function of the star and of the
system's random generator, so the same seed always gives the same system. Orbits are numbered 1.0, 2.0, ... from the
star, every kind together. Stars of type O have no orbits (their discs do not last long enough to form planets), except
the initial star, which always has some.

Where things go. Distances that depend on temperature come from the star's luminosity L, in watts: a black body at
temperature T is at the distance d = sqrt(L / (16 pi sigma T^4)) from the star, sigma being the Stefan-Boltzmann
constant (`OrbitLayout.distance_at`). Three temperatures set the zones (`SystemScales`): the inner edge, where dust
sublimates so nothing forms closer (and never within a margin of the star's heat death radius); the snow line, where
water ice survives in the disc (Hayashi 1981), beyond which giant planets form; and the cold belt, where debris sits,
as in the Kuiper belt and the cold debris discs seen around other stars. The rest is ratios to these distances and to
the neighbouring orbit.

How the architecture is built, outwards from the giants, as the Solar System was. The values are the constants of
`OrbitLayout` named at each step: they are tuned for gameplay and are not repeated here.

1. Giants (`GIANT_*`, `FIRST_GIANT_SNOW_LINES`). Their frequency grows with the mass of the star (Johnson et al. 2010).
   Real surveys would leave most systems without one; the game gives them to more stars, on purpose. Neighbouring
   giants keep a minimum ratio, the lowest of `GIANT_SPACING`: closer ones would be unstable (they need several
   mutual Hill radii between them, Chambers et al. 1996).
2. The inner belt (`INNER_BELT_*`). It sits where a giant keeps planets from forming, near its inner resonances (as the
   main belt does with Jupiter).
3. The terrestrial planets (`ROCKY_*`), from the outer limit of their zone inwards: inside the belt, or inside the
   first giant when there is no belt, or inside the snow line when there are no giants. Each is a spacing ratio closer
   than the next, a ratio drawn between limits that the Solar System and Kepler's multi-planet systems (Weiss et al.
   2018) guide. Now and then the place of a planet holds a belt instead (`FAILED_PLANET_CHANCE`): a planet that
   never formed.
4. The cold belt (`COLD_BELT_*`), beyond the outermost giant and never closer than the cold-belt zone. It is rarer
   without giants.

Orbits farther than `MAX_ORBIT` are dropped (a stellar disc, and its system, are not larger), and any two orbits closer
than `MIN_SPACING` are resolved by dropping the belt.

The initial system is generated until its orbit `INITIAL_ORBIT_NUMBER` is an earthlike planet that can start the
game: outside the star's death radius (the ship would reach its maximum temperature), and with room for a stable moon
(`World.moon_limit_in_radii`, `World.MOON_MIN_ROOM_RADII`). It always has one: see `OrbitLayout.generate`.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
import random
from typing import List, Optional, Tuple

from galaxies.star import Star
from galaxies.world import World

Entry = Tuple[float, "OrbitKind"]  # (distance from the star in metres, kind)


class OrbitKind(Enum):
    EARTHLIKE = "Earthlike planet"
    ASTEROID_BELT = "Asteroid belt"
    JOVIAN = "Jovian planet"


@dataclass(frozen=True)
class OrbitPlan:
    number: float  # 1.0 is the closest to the star, then 2.0, 3.0...
    kind: OrbitKind
    distance: float  # metres from the star: the semi-major axis, or the middle of a belt


@dataclass(frozen=True)
class SystemScales:
    """The distances, in metres, that depend on the star: the zones of its system."""
    luminosity: float  # W
    mass: float  # kg
    inner_edge: float
    snow_line: float
    cold_belt_min: float
    cold_belt_max: float
    max_orbit: float

    @staticmethod
    def of(star: Star) -> SystemScales:
        return SystemScales(
            luminosity=star.luminosity,
            mass=star.mass,
            inner_edge=max(OrbitLayout.distance_at(star.luminosity, OrbitLayout.INNER_EDGE_TEMPERATURE),
                           OrbitLayout.INNER_EDGE_DEATH_RADII * star.default_death_radius),
            snow_line=OrbitLayout.distance_at(star.luminosity, OrbitLayout.SNOW_LINE_TEMPERATURE),
            cold_belt_min=OrbitLayout.distance_at(star.luminosity, OrbitLayout.COLD_BELT_TEMPERATURES[1]),
            cold_belt_max=OrbitLayout.distance_at(star.luminosity, OrbitLayout.COLD_BELT_TEMPERATURES[0]),
            max_orbit=OrbitLayout.MAX_ORBIT,
        )


class OrbitLayout:
    """The orbits of one stellar system: `plans`, nearest first, and how they were reached (see the module docstring)."""

    # Temperatures (K) that set the zones: see the module docstring.
    INNER_EDGE_TEMPERATURE = 1500.0
    SNOW_LINE_TEMPERATURE = 170.0
    COLD_BELT_TEMPERATURES = (38.0, 51.0)  # farthest and nearest edge of the cold belt
    INNER_EDGE_DEATH_RADII = 1.5  # the inner edge is at least this many heat death radii of the star out
    MAX_ORBIT = 1.5e14  # m: nothing farther

    # Giants.
    GIANT_REFERENCE_MASS = 2.0e30  # kg: the star mass for which GIANT_CHANCE and GIANT_COUNT apply
    GIANT_CHANCE = 0.55  # of having any, for a star of the reference mass; grows with the square root of the mass
    GIANT_CHANCE_MAX = 0.9
    GIANT_COUNT = 2.6  # mean number, for a star of the reference mass; also grows with the square root of the mass
    GIANT_COUNT_SIGMA = 1.0
    GIANT_COUNT_MAX = 4
    FIRST_GIANT_SNOW_LINES = (1.2, 2.6)  # distance of the first giant, in snow lines
    GIANT_SPACING = (1.9, 0.18, 1.55, 2.8)  # ratio to the next one: median, sigma of its logarithm, lowest, highest

    # Belts.
    INNER_BELT_CHANCE_WITH_GIANTS = 0.85
    INNER_BELT_CHANCE_WITHOUT_GIANTS = 0.2
    INNER_BELT_OF_FIRST_GIANT = (0.45, 0.62)  # distance, in the first giant's
    INNER_BELT_OF_SNOW_LINE = (0.7, 1.0)  # without giants, in snow lines
    COLD_BELT_CHANCE_WITH_GIANTS = 0.7
    COLD_BELT_CHANCE_WITHOUT_GIANTS = 0.35
    COLD_BELT_OF_LAST_GIANT = (1.3, 1.8)
    FAILED_PLANET_CHANCE = 0.05  # each terrestrial place holds a belt instead of a planet

    # Terrestrial planets.
    ROCKY_COUNT_MEAN = 4.0
    ROCKY_COUNT_SIGMA = 1.3
    ROCKY_COUNT_MAX = 7
    ROCKY_SPACING = (1.55, 0.17, 1.3, 2.4)  # ratio to the next one, as GIANT_SPACING
    ROCKY_OUTSIDE_BELT = (1.45, 2.0)  # the outermost, in belts' distances inside
    ROCKY_OUTSIDE_GIANT = (0.25, 0.4)  # without a belt: the outermost, in the first giant's distances
    ROCKY_MAX_SNOW_LINES = 0.95  # the outermost never beyond this
    ROCKY_WITHOUT_GIANTS_SNOW_LINES = (0.6, 1.0)  # without giants and belt: the outermost, in snow lines
    ROCKY_OUTER_MIN_INNER_EDGES = 1.5  # the outermost is at least this many inner edges out

    MIN_SPACING = 1.25  # two orbits are never closer than this ratio

    # The initial system: orbit INITIAL_ORBIT_NUMBER is an earthlike planet outside the star's heat radius, with room for its moon.
    INITIAL_ORBIT_NUMBER = 3
    MAX_ATTEMPTS = 500
    FALLBACK_RATIOS = (0.5, 0.72, 1.0, 1.5)  # the fixed layout used when no draw fits: distances, in the third orbit's

    def __init__(self, plans: List[OrbitPlan], scales: SystemScales, attempts: int, needed_fallback: bool) -> None:
        self.plans: List[OrbitPlan] = plans
        self.scales: SystemScales = scales
        self.attempts: int = attempts  # layouts drawn until one met the initial system's conditions (1 otherwise)
        self.needed_fallback: bool = needed_fallback  # no layout met them: the fixed one was used

    @staticmethod
    def distance_at(luminosity: float, temperature: float) -> float:
        """The distance (m) from a star of the luminosity (W) at which a black body is at the temperature (K)."""
        return math.sqrt(luminosity / (16.0 * math.pi * Star.STEFAN_BOLTZMANN * temperature ** 4))

    # region The layout
    @staticmethod
    def generate(star: Star, my_random: random.Random, is_initial_system: bool) -> OrbitLayout:
        """The orbits of the star's system: none for a star of type O, unless it is the initial one. For the initial
        system, layouts are drawn until its orbit INITIAL_ORBIT_NUMBER is an earthlike planet that meets `_can_start`; if
        MAX_ATTEMPTS are not enough (a star whose zones leave no room), a fixed layout of four earthlike planets is used."""
        scales = SystemScales.of(star)
        if star.type is Star.Type.O and not is_initial_system:
            return OrbitLayout([], scales, 0, False)
        attempts = 0
        needed_fallback = False
        entries: List[Entry] = []
        while True:
            attempts += 1
            entries = OrbitLayout._draw(my_random, scales)
            if not is_initial_system or OrbitLayout._can_start(entries, star):
                break
            if attempts >= OrbitLayout.MAX_ATTEMPTS:
                entries = OrbitLayout._fallback(star, scales)
                needed_fallback = True
                break
        plans = [OrbitPlan(float(number), kind, distance) for number, (distance, kind) in enumerate(entries, start=1)]
        return OrbitLayout(plans, scales, attempts, needed_fallback)

    @staticmethod
    def _draw(my_random: random.Random, scales: SystemScales) -> List[Entry]:
        """One layout: giants, then the inner belt, the terrestrial planets inside it, and the cold belt."""
        giants = OrbitLayout._draw_giants(my_random, scales)
        inner_belt = OrbitLayout._draw_inner_belt(my_random, scales, giants)
        outer_limit = OrbitLayout._draw_rocky_outer_limit(my_random, scales, giants, inner_belt)
        cold_belt = OrbitLayout._draw_cold_belt(my_random, scales, giants)

        entries: List[Entry] = [(distance, OrbitKind.JOVIAN) for distance in giants]
        if inner_belt is not None:
            entries.append((inner_belt, OrbitKind.ASTEROID_BELT))
        if cold_belt is not None:
            entries.append((cold_belt, OrbitKind.ASTEROID_BELT))
        entries.extend(OrbitLayout._draw_rocky_zone(my_random, scales, outer_limit))
        return OrbitLayout._resolve_spacing(entries)

    @staticmethod
    def _draw_giants(my_random: random.Random, scales: SystemScales) -> List[float]:
        """The distances of the jovian planets, nearest first: none for some stars."""
        mass_factor = math.sqrt(scales.mass / OrbitLayout.GIANT_REFERENCE_MASS)
        chance = min(OrbitLayout.GIANT_CHANCE_MAX, OrbitLayout.GIANT_CHANCE * mass_factor)
        if my_random.random() >= chance:
            return []
        mean = OrbitLayout.GIANT_COUNT * mass_factor
        count = max(1, min(OrbitLayout.GIANT_COUNT_MAX, round(my_random.gauss(mean, OrbitLayout.GIANT_COUNT_SIGMA))))
        distance = scales.snow_line * my_random.uniform(*OrbitLayout.FIRST_GIANT_SNOW_LINES)
        result: List[float] = []
        for _ in range(count):
            if distance > scales.max_orbit:
                break
            result.append(distance)
            distance *= OrbitLayout._spacing(my_random, OrbitLayout.GIANT_SPACING)
        return result

    @staticmethod
    def _draw_inner_belt(my_random: random.Random, scales: SystemScales, giants: List[float]) -> Optional[float]:
        """The distance of the belt the first giant leaves inside, or of a belt at the snow line; None for no belt."""
        if giants:
            if my_random.random() < OrbitLayout.INNER_BELT_CHANCE_WITH_GIANTS:
                return giants[0] * my_random.uniform(*OrbitLayout.INNER_BELT_OF_FIRST_GIANT)
        elif my_random.random() < OrbitLayout.INNER_BELT_CHANCE_WITHOUT_GIANTS:
            return scales.snow_line * my_random.uniform(*OrbitLayout.INNER_BELT_OF_SNOW_LINE)
        return None

    @staticmethod
    def _draw_rocky_outer_limit(my_random: random.Random, scales: SystemScales,
                                giants: List[float], inner_belt: Optional[float]) -> float:
        """The distance of the outermost terrestrial planet: inside the belt or the first giant, and inside the snow line."""
        if inner_belt is not None:
            limit = inner_belt / my_random.uniform(*OrbitLayout.ROCKY_OUTSIDE_BELT)
        elif giants:
            limit = giants[0] * my_random.uniform(*OrbitLayout.ROCKY_OUTSIDE_GIANT)
        else:
            limit = scales.snow_line * my_random.uniform(*OrbitLayout.ROCKY_WITHOUT_GIANTS_SNOW_LINES)
        limit = min(limit, OrbitLayout.ROCKY_MAX_SNOW_LINES * scales.snow_line, scales.max_orbit)
        return max(limit, OrbitLayout.ROCKY_OUTER_MIN_INNER_EDGES * scales.inner_edge)

    @staticmethod
    def _draw_rocky_zone(my_random: random.Random, scales: SystemScales, outer_limit: float) -> List[Entry]:
        """The terrestrial places, from the outer limit inwards, each closer by a spacing ratio, until their count or the
        inner edge. Some places hold a belt instead of a planet. The first (the outermost) is always a planet."""
        count = max(1, min(OrbitLayout.ROCKY_COUNT_MAX,
                           round(my_random.gauss(OrbitLayout.ROCKY_COUNT_MEAN, OrbitLayout.ROCKY_COUNT_SIGMA))))
        distances = [outer_limit]
        while len(distances) < count:
            distance = distances[-1] / OrbitLayout._spacing(my_random, OrbitLayout.ROCKY_SPACING)
            if distance < scales.inner_edge:
                break
            distances.append(distance)
        entries: List[Entry] = []
        for index, distance in enumerate(distances):
            failed = index > 0 and my_random.random() < OrbitLayout.FAILED_PLANET_CHANCE
            entries.append((distance, OrbitKind.ASTEROID_BELT if failed else OrbitKind.EARTHLIKE))
        return entries

    @staticmethod
    def _draw_cold_belt(my_random: random.Random, scales: SystemScales, giants: List[float]) -> Optional[float]:
        """The distance of the cold belt, beyond the last giant, or None for no belt (or beyond MAX_ORBIT)."""
        chance = OrbitLayout.COLD_BELT_CHANCE_WITH_GIANTS if giants else OrbitLayout.COLD_BELT_CHANCE_WITHOUT_GIANTS
        if my_random.random() >= chance:
            return None
        distance = my_random.uniform(scales.cold_belt_min, scales.cold_belt_max)
        if giants:
            distance = max(distance, giants[-1] * my_random.uniform(*OrbitLayout.COLD_BELT_OF_LAST_GIANT))
        return distance if distance <= scales.max_orbit else None

    @staticmethod
    def _spacing(my_random: random.Random, spacing: Tuple[float, float, float, float]) -> float:
        """A ratio between neighbouring orbits: log-normal around its median, cut to the lowest and highest."""
        median, sigma, lowest, highest = spacing
        return min(highest, max(lowest, math.exp(my_random.gauss(math.log(median), sigma))))

    @staticmethod
    def _resolve_spacing(entries: List[Entry]) -> List[Entry]:
        """Nearest first, and no two orbits closer than MIN_SPACING: of two such, the belt is dropped (or the second
        if neither is a belt)."""
        result: List[Entry] = []
        for entry in sorted(entries, key=lambda e: e[0]):
            if result and entry[0] / result[-1][0] < OrbitLayout.MIN_SPACING:
                if entry[1] is OrbitKind.ASTEROID_BELT:
                    continue
                if result[-1][1] is OrbitKind.ASTEROID_BELT:
                    result[-1] = entry
                continue
            result.append(entry)
        return result
    # endregion

    # region The initial system
    @staticmethod
    def _can_start(entries: List[Entry], star: Star) -> bool:
        """True if the orbit INITIAL_ORBIT_NUMBER is an earthlike planet where the game can start: outside the star's
        death radius, and with room for a stable moon (World.MOON_MIN_ROOM_RADII, see World.moon_limit_in_radii)."""
        index = OrbitLayout.INITIAL_ORBIT_NUMBER - 1
        if len(entries) <= index:
            return False
        distance, kind = entries[index]
        return (kind is OrbitKind.EARTHLIKE
                and distance >= star.default_death_radius
                and World.moon_limit_in_radii(distance, star.mass) >= World.MOON_MIN_ROOM_RADII)

    @staticmethod
    def _fallback(star: Star, scales: SystemScales) -> List[Entry]:
        """Four earthlike planets, the third where the game can start (see _can_start): for a star whose zones left
        no layout."""
        room = World.MOON_MIN_ROOM_RADII / World.moon_limit_in_radii(1.0, star.mass)
        third = max(star.default_death_radius, room, OrbitLayout.ROCKY_OUTER_MIN_INNER_EDGES * scales.inner_edge)
        return [(third * ratio, OrbitKind.EARTHLIKE) for ratio in OrbitLayout.FALLBACK_RATIOS]
    # endregion
