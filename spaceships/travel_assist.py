"""The TRAVEL autopilot: flies the long distance advice (see long_distance_advice.py) to the targeted body, so that the
pilot does not have to chase a moving target by hand. The advisor works out each frame what to do (accelerate towards
the aim point, stay, decelerate) and the autopilot does it with the right, up and forward engines together, whatever
the attitude: the nose stays the pilot's, who may turn and look around, and compress time as far as it is safe (the
time scale that the caps lower returns by itself, see `Player.limit_time_scale`). Braking is the ship's brake, against
the target's velocity as S is, but straight against the motion (see `Navigation._brake`), as the advice assumes.

It ends where the advice does, near the target (inside its fixed zone, for a world: the ship is then fixed to it and
follows its orbit): it brakes to rest with respect to the target and hands the ship over. The last leg is the pilot's,
or the ORBIT assist's. It also ends when the pilot takes the controls (a translation key, or TRAVEL again; S only
stops the turns), when the target changes, when the straight line leads into the world the ship is fixed to, or when
the trip is too far for the energy or the supplies. It does not fly to a star. The time scale goes back to x1 when it
ends, so that the pilot is in control at once.
"""

from __future__ import annotations
import math
from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Tuple

from common.vector3 import Vector3
from galaxies.star import Star
import game_environment as gem
from spaceships.long_distance_advice import Advice, LongDistanceAdvisor

if TYPE_CHECKING:
    from galaxies.body import Body
    from .ship import Ship

Thrust = Tuple[float, float, float]  # shares of the right, up and forward engines, -1 to 1
NO_THRUST: Thrust = (0.0, 0.0, 0.0)


class TravelAssist:
    """One trip, from the press of TRAVEL until it ends. It lives on the ship's navigation (`Navigation.travel`)
    meanwhile."""

    REST_SPEED = 1.0  # m/s: the ship is at rest with respect to the target within this, and the autopilot hands it over

    def __init__(self, ship: Ship, target: Body) -> None:
        self.ship: Ship = ship
        self.target: Body = target

    @staticmethod
    def enabled(ship: Ship) -> bool:
        """TRAVEL can be pressed while the ship is unbound and the target's fixed zone does not hold it. It does not
        fly to a star: the plan ends too near it for the heat."""
        body = gem.current_environment.targeted_body
        return not ship.is_bound and not isinstance(body, Star) and not ship.navigation.in_fixed_zone(body)

    @staticmethod
    def begin(ship: Ship) -> Optional[str]:
        """Starts the autopilot if it can: None when it did, else the reason it cannot (for the notification). An
        orbit is left first: the advice is a straight line, which the ship follows only while the engines compensate
        the pull. The orbit comes back if the trip cannot be made."""
        environment = gem.current_environment
        navigation = ship.navigation
        body = environment.targeted_body
        if ship.is_bound or ship.is_docked or ship.owner.inside is not None:
            return "the ship is not in flight"
        if isinstance(body, Star):
            return "the autopilot does not fly to a star: its heat would burn the ship"
        if navigation.in_fixed_zone(body):
            return f"the ship is in the fixed zone of {body.name}"
        orbit = navigation.orbit
        navigation.orbit = None
        LongDistanceAdvisor.update(ship.owner, environment)
        advisory = LongDistanceAdvisor.current
        reason = None
        if advisory is None:
            reason = f"the ship is already at the end of the trip to {body.name}"
        elif advisory.advice is None:
            reason = "it is too far for the energy or the supplies"
        if reason is not None:
            navigation.orbit = orbit
            return reason
        navigation.travel = TravelAssist(ship, body)
        ship.notification.set(f"Travelling to {body.name}.")
        return None

    @staticmethod
    def press(ship: Ship) -> None:
        """The TRAVEL button and key: gives the controls back, or starts the trip, with a notification saying why it
        cannot."""
        if ship.navigation.travel is not None:
            ship.navigation.travel.leave()
            return
        reason = TravelAssist.begin(ship)
        if reason is not None:
            ship.notification.set(f"Travel not started: {reason}.", bad=True)

    def step(self, delta_time: float) -> Tuple[Thrust, bool]:
        """One frame of `delta_time` game seconds: the thrust to apply, as shares of the three engines, and whether to
        brake. It may end the trip instead, with a notification (then there is no thrust and no brake)."""
        ship = self.ship
        environment = gem.current_environment
        if ship.is_bound or ship.is_docked or ship.owner.inside is not None:
            self.end(None)
            return NO_THRUST, False
        if environment.targeted_body is not self.target:
            self.end("Travel cancelled: the target changed.")
            return NO_THRUST, False
        fixed = environment.fixed_body
        if fixed is not None and fixed is not self.target and ship.navigation.collision_warning(fixed):
            self.end(f"Travel cancelled: the path leads into {fixed.name}.")
            return NO_THRUST, False
        advisory = LongDistanceAdvisor.current
        if advisory is None:  # the plan is done, or the ship is in the target's fixed zone: it brakes to rest
            start = environment.date_time - timedelta(seconds=delta_time)  # the frame the brake works against
            velocity = ship.velocity.as_vector() - ship.navigation.velocity_reference_frame(start)
            if velocity.length() <= TravelAssist.REST_SPEED:
                self.end(f"Arrived at {self.target.name}, at rest with respect to it.")
                return NO_THRUST, False
            return NO_THRUST, True
        if advisory.advice is None:
            self.end("Travel cancelled: it is too far for the energy or the supplies.")
            return NO_THRUST, False
        if advisory.advice is Advice.DECELERATE:
            return NO_THRUST, True
        if advisory.advice is Advice.ACCELERATE and advisory.thrust is not None:
            direction = Vector3(*(float(component) for component in advisory.thrust))
            return self._thrust_along(direction, advisory.phase_time, delta_time), False
        return NO_THRUST, False

    def leave(self) -> None:
        """The pilot takes the controls back: TRAVEL pressed again, or a translation key."""
        self.end("Travel cancelled by the pilot.")

    def end(self, message: Optional[str]) -> None:
        """Hands the ship over, at x1. `message` is the notification, or None for none."""
        ship = self.ship
        ship.navigation.travel = None
        ship.owner.reset_time_scale()
        if message is not None:
            ship.notification.set(message)

    def _thrust_along(self, direction: Vector3, phase_time: Optional[float], delta_time: float) -> Thrust:
        """The shares of the three engines that push along `direction` (a unit vector), at the acceleration of the
        forward engine, which the plan assumes: no more than the engines give, whatever the attitude (the side engine is
        the weakest, so the push is weaker when the side of the ship faces the direction: the advice, worked out every
        frame, follows what the ship does). A frame longer than the push that is still needed (`phase_time` of the
        advice, at the forward acceleration) gets only that push, so that time compression does not carry the speed
        past the plan's."""
        ship = self.ship
        attitude = ship.attitude
        engines = ((attitude.right, ship.RIGHT_LEFT_ACC), (attitude.up, ship.UP_DOWN_ACC),
                   (attitude.forward, ship.FORWARD_BACKWARD_ACC))
        shares = [direction.dot(axis) * ship.FORWARD_BACKWARD_ACC / acceleration for axis, acceleration in engines]
        peak = max(abs(share) for share in shares)
        if peak > 1.0:
            shares = [share / peak for share in shares]
        if phase_time is not None:
            push = math.sqrt(sum((share * acceleration) ** 2 for share, (_, acceleration) in zip(shares, engines)))
            needed = phase_time * ship.FORWARD_BACKWARD_ACC
            if push * delta_time > needed > 0.0:
                shares = [share * needed / (push * delta_time) for share in shares]
        return shares[0], shares[1], shares[2]
