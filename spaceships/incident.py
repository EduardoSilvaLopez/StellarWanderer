"""Incidents: random hardships that happen to the ship in space, bound or unbound. The check rolls every game
minute, over the time a frame covers. A hit happens at the end of that frame, at once, so that its notification sets
the time rate back to x1 before the next frame moves the clock. Nothing happens inside a settlement.

The only kind so far is the micrometeoroid impact. Where the ship is decides its impact profile (see ImpactProfile):
how often impacts come, and how many of them are medium or big. An impact opens an air leak in the hull, of the size it
drew. Sealing packs close the leak, one pack per click (see Ship.seal_leak); a settlement's dock
closes every leak at once. No incident waits in the queue, so none is saved: the check starts again after a load."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import random
from typing import TYPE_CHECKING, Any

from common.updating import Updatable, update_queue
from spaceships.malfunction import Instrument
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.people.player import Player
    from spaceships.ship import Ship


class Size(Enum):
    """How big an impact is: the leak it opens, the sealing packs it takes, and the air it wastes."""
    BASE = 'base'
    MEDIUM = 'medium'
    BIG = 'big'


@dataclass(frozen=True)
class ImpactProfile:
    """How impacts come in a place. `base` is the chance per game minute that an impact comes at all. `medium` and `big`
    are the shares of those impacts that are medium and big; the rest are base."""
    base: float
    medium: float
    big: float


BASE_PROFILE = ImpactProfile(base=1e-5, medium=0.09, big=0.01)  # in normal space
BELT_PROFILE = ImpactProfile(base=1e-3, medium=0.2, big=0.05)  # inside an asteroid belt
RING_PROFILE = ImpactProfile(base=1e-3, medium=0.1, big=0.02)  # inside a giant's ring
MALFUNCTION_BASE_CHANCE = 1e-5  # the chance per game minute of a malfunction, times the ship's precariousness
FAILURE_CONTINUE_CHANCE = 0.8  # The base for the number of instruments a malfunction breaks (see failures)

AIR_FACTOR: dict[Size, float] = {Size.BASE: 200.0, Size.MEDIUM: 2000.0, Size.BIG: 20000.0}  # x normal
PACKS: dict[Size, int] = {Size.BASE: 1, Size.MEDIUM: 2, Size.BIG: 4}  # sealing packs to close the leak
MAINTENANCE_LOSS: dict[Size, float] = {Size.BASE: 0.05, Size.MEDIUM: 0.1, Size.BIG: 0.15}  # of the whole bar, at once
FADE_SHARE = 0.5  # How much of its strength a leak texture loses once all its packs are in (see Leak.visibility)

def roll_size(profile: ImpactProfile) -> Size:
    """The size of an impact that comes in `profile`, drawn at random."""
    draw = random.random()
    if draw < profile.big:
        return Size.BIG
    if draw < profile.big + profile.medium:
        return Size.MEDIUM
    return Size.BASE

def failures() -> int:
    """How many instruments a malfunction breaks: the successes of FAILURE_CONTINUE_CHANCE before the first failure,
    and at least one."""
    count = 0
    while random.random() < FAILURE_CONTINUE_CHANCE:
        count += 1
    return max(1, count)


def profile_at(ship: Ship, current_datetime: datetime) -> ImpactProfile:
    """The impact profile of the ship's place: a giant's ring if the ship is in one, else an asteroid belt, else normal
    space. A ring is looked for first: it is the smaller of the two, and the belts are far from the giants."""
    from galaxies.asteroid_belt import AsteroidBelt
    from galaxies.jovian_world import JovianWorld
    position = ship.navigation.stellar_position(current_datetime)
    orbits = gem.current_environment.nearest_system.orbits
    for orbit in orbits:
        for planet in orbit.planets:
            if isinstance(planet, JovianWorld) and planet.in_ring(position, current_datetime):
                return RING_PROFILE
    for orbit in orbits:
        if isinstance(orbit, AsteroidBelt) and orbit.contains(position):
            return BELT_PROFILE
    return BASE_PROFILE


@dataclass
class Leak:
    """An open air leak: its seed (its crack is drawn from it, see graphics/incident_view.py), its size, and the sealing
    packs it still needs."""
    seed: int
    size: Size
    packs_left: int

    @staticmethod
    def new(seed: int, size: Size) -> Leak:
        return Leak(seed, size, PACKS[size])

    def visibility(self) -> float:
        """How strong the leak shows, from 1 with all its packs still to go in, down as they go in: the share of the
        packs still to go in, with FADE_SHARE of the rest taken off."""
        return 1.0 - FADE_SHARE * (1.0 - self.packs_left / PACKS[self.size])

    def serialize(self) -> dict[str, Any]:
        return {'seed': self.seed, 'size': self.size.value, 'packs_left': self.packs_left}

    @staticmethod
    def deserialize(src: dict[str, Any]) -> Leak:
        return Leak(src['seed'], Size(src['size']), src['packs_left'])


class IncidentCheck(Updatable):
    """The roll, every game minute, of whether an incident happens in it, with the base chance of the ship's profile
    (see profile_at). It keeps itself in the queue, and each impact that comes is scheduled as an ImpactIncident. Game
    time that passed in one frame (at a high time compression) is rolled minute by minute in one draw, so that several
    impacts can come in one frame; the first of them to happen sets the time back to x1 (see Notification.set)."""

    def __init__(self, player: Player) -> None:
        self.player: Player = player
        self.checked_until: datetime = gem.current_environment.date_time
        update_queue.add(self)

    def get_next_update(self) -> datetime:
        return self.checked_until + timedelta(minutes=1)

    def update(self, game_date_time: datetime) -> None:
        minutes = int((game_date_time - self.checked_until).total_seconds() // 60)
        self.checked_until += timedelta(minutes=minutes)
        if self.player.inside is None:
            profile = profile_at(self.player.ship, game_date_time)
            for _ in range(random.binomialvariate(minutes, profile.base)):
                ImpactIncident(self.player, game_date_time, profile).update(game_date_time)
            ship = self.player.ship
            for _ in range(random.binomialvariate(minutes, MALFUNCTION_BASE_CHANCE * ship.precariousness)):
                for _ in range(failures()):
                    ship.break_instrument(random.choice(list(Instrument)))  # any instrument, broken already or not
                ship.notification.set(ImpactIncident.MALFUNCTION_MESSAGE)
        update_queue.add(self)


class ImpactIncident(Updatable):
    """A micrometeoroid hits the ship at `moment`, if the pilot is then in space: it opens an air leak of a size drawn
    from `profile`, costs maintenance at once, and warns the pilot. Only the base size has its text written so far."""

    # The notification of each size of impact (TODO: the texts of the medium and big ones), and of a malfunction.
    IMPACT_MESSAGES: dict[Size, str] = {
        Size.BASE: 'WARNING: Micrometeoroid impact detected, air leak. Repair using sealing packs.',
        Size.MEDIUM: 'CRITICAL: Small meteoroid impact detected, air leak. Repair using sealing packs.',
        Size.BIG: 'CRITICAL: Meteoroid impact detected, severe air leak. Repair IMMEDIATELY using sealing packs.',
    }
    MALFUNCTION_MESSAGE = 'WARNING: Instrument malfunction detected. Repair using a repair kit.'

    def __init__(self, player: Player, moment: datetime, profile: ImpactProfile) -> None:
        self.player: Player = player
        self.moment: datetime = moment
        self.profile: ImpactProfile = profile

    def get_next_update(self) -> datetime:
        return self.moment

    def update(self, game_date_time: datetime) -> None:
        if self.player.inside is not None:
            return
        ship = self.player.ship
        size = roll_size(self.profile)
        ship.open_leak(Leak.new(random.getrandbits(32), size), self.moment)
        ship.notification.set(ImpactIncident.IMPACT_MESSAGES[size], 'impact_micrometeoroid')
