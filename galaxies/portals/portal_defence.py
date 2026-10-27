"""What the portal base does about a ship that heads for the Portal, in three stages. Each stage is given by where the
ship's straight line takes it (Portal.arrival_time), counted to the Portal's centre, with the ship's velocity in the
stellar frame (the Portal does not move in it):

  1. it gets within STAGES[0] metres in under its seconds: a warning dialog, and a notification that the base's weapons
     are aimed at the ship;
  2. the same for the second sphere: a last warning;
  3. the same for the third: the base takes the ship by remote control and stops it. The pilot loses
     REPUTATION_PENALTY reputation: below zero it is game over, else they are brought back to the base, which takes
     FORCED_BACK_SECONDS of game time (`update` returns them, for the caller to add to the clock). The stop always
     works (the base's lasers are what stops the ones who try to steal their ships; no failure is played).

A ship already inside a sphere counts as arriving unless it moves away. Each stage is given once, one at a time, and
only when the ship is also nearer than NEXT_STAGE_FRACTION of the distance where the one before was given: a ship that
speeds up from rest widens the distances its time gives, and would get them all at once. The stages are given again
only when the ship has left the area where it was warned: farther from the Portal than REARM_FACTOR times the distance
of the first warning, whatever its course (Portal.warning_stage, Portal.rearm_distance). The check is made each frame,
while the ship is unbound and outside the settlements. A frame that lasts long in game time (time compression) widens
the seconds of the first stage by its length, so that the ship cannot cross the spheres between two checks. The time
scale goes back to its minimum at every stage, and the next ones follow at that pace.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from common.dialogs.messages import Message, show_message

if TYPE_CHECKING:
    from galaxies.portals.portal_base import PortalBase
    from galaxies.people.player import Player
    from game_environment import GameEnvironment

logger = logging.getLogger(__name__)


class PortalDefence:
    """The portal base's defence of its Portal."""

    # (metres from the Portal's centre, seconds) of each stage
    STAGES = ((500.0, 420.0), (300.0, 150.0), (200.0, 90.0))
    REPUTATION_PENALTY = 1000.0
    FORCED_BACK_SECONDS = 24 * 60 * 60.0  # a day
    NEXT_STAGE_FRACTION = 0.6  # a stage needs the ship this near, in parts of the distance of the one before
    REARM_FACTOR = 1.5  # the warnings start again beyond this many times the distance of the first warning

    @staticmethod
    def update(player: Player, environment: GameEnvironment) -> float:
        """Every frame: gives the stage the ship's course calls for, if it is a higher one than the last given. Returns
        the seconds of game time that what it did takes (0 for nearly always)."""
        system = environment.nearest_system
        portal = system.portal
        now = environment.date_time
        step = 0.0 if portal.checked_at is None else max(0.0, (now - portal.checked_at).total_seconds())
        portal.checked_at = now
        ship = player.ship
        if ship.is_bound or player.inside is not None or player.is_dead:
            return 0.0

        position = ship.navigation.stellar_position(now)
        velocity = ship.velocity.as_vector()
        stage = 0
        for number, (radius, seconds) in enumerate(PortalDefence.STAGES, start=1):
            arrival = portal.arrival_time(position, velocity, radius)
            margin = step if number == 1 else 0.0
            if arrival is not None and arrival < seconds + margin:
                stage = number
        distance = (position - portal.centre).length()
        if portal.warning_stage > 0 and distance > portal.rearm_distance:
            portal.warning_stage = 0  # it has left the area where it was warned: the warnings start again
        if portal.warning_stage > 0 and distance > PortalDefence.NEXT_STAGE_FRACTION * portal.stage_distance:
            stage = portal.warning_stage  # not yet close enough for the next one
        elif stage > portal.warning_stage > 0:
            stage = portal.warning_stage + 1  # one at a time
        if stage <= portal.warning_stage:
            return 0.0
        first = portal.warning_stage == 0
        if first:
            portal.rearm_distance = PortalDefence.REARM_FACTOR * distance
        portal.warning_stage = stage
        portal.stage_distance = distance
        logger.info(f"Portal defence of {system.name}: stage {stage}, ship {distance:.0f} m from the Portal, "
                    f"{velocity.length():.2f} m/s.")
        player.time_scale = player.TIME_SCALE_MIN
        base = system.portal_base
        if stage < len(PortalDefence.STAGES):
            PortalDefence._warn(player, base, stage, first)
            return 0.0
        return PortalDefence._block(player, base)

    @staticmethod
    def _warn(player: Player, base: PortalBase, stage: int, first: bool) -> None:
        """The dialog of the stage, and after it, if no stage was given before, the notification of the targeting."""
        if stage == 1:
            text = f"Your ship is not authorised to cross. Please do not approach the Portal, {player.get_title()}."
        else:
            text = f"If you don't turn back immediately {base.name} will have to block your ship."

        def on_result(_: int | None) -> None:
            if first:
                player.ship.notification.set(f"CRITICAL: Laser and missile targeting by {base.name} detected.")

        show_message(Message(title=f"WARNING FROM {base.name.upper()}", text=text), on_result)

    @staticmethod
    def _block(player: Player, base: PortalBase) -> float:
        """The base stops the ship. The pilot is brought back to the base (the seconds that takes are returned), or it
        is game over."""
        player.ship.velocity.set_vector((0.0, 0.0, 0.0))
        player.those_who_share.adjust_reputation(-PortalDefence.REPUTATION_PENALTY)
        if player.those_who_share.reputation < 0.0:
            final_status: str = ''
            if player.get_title() == "Prisoner":
                final_status = "you will spend long years of forced labour in the prisons of the capital"
            elif player.get_title() == "Dependent":
                final_status = (
                    "you will be put in constant oversight and moved to a job of their choosing. Which is"
                    " very lenient, they are taking into account your extraordinary deeds"
                )
            else:
                final_status = (
                    "you will be sent to a polischool for a while before you are allowed to search a different job."
                    " Which is extremely lenient, they are taking in account our extraordinary deeds"
                )
            player.game_over(
                "You are collected from the inert ship by the security staff of the base. They look at you with"
                " commiseration and respect, like nurses handling a demented person. They restrain you and put you"
                " in a cell. Next day, you have a long talk with Ringmaster and Komisar. What you have done is a"
                " severe crime against the whole Community. You are only alive because the autopilot worked,"
                f" but {final_status}. And you will never touch a ship again."
                )
            return 0.0
        base.stellar_system.portal.warning_stage = 0  # the pilot starts again after the return
        base.place_after_leaving(player.ship)
        base.prepare()
        for person in base.staff:
            # Intentionally two calls, prevents hitting 0 too soon.
            person.adjust_sympathy(-0.5 * (person.loyalty100-20))
            person.adjust_sympathy(-0.5 * (person.loyalty100-20))
        player.enter_settlement(base)
        show_message(Message(
            title="Arrested",
            text="You are collected from the inert ship by the security staff of the base. They look at you with"
                " surprise but respect. They beg your pardon for having to restrain you. You are brought into a cell."
                " Not ten minutes later the Ringmaster and the Komisar arrive. They ask you many questions, but"
                " remind you that what you have done is severe Crime Against the Community.\n\n"
                "Were you a common"
                " Pilot, you would now serve many years in prison. As it is, you can still pilot your ship, but"
                " nobody is going to forget this and you should expect a different treatment from now on.\n\n"
                "If the autopilot hadn't worked, you would be now vapour drifting in the void."
            ))
        return PortalDefence.FORCED_BACK_SECONDS
