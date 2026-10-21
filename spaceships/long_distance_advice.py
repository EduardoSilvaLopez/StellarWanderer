"""Long distance advice: whether to accelerate, stay or decelerate to reach the targeted body, shown under the proximity
meter's "Target" (see graphics/instruments/proximity_meter.py), with a mark in the window where the target will be
(graphics/lead_marker.py). The instruments and the main loop use it (`LongDistanceAdvisor.update` runs once per
frame), and so do the missions, to warn about a trip the ship may not manage (`LongDistanceAdvisor.shortage`).

The algorithm
-------------
The ship feels no gravity, so it moves in straight lines at the speed it has, and only the pilot's thrust changes that.
The trip is one straight line, flown in three phases: accelerate (thrust towards the target), stay (no thrust, coast)
and decelerate (thrust against the motion): the "bang-coast-bang" profile. Each frame the advice is worked out again
from the state of the ship, so it follows the target as it moves and corrects whatever the pilot did.

1. The aim point. The target moves, so the line is drawn to where it will be on arrival, not where it is: the arrival
   time `T` is found by iteration (`INTERCEPT_ITERATIONS`) with the true position of the target at `date + T`, a pure
   function of the date. The motion is worked out in the frame that moves with the target's velocity on arrival, so
   that arriving at rest in it is arriving at rest with respect to the target. In that frame the ship starts with the
   velocity `u` that it has relative to the target: its part along the line to the aim point is `u_r` (positive:
   coming closer) and the part across it is `u_perp` (the drift). The plan covers the distance `d` to the target's
   surface.

2. The constraints, for a peak speed `v` (acceleration `a`, the ship's forward and backward one, and braking `b`,
   its brake's, which is never less):
   - Minimise the travel time: the highest `v` that satisfies the others.
   - At least a third of the time stays (coasts): `COAST_SHARE` of the whole trip, from the departure to the arrival.
     For a trip that starts at rest, with `a` = `b`, this is `v <= sqrt(a * D / 2)`, `D` being the whole distance. As
     the plan is worked out again at every frame, `D` is that of the trip as if it had started at rest here:
     `d + u_r^2 / (2 * a)`.
   - Keep the energy on arrival at `RESERVE_WITHOUT_OUTPOST` (60 %) of its maximum, `RESERVE_WITH_OUTPOST` (20 %) if
     the target has an outpost. A change of speed costs `Navigation.ENERGY_PER_SPEED` per m/s, whatever its
     direction: changing the velocity to `v` along the line (the drift cancelled on the way) and then stopping costs
     `hypot(v - u_r, u_perp) + v`, which cannot be more than the energy above the reserve divided by that cost.
   - Keep the supplies (air, water and food, a day of each per day) on arrival at the same shares of their maxima:
     the time left of the plan, `eta`, cannot exceed the days that the supply with the least above its reserve has.
   - "Too far" if no plan keeps them: the energy above the reserve does not even stop the ship (`hypot(u_r,
     u_perp)`, with `ENERGY_SLACK`: a plan that spends its whole budget leaves just that at its peak), or the
     supplies do not last the time left.

3. The advice, from the peak speed `v_plan` of the plan and the speed `u_r` of the ship:
   - DECELERATE when `d` is no more than the distance to stop, `u_r^2 / (2 * b)`, with `BRAKE_MARGIN` to spare.
   - ACCELERATE when `u_r` is below `v_plan` (by `RESUME_TOLERANCE` after a stay, by `ACCELERATE_TOLERANCE` while
     accelerating): the part of the plan that gets the speed up. `v_plan` shrinks as the distance does, so the ship
     that has reached it stays at it.
   - ACCELERATE too, instead of a stay, while the drift is above `DRIFT_TOLERANCE` of the closing speed (and
     `DRIFT_FLOOR`): thrust that cancels it, in the direction of 4.
   - STAY otherwise. A DECELERATE is kept until the closing speed is nil, or the distance is
     `DECELERATE_RELEASE` times the stopping distance (the ship braked much more than it needed): braking at full
     thrust keeps the distance above the stopping distance by a constant, so a ratio would flicker.
     The pilot brakes with S, which outside the fixed zones brakes against the target's velocity
     (`Navigation.velocity_reference_frame`), so the DECELERATE is done with the ship's brake (`b`).

The advice is given only while the target is farther than `FAR_DISTANCE` (1 Gm, a million km) from the ship's, however
fast the ship moves: nearer, the pilot has the other instruments. It is not given in the fixed zone of the target
either. `ENERGY_MARGIN` of the maximum energy is kept above the reserve: a plan that spent it all would turn into
"Too far" at its last step (a share of what is left each time would compound, so the margin is a fixed amount).

A change from one of the three pieces of advice to another puts the time compression back to x1, with a sound, so that
the pilot does not miss it.

   Once the advice has been DECELERATE the ship brakes to rest with respect to the target as it is now, not on
   arrival: what is left of the trip is short, and the target's velocity changes by kilometres per second in a
   long wait.

4. The direction to thrust in. Drift is common (two planets move at kilometres per second with respect to each other)
   and it is not along the line, so the thrust that cancels it is not either. The direction is that of the change of
   velocity that the advice calls for: ACCELERATE, from the velocity `u` to `v_plan` along the line to the aim point
   (so the drift is cancelled on the way); DECELERATE, against `u`. The instruments show it as how far the nose has to
   turn, and the mark in the window shows where the target will be.

The search for the arrival time starts, each frame, from the arrival of the last frame (the first one, from the target
where it is now): a plan that is found again from zero can settle on another arrival date as the ship moves, and the
target's velocity on arrival, which costs energy to match, changes with the date. A target that accelerates a lot
during the trip is followed by the next frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

from common import audio
from .navigation import Navigation

if TYPE_CHECKING:
    from datetime import datetime

    from galaxies.body import Body
    from galaxies.people.player import Player
    from game_environment import GameEnvironment
    from .ship import Ship

SECONDS_PER_DAY = 86400.0
ENERGY_SLACK = 0.02  # a plan that spends its whole budget leaves just what stopping needs: this much less is still fine


class Advice(Enum):
    ACCELERATE = 'ACCELERATE'
    STAY = 'STAY'
    DECELERATE = 'DECELERATE'


@dataclass(frozen=True)
class Advisory:
    """What the advisor says now: the advice (None for "Too far"), the time left of the plan in seconds (None if
    there is no plan), where the target will be, from the ship (the stellar frame), and the unit vector to thrust in
    (None while staying, or too far)."""
    advice: Advice | None
    eta: float | None
    lead: np.ndarray
    thrust: np.ndarray | None = None
    arrival: datetime | None = None  # when the plan arrives: the next frame starts its search from it


@dataclass(frozen=True)
class Plan:
    peak_speed: float  # m/s: the highest speed of the trip
    eta: float | None  # s: the time left; None if the ship cannot stop in the distance


def coast_limit(distance: float, start_speed: float, acceleration: float, brake: float, coast_share: float) -> float:
    """The highest peak speed of a trip of `distance` from `start_speed`, accelerating at `acceleration` and braking at
    `brake`, that coasts `coast_share` of its time at least. By bisection: the more speed, the less coast."""
    ratio = coast_share / (1.0 - coast_share)  # the coast, in the time of the two thrusts

    def excess(speed: float) -> float:
        thrust_time = (speed - start_speed) / acceleration + speed / brake
        covered = (speed * speed - start_speed * start_speed) / (2.0 * acceleration) + speed * speed / (2.0 * brake)
        return (distance - covered) / speed - ratio * thrust_time

    low = max(start_speed, 1e-3)
    if excess(low) < 0.0:
        return low
    high = math.sqrt(2.0 * acceleration * brake / (acceleration + brake) * distance + start_speed * start_speed) + 1.0
    for _ in range(60):
        middle = (low + high) / 2.0
        low, high = (middle, high) if excess(middle) >= 0.0 else (low, middle)
    return low


def make_plan(distance: float, radial: float, drift: float, acceleration: float, brake: float, budget: float,
              coast_share: float) -> Plan | None:
    """The plan for a trip of `distance` m (to the surface) by a ship that comes closer at `radial` m/s (negative:
    moves away) and drifts across at `drift`, with `budget` m/s of change of speed (the energy above the reserve);
    None if the budget does not even stop the ship."""
    stop_cost = math.hypot(radial, drift)
    if budget < stop_cost * (1.0 - ENERGY_SLACK):
        return None
    budget = max(budget, stop_cost * (1.0 + 1e-6))
    # The highest v with hypot(v - radial, drift) + v <= budget (see 2. in the module docstring).
    energy_limit = (budget * budget - radial * radial - drift * drift) / (2.0 * (budget - radial))
    if radial > 0.0:  # as if the trip had started at rest here: the distance it would have covered so far counts
        coast = coast_limit(distance + radial * radial / (2.0 * acceleration), 0.0, acceleration, brake, coast_share)
    else:
        coast = coast_limit(distance, radial, acceleration, brake, coast_share)
    peak = min(coast, energy_limit)
    speed = max(peak, radial)  # a ship that is faster than the plan stays at its speed
    covered = (speed * speed - radial * radial) / (2.0 * acceleration) + speed * speed / (2.0 * brake)
    if distance < covered:
        return Plan(peak, None)
    return Plan(peak, (speed - radial) / acceleration + speed / brake + (distance - covered) / speed)


class LongDistanceAdvisor:
    """Works out the advice every frame (see the module docstring) and keeps it in `current` for the instruments."""

    FAR_DISTANCE = 1.0e9  # m, a million km: the advice is given beyond it
    COAST_SHARE = 1.0 / 3.0
    RESERVE_WITHOUT_OUTPOST = 0.60
    RESERVE_WITH_OUTPOST = 0.20
    BRAKE_MARGIN = 1.01
    DRIFT_TOLERANCE = 0.05  # of the closing speed: the drift beyond which a stay turns into thrust (about 3 degrees)
    DRIFT_FLOOR = 100.0  # m/s: the drift that is never worth advice
    DRIFT_RELEASE = 0.2  # of the tolerance: the thrust that cancels the drift goes on until it is this low
    ENERGY_MARGIN = 0.02  # of the maximum energy, kept above the reserve: the plan does not spend all of it
    DECELERATE_RELEASE = 100.0
    ACCELERATE_TOLERANCE = 0.01
    RESUME_TOLERANCE = 0.05
    INTERCEPT_ITERATIONS = 6
    MAX_LEAD_SECONDS = 1.0e9
    CHANGE_SOUND = 'notify'

    current: Advisory | None = None
    _advice: Advice | None = None
    _braked: bool = False  # the advice has been DECELERATE on this approach
    _arrival: datetime | None = None
    _target: Body | None = None

    @staticmethod
    def update(player: Player, environment: GameEnvironment) -> None:
        """Once per frame, after the ship has moved: works out the advice, and when it changes from one piece to another
        puts the time compression back to x1 and plays the sound."""
        if player.is_paused:
            return
        advisor = LongDistanceAdvisor
        body = environment.targeted_body
        same_target = body is advisor._target  # a new target starts without a past
        previous = advisor._advice if same_target else None
        braked = advisor._braked and same_target
        advisory = None if player.ship.is_bound else advisor.advise(
            player.ship, body, environment.date_time, previous, braked, advisor._arrival if same_target else None)
        LongDistanceAdvisor.current = advisory
        LongDistanceAdvisor._arrival = None if advisory is None else advisory.arrival
        LongDistanceAdvisor._target = body
        LongDistanceAdvisor._advice = None if advisory is None else advisory.advice
        advice = LongDistanceAdvisor._advice
        LongDistanceAdvisor._braked = advisory is not None and (braked or advice is Advice.DECELERATE)
        if previous is not None and advice is not None and advice is not previous:
            player.time_scale = min(player.time_scale, player.TIME_SCALE_MIN)
            audio.play(LongDistanceAdvisor.CHANGE_SOUND)

    @staticmethod
    def advise(ship: Ship, body: Body, date: datetime, previous: Advice | None, braked: bool = False,
               arrival: datetime | None = None) -> Advisory | None:
        """The advice for the ship to reach the body at the date, or None when none is given (the body is near, or in
        its fixed zone). `previous` is the last piece of advice, for the hysteresis, and `braked` whether it has been
        DECELERATE on this approach. `arrival` is the arrival of the last frame's plan, where the search starts from."""
        navigation = ship.navigation
        advisor = LongDistanceAdvisor
        if navigation.in_fixed_zone(body):
            return None
        if navigation.distance_to_body_centre(body) - body.radius <= advisor.FAR_DISTANCE:  # not to the aim point
            return None

        position = np.array(tuple(navigation.stellar_position(date)))
        velocity = np.array(tuple(ship.velocity.as_vector()))
        accelerations = (ship.FORWARD_BACKWARD_ACC, ship.BRAKE_ACC)
        reserve = advisor.RESERVE_WITH_OUTPOST if getattr(body, 'outposts', None) else advisor.RESERVE_WITHOUT_OUTPOST
        spare_energy = ship.energy - (reserve + advisor.ENERGY_MARGIN) * ship.energy_max
        budget = spare_energy / Navigation.ENERGY_PER_SPEED
        hold = ship.cargo_hold
        spare_days = min(hold.air - reserve * hold.air_max, hold.water - reserve * hold.water_max,
                         hold.food - reserve * hold.food_max)

        trip_time = 0.0 if arrival is None or braked else max(0.0, (arrival - date).total_seconds())
        plan, target, direction, distance, relative, radial, drift = advisor._trip(
            position, velocity, body, date, accelerations, budget, trip_time, 1 if braked else None)
        lead = target - position

        too_far = plan is None or (plan.eta is not None and plan.eta / SECONDS_PER_DAY > spare_days)
        if too_far:
            return Advisory(None, None, lead)
        advice = advisor._choose(plan, radial, drift, distance, accelerations[1], previous)
        change = {Advice.ACCELERATE: plan.peak_speed * direction - relative, Advice.DECELERATE: -relative}.get(advice)
        size = 0.0 if change is None else float(np.linalg.norm(change))
        when = None if plan.eta is None else date + timedelta(seconds=min(plan.eta, advisor.MAX_LEAD_SECONDS))
        return Advisory(advice, plan.eta, lead, change / size if size > 1e-9 else None, when)

    @staticmethod
    def _trip(position: np.ndarray, velocity: np.ndarray, body: Body, date: datetime,
              accelerations: tuple[float, float], budget: float, trip_time: float,
              iterations: int | None = None) -> tuple:
        """The plan of the trip from `position` at `velocity` to the body, and what it was made from: the target's
        position, the unit direction to the aim point, the distance to the surface from there, the velocity relative to
        the target on arrival and its parts along and across the direction. `trip_time` is where the search for the
        arrival starts; a few `iterations` (INTERCEPT_ITERATIONS by default) refine it."""
        advisor = LongDistanceAdvisor
        plan: Plan | None = None
        for _ in range(advisor.INTERCEPT_ITERATIONS if iterations is None else iterations):
            arrival = date + timedelta(seconds=min(trip_time, advisor.MAX_LEAD_SECONDS))
            target = np.array(tuple(body.calculate_stellar_position(arrival)))
            target_velocity = np.array(tuple(body.calculate_stellar_velocity(arrival)))
            # The aim point, in the frame that moves with the target's velocity on arrival.
            aim = target - target_velocity * trip_time
            offset = aim - position
            centre_distance = float(np.linalg.norm(offset))
            direction = offset / max(centre_distance, 1.0)
            distance = max(centre_distance - body.radius, 1.0)
            relative = velocity - target_velocity
            radial = float(relative @ direction)
            drift = float(np.linalg.norm(relative - radial * direction))
            plan = make_plan(distance, radial, drift, *accelerations, budget, advisor.COAST_SHARE)
            if plan is None or plan.eta is None or abs(plan.eta - trip_time) <= 1e-3 * max(trip_time, 1.0):
                break
            trip_time = plan.eta
        return plan, target, direction, distance, relative, radial, drift

    @staticmethod
    def shortage(ship: Ship, body: Body, date: datetime, position: np.ndarray, velocity: np.ndarray) -> str | None:
        """What a ship of this kind, with its tanks and stores full, would lack for a trip to the body from rest at
        `position` and `velocity` (stellar frame): "energy", "air", "water" or "food", whichever the advice would
        turn into "Too far" for. None if it has all it needs, or if the body is near enough (within FAR_DISTANCE of
        its surface) for the advice not to be given. Used by the missions, to warn the player before they take one."""
        advisor = LongDistanceAdvisor
        centre = np.array(tuple(body.calculate_stellar_position(date)))
        if float(np.linalg.norm(centre - position)) - body.radius <= advisor.FAR_DISTANCE:
            return None
        reserve = advisor.RESERVE_WITH_OUTPOST if getattr(body, 'outposts', None) else advisor.RESERVE_WITHOUT_OUTPOST
        budget = (1.0 - reserve - advisor.ENERGY_MARGIN) * ship.energy_max / Navigation.ENERGY_PER_SPEED
        accelerations = (ship.FORWARD_BACKWARD_ACC, ship.BRAKE_ACC)
        plan = advisor._trip(position, velocity, body, date, accelerations, budget, 0.0)[0]
        if plan is None:
            return 'energy'
        hold = ship.cargo_hold
        days = plan.eta / SECONDS_PER_DAY if plan.eta is not None else 0.0
        stores = {'air': hold.air_max, 'water': hold.water_max, 'food': hold.food_max}
        return next((name for name, most in stores.items() if days > (1.0 - reserve) * most), None)

    @staticmethod
    def _choose(plan: Plan, radial: float, drift: float, distance: float, brake: float,
                previous: Advice | None) -> Advice:
        """The piece of advice for a ship that comes closer at `radial` m/s, `distance` m from the surface (see 3. in
        the module docstring)."""
        advisor = LongDistanceAdvisor
        stopping = radial * radial / (2.0 * brake) if radial > 0.0 else 0.0
        if radial > 0.0 and distance <= stopping * advisor.BRAKE_MARGIN:
            return Advice.DECELERATE
        if previous is Advice.DECELERATE and radial > 0.0 and distance <= stopping * advisor.DECELERATE_RELEASE:
            return Advice.DECELERATE
        tolerance = advisor.ACCELERATE_TOLERANCE if previous is Advice.ACCELERATE else advisor.RESUME_TOLERANCE
        if radial < plan.peak_speed * (1.0 - tolerance):
            return Advice.ACCELERATE
        drift_tolerance = advisor.DRIFT_TOLERANCE * max(radial, 0.0) + advisor.DRIFT_FLOOR
        if previous is Advice.ACCELERATE:
            drift_tolerance *= advisor.DRIFT_RELEASE
        return Advice.ACCELERATE if drift > drift_tolerance else Advice.STAY
