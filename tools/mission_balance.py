"""Balance of the missions' rewards against the time they take, for one ship.

For each kind of mission and kind of issuing settlement it samples the offers the boards would make over some days (the
game's own `Mission.offered_on`), takes the median distance of the trip, the Travel autopilot's duration for it (the
planner of spaceships/long_distance_advice.py, with the energy of the ship across the legs) and the reputation the
mission gives (the mission's own `give_reward`, so that a change of the formulas is followed). The scenario is that of
the constants below. Nothing is saved: the game is started in memory and never written.

Run from anywhere:
    python tools/mission_balance.py [--seeds 1 2 3] [--days 365] [--ship TwsMiner] [--load 0.5] [--out table.md]

Not in the durations: take-off and landing, finding or scanning a rock, mining, and the pilot's choices. The ore
comes from a world of the issuer's planetary system. A trip is a
straight line from where the settlement is when the offer is made; the planets' motion is not followed.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Iterable

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402  (first: it loads the packages in the order the game does)
import game_environment as gem  # noqa: E402
import galaxies.people.player as player_module  # noqa: E402
from common.units import format_compact_distance  # noqa: E402
from galaxies.constants import EPOCH  # noqa: E402
from galaxies.missions import (DeliverOre, DeliverPackage, DeliverWater, Mission, ScanAsteroid,  # noqa: E402
                               ScanRock, ScoopGiant, ScoopStar)
from galaxies.missions.mission_board import KINDS, LOCAL_KINDS  # noqa: E402
from galaxies.missions.terms import Terms  # noqa: E402
from galaxies.settlement import Settlement  # noqa: E402
from galaxies.settlement_kind import SettlementKind  # noqa: E402
from galaxies.body import Body  # noqa: E402
from spaceships.long_distance_advice import LongDistanceAdvisor, energy_cost, make_plan  # noqa: E402
from spaceships.ship import Ship  # noqa: E402
import spaceships.ship_configurations  # noqa: E402,F401  (registers the ships in Ship.by_name)

SECONDS_PER_DAY = 86400.0
SHIP_NAME = 'TwsMiner'
LOAD_SHARE = 0.5  # of the hold's capacity, as mass the engines push
WATER_SCOOP_KG_PER_SECOND = Ship.SCOOP_WATER_KG_PER_SECOND
WITH_SCOOP = (DeliverWater, ScoopStar, ScoopGiant)  # the kinds that need the scoop (its mass counts)


@dataclass(frozen=True)
class Route:
    """Where a mission sends the pilot: out from the issuer to `target` and, if `back`, home again."""
    target: Body | None  # None: no flight to count (nothing to fly to, or the trip is not a Travel one)
    back: bool
    hold_seconds: float = 0.0  # time spent at the target (the scan, the scoop)
    stop_radius: float | None = None  # the leg ends this far from the target's centre (a star's heat radius)


@dataclass(frozen=True)
class ShipModel:
    """What the planner needs of the ship in the scenario."""
    acceleration: float
    brake: float
    energy_max: float
    energy_per_delta_v: float  # Wh per m/s
    store_days: float  # the days the least of air, water and food lasts, full

    @staticmethod
    def of(ship: Ship, load_share: float, scoop: bool) -> ShipModel:
        ship.has_scoop = scoop
        mass = ship.MASS + ship.equipment_mass() + load_share * ship.cargo_hold.capacity
        hold = ship.cargo_hold
        return ShipModel(ship.FORWARD_BACKWARD_ACC, ship.BRAKE_ACC, ship.energy_max, ship.energy_per_delta_v(mass),
                         min(hold.air_max, hold.water_max, hold.food_max))


@dataclass(frozen=True)
class Leg:
    seconds: float
    energy: float  # Wh spent


@dataclass
class Sample:
    """One offer reduced to plain numbers: the next seed replaces the galaxy, and with it the offer's settlements."""
    kind: type
    issuer: SettlementKind
    terms: Terms
    back: bool
    hold_seconds: float
    ends_at_radius: bool
    distance: float | None  # m, one way, from the issuer to where the leg ends; None when there is no flight
    services: bool  # the target has a settlement (the planner then keeps less in reserve)
    is_world: bool
    radius: float  # of the target
    home_is_world: bool
    home_radius: float  # of the issuer's body
    reputation: float


# region Routes
def _water_source(mission: DeliverWater, origin: Settlement, date) -> Body | None:
    """The nearest icy world of the tier the mission pays for, else its asteroid."""
    worlds = mission.icy_worlds() or mission.icy_stellar_worlds()
    if worlds:
        here = tuple(origin.stellar_position(date))
        return min(worlds, key=lambda world: math.dist(here, tuple(world.calculate_stellar_position(date))))
    return mission.asteroid()


def _mine_world(origin: Settlement, date) -> Body | None:
    """Where the ore comes from: a rocky world of the issuer's planetary system (its planet and moons, or the moons of
    its giant), other than its own; the one at the median distance. A portal base has no planet: any rocky world of the
    system. None if there is none."""
    from galaxies.outpost import Outpost
    from galaxies.rocky_world import RockyWorld
    if isinstance(origin, Outpost):
        host = origin.planet.parent_planet or origin.planet
        worlds = ([host] if host is origin.planet else []) + list(host.moons)
    else:
        worlds = origin.stellar_system.get_all_worlds()
    here = tuple(origin.stellar_position(date))
    candidates = sorted((world for world in worlds if isinstance(world, RockyWorld) and world is not origin.body),
                        key=lambda world: math.dist(here, tuple(world.calculate_stellar_position(date))))
    return candidates[(len(candidates) - 1) // 2] if candidates else None


def route_of(mission: Mission, load: float) -> Route:
    date = mission.created_at
    origin = mission.issuer_settlement
    if isinstance(mission, DeliverOre):
        return Route(_mine_world(origin, date), True)
    if isinstance(mission, DeliverPackage):
        return Route(mission.destination_settlement.body, False)
    if isinstance(mission, DeliverWater):
        return Route(_water_source(mission, origin, date), True, load / WATER_SCOOP_KG_PER_SECOND)
    if isinstance(mission, ScanRock):
        return Route(mission._world(), True)  # a rock on the issuer's own world is a flight over the ground
    if isinstance(mission, ScanAsteroid):
        asteroid = mission.asteroid()
        from galaxies.asteroid import Asteroid
        return Route(asteroid, True, Asteroid.SCAN_SECONDS_PER_SQRT_KM * math.sqrt(2.0 * asteroid.radius / 1000.0))
    if isinstance(mission, ScoopStar):
        star = origin.stellar_system.star
        return Route(star, True, mission.COLLECTION_SECONDS, star.default_heat_radius)
    if isinstance(mission, ScoopGiant):
        return Route(mission.giant_world(), True, mission.COLLECTION_SECONDS)
    raise TypeError(f"{type(mission).__name__} has no route: add it to route_of")


def trip_distance(route: Route, origin: Settlement, date) -> float | None:
    """The distance of one leg, from the issuer to the surface of the target (or to its stop radius), in metres.
    0 for the issuer's own world; None when there is no flight."""
    if route.target is None:
        return None
    if route.target is origin.body:
        return 0.0
    centre = math.dist(tuple(origin.stellar_position(date)), tuple(route.target.calculate_stellar_position(date)))
    return max(0.0, centre - (route.stop_radius if route.stop_radius is not None else route.target.radius))
# endregion


# region Flight
def fly(model: ShipModel, distance: float, radius: float, is_world: bool, services: bool, energy: float,
        ends_at_radius: bool = False) -> Leg | None:
    """One leg flown by the Travel autopilot and the pilot's last leg, as the advisor plans them (see its docstring):
    from rest to rest over `distance`, starting with `energy` Wh. None when no plan keeps the reserve ("Too far").
    `ends_at_radius`: the leg ends at a given distance from the centre, not at the target's surface: no last leg."""
    advisor = LongDistanceAdvisor
    if distance <= 0.0:
        return Leg(0.0, 0.0)
    accelerations = (model.acceleration, model.brake)
    if ends_at_radius:
        end_distance = 0.0
    elif distance <= advisor.PLAN_END_DISTANCE + advisor.END_TOLERANCE:
        end_distance = ((advisor.NEAR_END_RADII if is_world else advisor.NEAR_END_RADII_OUTSIDE) - 1.0) * radius
    else:
        end_distance = advisor.PLAN_END_DISTANCE
    leg_energy, leg_time = advisor._final_leg(accelerations, end_distance) if end_distance > 0.0 else (0.0, 0.0)
    reserve = advisor.RESERVE_WITH_SERVICES if services else advisor.RESERVE_WITHOUT_OUTPOST
    budget = (energy - reserve * model.energy_max) / model.energy_per_delta_v - leg_energy
    margin = advisor.ENERGY_MARGIN * model.energy_max / model.energy_per_delta_v
    plan_distance = max(distance - end_distance, 1.0)
    plan = (make_plan(plan_distance, 0.0, 0.0, *accelerations, budget - margin)
            or make_plan(plan_distance, 0.0, 0.0, *accelerations, budget))
    if plan is None or plan.eta is None:
        return None
    return Leg(plan.eta + leg_time, (energy_cost(plan.peak_speed, 0.0, 0.0) + leg_energy) * model.energy_per_delta_v)


@dataclass(frozen=True)
class Trip:
    days: float
    feasible: bool
    note: str


def trip_days(model: ShipModel, offer: Sample, distance: float, services: bool) -> Trip:
    """The whole trip of an offer over `distance`, from full energy at the issuer: out, the time at the target, and
    back if the mission asks."""
    out = fly(model, distance, offer.radius, offer.is_world, services, model.energy_max, offer.ends_at_radius)
    if out is None:
        return Trip(math.inf, False, "too far for the energy")
    seconds = out.seconds + offer.hold_seconds
    if offer.back:
        home = fly(model, distance, offer.home_radius, offer.home_is_world, True, model.energy_max - out.energy)
        if home is None:
            return Trip(math.inf, False, "cannot get back")
        seconds += home.seconds
    days = seconds / SECONDS_PER_DAY
    return Trip(days, True, "" if days <= model.store_days * (1.0 - LongDistanceAdvisor.RESERVE_WITH_SERVICES)
                else "supplies run out")
# endregion


# region Sampling and rewards
def pilot_ship(player: player_module.Player, name: str) -> Ship:
    return Ship.by_name[name](player)


def reward_at_delivery(mission: Mission, player: player_module.Player, load: float) -> float:
    """The reputation the mission's own `give_reward` gives, with the deadline at its longest and the delivery halfway
    between its shortest and its longest deadline."""
    terms = mission.terms
    mission.deadline = mission.created_at + timedelta(days=terms.deadline_days_max)
    delivery = mission.created_at + timedelta(days=(terms.deadline_days_min + terms.deadline_days_max) / 2.0)
    environment = gem.current_environment
    kept = environment.clock.seconds
    environment.clock.seconds = (delivery - EPOCH).total_seconds()
    if isinstance(mission, DeliverWater):
        mission.delivered = load
    before = player.reputation
    mission.give_reward(player)
    gain = player.reputation - before
    environment.clock.seconds = kept
    return gain


def offers(system, days: int) -> Iterable[Mission]:
    """Every offer the settlements of the system would make in `days` days from the epoch: the outposts' own kinds, and
    all of them at the portal base. Taking by others is ignored: it is the offers made that are counted."""
    for settlement in system.settlements():
        kinds = KINDS if settlement.kind is SettlementKind.PORTAL_BASE else LOCAL_KINDS
        for index in range(days):
            day = EPOCH + timedelta(days=index)
            for kind in kinds:
                mission = kind.offered_on(day, settlement)
                if mission is not None:
                    yield mission


def sample(seed: int, days: int, load: float) -> list[Sample]:
    main.start_game('new', seed)
    system = gem.current_environment.nearest_system
    player = player_module.current_player
    samples: list[Sample] = []
    for mission in offers(system, days):
        route = route_of(mission, load)
        origin = mission.issuer_settlement
        target = route.target
        if isinstance(mission, (DeliverWater, DeliverOre)) and target is None:
            continue  # the water or the ore can come from anywhere: no trip to count
        samples.append(Sample(
            type(mission), mission.issuer_kind, mission.terms, route.back, route.hold_seconds,
            route.stop_radius is not None, trip_distance(route, origin, mission.created_at),
            target is not None and target.has_settlements(), target is not None and target.is_world,
            0.0 if target is None else target.radius, origin.body.is_world, origin.body.radius,
            reward_at_delivery(mission, player, load)))
    return samples
# endregion


# region Report
@dataclass
class Row:
    name: str
    issuer: str
    count: int
    distance: float | None
    surface_share: float
    legs: int
    days: float | None
    median_days: float | None
    deadline_days: int
    delivery_days: float
    reputation: float
    penalty: float
    note: str


def row_of(group: list[Sample], model_for: Callable[[type], ShipModel]) -> Row:
    first = group[0]
    terms = first.terms
    flights = [s for s in group if s.distance is not None]
    reputation = statistics.median(s.reputation for s in group)
    delivery = (terms.deadline_days_min + terms.deadline_days_max) / 2.0
    row = Row(first.kind.__name__, first.issuer.value, len(group), None, 0.0, 0, None, None, terms.deadline_days_max,
              delivery, reputation, terms.failure_penalty, "no flight to count")
    if not flights:
        return row
    model = model_for(first.kind)
    airborne = [s for s in flights if s.distance > 0.0]  # the others are flights over the ground: no Travel
    row.surface_share = 1.0 - len(airborne) / len(flights)
    if not airborne:
        row.note = "all over the ground"
        return row
    flights = airborne
    median_distance = statistics.median(s.distance for s in flights)
    row.distance = median_distance
    row.legs = 2 if first.back else 1
    typical = flights[len(flights) // 2]  # for what does not vary: the kind of target
    services = sum(1 for s in flights if s.services) * 2 > len(flights)
    trips = [trip_days(model, s, s.distance, s.services) for s in flights]
    finite = [trip.days for trip in trips if trip.feasible]
    row.median_days = statistics.median(finite) if finite else None
    at_median = trip_days(model, typical, median_distance, services)
    row.days = at_median.days if at_median.feasible else None
    notes = [at_median.note] if at_median.note else []
    if row.surface_share > 0.0:
        notes.append(f"{row.surface_share:.0%} of the offers are over the ground, not counted")
    infeasible = len(trips) - len(finite)
    if infeasible:
        notes.append(f"{infeasible}/{len(trips)} offers too far")
    row.note = "; ".join(notes)
    return row


def render(rows: list[Row], model: ShipModel, ship_name: str, load: float, seeds: list[int], days: int) -> str:
    def cell(value: float | None, fmt: str) -> str:
        return "-" if value is None else format(value, fmt)

    lines = [
        f"# Mission balance: {ship_name}, {load:.0%} loaded",
        "",
        f"Seeds {', '.join(str(seed) for seed in seeds)}, offers of {days} days each. Deadline: the longest; delivery: "
        "halfway between the shortest and the longest. Distances and rewards are medians over the offers; the days are "
        "the Travel plan at the median distance (the median of the offers' own days in brackets).",
        "",
        "| Mission | Issuer | Offers | Median distance | Legs | Travel days | Deadline | Delivery | Reputation "
        "| Rep/Travel day | Failure | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        distance = "-" if row.distance is None else format_compact_distance(row.distance)
        travel = cell(row.days, '.2f') + ("" if row.median_days is None else f" ({row.median_days:.2f})")
        per_day = "-" if not row.days else format(row.reputation / row.days, '.2f')
        lines.append(f"| {row.name} | {row.issuer} | {row.count} | {distance} | {row.legs or '-'} | {travel} "
                     f"| {row.deadline_days} d | {row.delivery_days:g} d | {row.reputation:.2f} | {per_day} "
                     f"| {row.penalty:g} | {row.note} |")
    lines += ["", f"Ship: acceleration {model.acceleration:g} m/s2, brake {model.brake:g} m/s2, energy "
                  f"{model.energy_max:.3g} Wh, {model.energy_per_delta_v:.3g} Wh per m/s, supplies "
                  f"{model.store_days:g} days."]
    return "\n".join(lines)


def main_report(seeds: list[int], days: int, ship_name: str, load: float) -> str:
    samples: list[Sample] = []
    for seed in seeds:
        samples += sample(seed, days, load * Ship.by_name[ship_name].CARGO_HOLD.CAPACITY)
    player = player_module.current_player
    ship = pilot_ship(player, ship_name)

    def model_for(kind: type) -> ShipModel:
        return ShipModel.of(ship, load, issubclass(kind, WITH_SCOOP))

    groups: dict[tuple[str, str], list[Sample]] = defaultdict(list)
    for item in samples:
        groups[(item.kind.__name__, item.issuer.value)].append(item)
    order = [kind.__name__ for kind in KINDS]
    rows = [row_of(group, model_for) for _, group in sorted(
        groups.items(), key=lambda entry: (order.index(entry[0][0]), entry[0][1]))]
    return render(rows, model_for(DeliverOre), ship_name, load, seeds, days)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--seeds', type=int, nargs='+', default=[1], help="galaxy seeds to sample (default: 1)")
    parser.add_argument('--days', type=int, default=365, help="days of offers sampled per seed (default: 365)")
    parser.add_argument('--ship', default=SHIP_NAME, choices=sorted(Ship.by_name), help="ship configuration")
    parser.add_argument('--load', type=float, default=LOAD_SHARE, help="share of the hold's capacity carried")
    parser.add_argument('--out', help="also write the table to this file")
    arguments = parser.parse_args()
    report = main_report(arguments.seeds, arguments.days, arguments.ship, arguments.load)
    print(report)
    if arguments.out:
        with open(arguments.out, 'w', encoding='utf-8') as handle:
            handle.write(report + "\n")
