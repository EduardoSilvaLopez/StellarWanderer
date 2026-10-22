from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Iterator, List, Optional, Tuple, Union

import math

import logging

from common import audio

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from galaxies.world import World
    from galaxies.km2 import Km2
    from galaxies.rock import Rock
    from galaxies.ore_mine import OreMine
    from galaxies.outpost import Outpost
    from galaxies.asteroid import Asteroid

logger = logging.getLogger(__name__)

# Everything the beam can hit.
Target = Union['Rock', 'OreMine', 'Outpost']


class Scanner:
    """Aiming and targeting: what the crosshair hits (rocks, ore mines, outposts) and ore collection.

    The scanner decides what is targeted; the laser (spaceships/laser.py) only fires at it. While bound, the beam
    (drawn by graphics/laser.py while `Laser.firing` is set, i.e. SPACE held on a rock or on nothing) is a shallow
    slope from the emitter (half of Ship.HEIGHT below the camera) down to the ground at
    MAX_LENGTH metres ahead (horizontally), so it hits the ground at full range when the ship is low. Rocks closer
    than the slope's height at their distance pass over the beam. A hit counts only within MAX_LENGTH metres of the
    camera: from higher up the beam is steeper and longer, and what it meets on the ground is out of reach.
    `targeted_rock` and `targeted_mine` are what the scanner panel (graphics/instruments/scanner.py, a different class
    with the same name) shows, and what `activate` heats or collects from.

    Unbound, the targeted body (`GameEnvironment.targeted_body`) can be an asteroid that is not yet fully scanned: it is
    `scan_asteroid`, and `scan_problem` says why the beam cannot work on it now (None if it can): out of range, too fast
    or not in the crosshair (the limits are Asteroid's SCAN_*). While SPACE is held and there is no problem, the scan
    advances in game time (`Asteroid.advance_scan`), with the 'scan' buzz and no laser, which stays off until SPACE
    is released. The time scale is capped at its minimum then, and stays there: the progress of the first frame at the
    old scale does not count. When it reaches 1, the ship says so.
    """

    MAX_LENGTH = 200  # metres

    def __init__(self, ship: Ship) -> None:
        self.ship = ship
        self.target: Optional[Target] = None
        self.scan_asteroid: Optional[Asteroid] = None  # the targeted asteroid, if it can still be scanned
        self.scan_problem: Optional[str] = None  # why it cannot be now, for the scanner panel
        self._scan_held: bool = False  # SPACE went down on an asteroid and is still down: the laser stays off
        # the rock with an adjective whose scan was announced since SPACE went down
        self._announced_rock: Optional[Rock] = None
        self.start_x = 0.0
        self.start_y = 0.0
        self.start_z = 0.0
        self.end_x = 0.0
        self.end_y = 0.0
        self.end_z = 0.0

    # region Targets
    # Imported here, not at module level: galaxies.ore_mine needs spaceships.ship to load first.
    @property
    def targeted_rock(self) -> Optional[Rock]:
        from galaxies.rock import Rock
        return self.target if isinstance(self.target, Rock) else None

    @property
    def targeted_mine(self) -> Optional[OreMine]:
        from galaxies.ore_mine import OreMine
        return self.target if isinstance(self.target, OreMine) else None

    @property
    def targeted_outpost(self) -> Optional[Outpost]:
        from galaxies.outpost import Outpost
        return self.target if isinstance(self.target, Outpost) else None

    def update_target(self) -> None:
        """Recompute the beam's start and end from the ship's attitude and position, then the object it hits
        first. Called once per frame, so the scanner always shows what is in the crosshair."""
        ship = self.ship
        self.target = None
        self.scan_asteroid = self.scan_problem = None
        if not ship.is_bound:
            self._look_for_asteroid()
        offset = ship.HEIGHT / 2  # the emitter, below the camera
        forward, up = ship.attitude.forward, ship.attitude.up

        # Unbound, the beam is stored relative to the ship. Bound, it is in surface coordinates and starts above
        # the ship's position, where forward is horizontal and up is vertical.
        origin = (ship.position.x, ship.position.y, ship.position.z) if ship.is_bound else (0.0, 0.0, 0.0)

        # Start just below and ahead of the camera (5 m ahead, so the camera's own geometry is not hit).
        self.start_x, self.start_y, self.start_z = (
            o + f * 5.0 - u * offset for o, f, u in zip(origin, forward, up)
        )

        if not ship.is_bound:
            self.end_x, self.end_y, self.end_z = (
                o + f * self.MAX_LENGTH - u * offset for o, f, u in zip(origin, forward, up)
            )
            return

        # Bound, the beam slopes down to the ground MAX_LENGTH metres ahead.
        self.end_x = origin[0] + forward[0] * self.MAX_LENGTH
        self.end_y = 0.0
        self.end_z = origin[2] + forward[2] * self.MAX_LENGTH

        # No Km2 while bound means too high: nothing is in reach.
        if ship.position.km2 is None:
            return

        import game_environment as gem
        hit = self._closest_hit(gem.current_environment.fixed_world)
        if hit is None:
            return
        target, t = hit

        # The beam ends where it hits: start + t * (end - start). It slopes, so the height moves too.
        hit_x = self.start_x + t * (self.end_x - self.start_x)
        hit_y = self.start_y + t * (self.end_y - self.start_y)
        hit_z = self.start_z + t * (self.end_z - self.start_z)

        # The beam is long when the ship is high (it runs down to the ground MAX_LENGTH metres ahead, horizontally), but
        # a hit counts only within MAX_LENGTH of the camera: nothing is targeted, or heated, farther than that.
        if math.dist(origin, (hit_x, hit_y, hit_z)) > self.MAX_LENGTH:
            return
        self.target = target
        self.end_x, self.end_y, self.end_z = hit_x, hit_y, hit_z
    # endregion

    # region Asteroids
    def _look_for_asteroid(self) -> None:
        """Sets `scan_asteroid` to the targeted body if it is an asteroid still to scan, and `scan_problem` to what
        keeps the beam from working on it."""
        import game_environment as gem
        from common.units import format_compact_distance
        from galaxies.asteroid import Asteroid
        environment = gem.current_environment
        body = environment.targeted_body
        if not isinstance(body, Asteroid) or body.scan_progress >= 1.0:
            return
        self.scan_asteroid = body

        ship = self.ship
        distance = ship.navigation.distance_to_body_centre(body)
        reach = min(Asteroid.SCAN_RANGE_DIAMETERS * 2.0 * body.radius, Asteroid.SCAN_MAX_RANGE)
        relative_speed = math.dist(tuple(ship.velocity.as_vector()),
                                   tuple(body.calculate_stellar_velocity(environment.date_time)))
        direction = ship.navigation.direction_to_body(body, environment.date_time)
        cosine = direction.dot(ship.attitude.forward) / max(direction.length(), 1e-9)
        in_crosshair = distance <= body.radius or cosine >= math.cos(math.asin(body.radius / distance))
        if distance - body.radius > reach:
            self.scan_problem = (f"Out of range: {format_compact_distance(distance - body.radius)}, "
                                 f"{format_compact_distance(reach)} at most")
        elif relative_speed > Asteroid.SCAN_MAX_SPEED:
            self.scan_problem = f"Too fast: {relative_speed:.0f} m/s, {Asteroid.SCAN_MAX_SPEED:.0f} m/s at most"
        elif not in_crosshair:
            self.scan_problem = "Aim at the asteroid"

    def _scan(self, asteroid: Asteroid, game_seconds: float) -> None:
        """The beam works on the asteroid for the time of this frame (see the class docstring for the time scale)."""
        player = self.ship.owner
        if player.time_scale > player.TIME_SCALE_MIN:
            player.time_scale = player.TIME_SCALE_MIN
            return
        if asteroid.advance_scan(game_seconds):
            self.ship.notification.set(
                f"Asteroid {asteroid.name} scanned, {player.get_title()} Pilot: the results are in the ship computer.",
                'mission_delivered')
    # endregion

    # region Actions
    def activate(self, time_passed: int) -> Scanner:
        """SPACE held. On a targeted ore mine, transfer its ore to the ship (the beam stays off). On a targeted outpost,
        holding the key does nothing here: Numpad 5 opens its mission board or talks to its com officer (see main.py).
        On a rock with an adjective,
        the beam stays off and a message says the rock has been scanned (once per press, see release). Otherwise switch
        the beam on, heating the targeted rock if there is one. Uses the target found by this frame's update_target, so
        it does not search again."""

        if self.targeted_mine is not None:
            mine: OreMine = self.targeted_mine
            if mine.content > 0:
                self.ship.laser.cease_fire()
                ore_transfer = int(min(self.ship.cargo_hold.free_capacity(), mine.content))
                logger.debug(
                    "Transfer Ore to Ship:"
                    f"\nCargo capacity: {self.ship.cargo_hold.capacity}"
                    f"\nFree capacity: {self.ship.cargo_hold.free_capacity()}"
                    f"\nMine content: {mine.content}"
                    f"\nOre transfer: {ore_transfer}"
                    )
                self.ship.cargo_hold.ore += ore_transfer
                mine.content -= ore_transfer
                if ore_transfer > 0:
                    audio.play('ore_collected')
            return self

        if self.targeted_outpost is not None:
            return self

        self._scan_held = self._scan_held or self.scan_asteroid is not None
        scanning = self.scan_asteroid is not None and self.scan_problem is None
        audio.set_loop('scan', scanning)
        if scanning:
            self._scan(self.scan_asteroid, time_passed)
        if self._scan_held:
            self.ship.laser.cease_fire()
            return self

        rock = self.targeted_rock
        if rock is not None and rock.adjective:
            # A rock with an adjective is scanned, not heated: the laser stays off, so it cannot be molten. Announced
            # once per press.
            self.ship.laser.cease_fire()
            if self._announced_rock is not rock:
                self._announced_rock = rock
                from common.dialogs.messages import Message, show_message
                show_message(Message(
                    title='ROCK SCANNED',
                    text=f"This {rock.adjective} rock has been scanned, and the results stored in the ship computer, "
                         "forbidding it from being damaged.",
                ))
                for mission in self.ship.owner.missions:
                    mission.on_rock_scanned(rock)
            return self

        self.ship.laser.fire(rock, time_passed)
        return self

    def release(self) -> Scanner:
        """SPACE is up: the next press of it announces a scanned rock again."""
        self._announced_rock = None
        self._scan_held = False
        audio.set_loop('scan', False)
        return self

    def deactivate(self) -> Scanner:
        self.ship.laser.cease_fire()
        audio.set_loop('scan', False)
        return self
    # endregion

    # region Search
    def _closest_hit(self, world: World) -> Optional[Tuple[Target, float]]:
        """The target the beam enters first, with its t-value, or None."""
        hits = []
        for target, hit_t in self._candidates(world):
            t = hit_t(target)
            if t is not None:
                hits.append((target, t))
        return min(hits, key=lambda hit: hit[1], default=None)

    def _candidates(self, world: World) -> Iterator[Tuple[Target, Callable[[Target], Optional[float]]]]:
        """Every target within reach (the rocks, mines and outpost of the Km2s near the beam), each with the test that
        finds where the beam enters it."""
        for km2 in self._get_relevant_km2s(world):
            for rock in km2.rocks:
                yield rock, self._rock_entry
            for field in km2.ore_fields:
                for mine in field.mines:
                    yield mine, self._mine_entry
            if km2.outpost:
                yield km2.outpost, self._outpost_entry

    def _get_relevant_km2s(self, world: World) -> List[Km2]:
        """Km2s whose square lies within the beam's reach in longitude and latitude. A rough filter, applied
        before the per-object tests."""
        position = self.ship.position
        reach = self.MAX_LENGTH
        return [
            km2 for km2 in world.km2s
            if position.x - reach - km2.SIZE < km2.longitude < position.x + reach
            and position.z - reach - km2.SIZE < km2.latitude < position.z + reach
        ]
    # endregion

    # region Beam geometry
    @staticmethod
    def _clip_slab(start: float, delta: float, low: float, high: float, t_min: float,
                   t_max: float) -> Optional[Tuple[float, float]]:
        """Narrow [t_min, t_max] to the part of the beam between the planes low and high on one axis."""
        if abs(delta) <= 1e-9:  # parallel to the slab: all or nothing
            return (t_min, t_max) if low <= start <= high else None
        t1 = (low - start) / delta
        t2 = (high - start) / delta
        return max(t_min, min(t1, t2)), min(t_max, max(t1, t2))

    def _beam_enters_box(self, start: Tuple[float, float, float], end: Tuple[float, float, float],
                         half_sizes: Tuple[float, float, float]) -> Optional[float]:
        """Slab test of the segment start -> end against an axis-aligned box centred on the origin.
        Returns the t-value where the beam enters, or None."""
        t_min, t_max = 0.0, 1.0
        for s, e, half in zip(start, end, half_sizes):
            clipped = self._clip_slab(s, e - s, -half, half, t_min, t_max)
            if clipped is None:
                return None
            t_min, t_max = clipped
        return t_min if t_min <= t_max else None

    def _beam_within_reach(self, x: float, y: float, z: float, radius: float) -> bool:
        """Whether the beam segment passes within radius of (x, y, z)."""
        dx = self.end_x - self.start_x
        dy = self.end_y - self.start_y
        dz = self.end_z - self.start_z
        length_sq = dx * dx + dy * dy + dz * dz
        px = x - self.start_x
        py = y - self.start_y
        pz = z - self.start_z
        t = 0.0 if length_sq <= 1e-12 else max(0.0, min(1.0, (px * dx + py * dy + pz * dz) / length_sq))
        gx = px - t * dx
        gy = py - t * dy
        gz = pz - t * dz
        return gx * gx + gy * gy + gz * gz <= radius * radius

    def _beam_enters_oriented_box(self, centre: Tuple[float, float, float], half_sizes: Tuple[float, float, float],
                                  tilt_degrees: float, orientation_degrees: float) -> Optional[float]:
        """t-value where the beam first enters a box centred on `centre`, or None. The box is tilted by tilt_degrees
        around its local Z axis, then turned by orientation_degrees around Y (0 = unrotated, positive = clockwise
        from north, the same convention as the ship's forward vector)."""
        # Cheap rejection first: the box is turned about its centre, so it lies within its circumscribed sphere.
        radius = math.sqrt(sum(half * half for half in half_sizes))
        if not self._beam_within_reach(centre[0], centre[1], centre[2], radius):
            return None

        tilt = math.radians(tilt_degrees)
        cos_t, sin_t = math.cos(tilt), math.sin(tilt)
        orientation = math.radians(orientation_degrees)
        cos_o, sin_o = math.cos(orientation), math.sin(orientation)

        # Undo the rotation and tilt, in reverse order, to bring the beam's endpoints into the box's local frame.
        def to_local(world_x: float, world_y: float, world_z: float) -> Tuple[float, float, float]:
            dx = world_x - centre[0]
            dy = world_y - centre[1]
            dz = world_z - centre[2]
            x1 = dx * cos_o - dz * sin_o
            z1 = dx * sin_o + dz * cos_o
            x2 = x1 * cos_t + dy * sin_t
            y2 = -x1 * sin_t + dy * cos_t
            return x2, y2, z1

        return self._beam_enters_box(
            to_local(self.start_x, self.start_y, self.start_z),
            to_local(self.end_x, self.end_y, self.end_z),
            half_sizes,
        )

    def _rock_entry(self, rock: Rock) -> Optional[float]:
        """t-value where the beam first enters the rock, or None. The test is the rock's bounding cube, of side
        rock.size, centred on (longitude, altitude, latitude), tilted by rock.tilt and turned by rock.orientation.
        The boulder drawn inside it (graphics/rock_shape.py) touches the cube on every axis, but is not the whole
        cube, so a beam can hit the cube a little before the visible rock; close enough for aiming."""
        half = rock.size / 2.0
        return self._beam_enters_oriented_box(
            (rock.longitude, rock.altitude, rock.latitude), (half, half, half), rock.tilt, rock.orientation,
        )

    def _mine_entry(self, mine: OreMine) -> Optional[float]:
        """t-value where the beam first enters the mine, or None. A mine is a vertical cylinder of radius
        MINE_RADIUS and height MINE_HEIGHT, standing on the ground at (longitude, latitude). Being rotationally
        symmetric, it needs no un-rotation, unlike rocks."""
        start_x = self.start_x - mine.longitude
        start_z = self.start_z - mine.latitude
        dx = self.end_x - self.start_x
        dz = self.end_z - self.start_z
        dy = self.end_y - self.start_y

        t_min, t_max = 0.0, 1.0

        # Circular cross-section (XZ plane): solve |start + t*d|^2 = radius^2.
        a = dx * dx + dz * dz
        b = 2.0 * (start_x * dx + start_z * dz)
        c = start_x * start_x + start_z * start_z - mine.MINE_RADIUS ** 2
        if abs(a) > 1e-9:
            discriminant = b * b - 4.0 * a * c
            if discriminant < 0:
                return None
            root = math.sqrt(discriminant)
            t_min = max(t_min, (-b - root) / (2.0 * a))
            t_max = min(t_max, (-b + root) / (2.0 * a))
        elif c > 0:  # not moving across the circle, and outside it
            return None

        # Height bounds (Y axis).
        clipped = self._clip_slab(self.start_y, dy, 0.0, mine.MINE_HEIGHT, t_min, t_max)
        if clipped is None:
            return None
        t_min, t_max = clipped
        return t_min if t_min <= t_max else None

    def _outpost_entry(self, outpost: Outpost) -> Optional[float]:
        """t-value where the beam first enters the outpost building, or None. The building is a box of
        Outpost.WIDTH x HEIGHT x DEPTH standing on the ground at (longitude, latitude), with its width along local x
        and its depth along local z; the door is on the local +z side, so orientation is the heading the door faces."""
        from galaxies.outpost import Outpost
        return self._beam_enters_oriented_box(
            (outpost.longitude, Outpost.HEIGHT / 2, outpost.latitude),
            (Outpost.WIDTH / 2, Outpost.HEIGHT / 2, Outpost.DEPTH / 2),
            0.0,
            outpost.orientation,
        )
    # endregion
