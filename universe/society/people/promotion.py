"""The promotions of the pilot: what the Community gives a pilot who has earned it."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from universe.artifacts.spaceships.configurations.tws_hauler import TwsHauler
from universe.artifacts.spaceships.configurations.tws_shabby_miner import ShabbyTwsMiner
from universe.artifacts.spaceships.configurations.tws_versatile import TwsVersatile
from universe.society.missions.deliver_ore import DeliverOre
from universe.society.missions.mission import DONE

if TYPE_CHECKING:
    from universe.society.people.player import Player

STANDARD_HOLD = 'standard hold'  # the Shabby miner's hold is repaired
MISSIONS = 'missions'  # the mission boards open
EXTENDED_HOLD = 'extended hold'
MINER = 'miner'  # the Shabby miner is replaced by a modern one
VERSATILE = 'versatile'  # offered to a pilot who does more than mine
HAULER = 'hauler'  # offered
INTERSTELLAR_CLEARANCE = 'vacation'  # the pilot may take the ship and go

MISSIONS_FLAG = 'Missions Added'
VERSATILE_FLAG = 'Versatile Asked'
HAULER_FLAG = 'Hauler Asked'
INTERSTELLAR_CLEARANCE_FLAG = 'Interstellar Clearance'
VERSATILE_MAX_ORE_SHARE = 0.65  # the Versatile is for a pilot whose done missions are at most this share of ore


def ore_share(player: Player) -> float:
    """The share of the pilot's done missions that deliver ore (1 while none is done)."""
    done = [mission for mission in player.missions if mission.status == DONE]
    return sum(isinstance(mission, DeliverOre) for mission in done) / len(done) if done else 1.0

def next_step(player: Player) -> Optional[str]:
    """The first step due to `player` now, or None. The order is the order they are given in."""
    rep: float = player.reputation
    ship = player.ship
    if rep >= 10 and isinstance(ship, ShabbyTwsMiner) and isinstance(ship.cargo_hold, ShabbyTwsMiner.ShabbyHold):
        return STANDARD_HOLD
    if rep >= 20 and MISSIONS_FLAG not in player.flags:
        return MISSIONS
    if rep >= 50 and isinstance(ship, ShabbyTwsMiner) and not isinstance(ship.cargo_hold, ShabbyTwsMiner.ExtendedHold):
        return EXTENDED_HOLD
    if rep >= 100 and isinstance(ship, ShabbyTwsMiner):
        return MINER
    if (rep >= 200 and VERSATILE_FLAG not in player.flags and not isinstance(ship, TwsVersatile)
            and ore_share(player) <= VERSATILE_MAX_ORE_SHARE):
        return VERSATILE
    if rep >= 500 and HAULER_FLAG not in player.flags and not isinstance(ship, (TwsVersatile, TwsHauler)):
        return HAULER
    if rep >= 1000 and INTERSTELLAR_CLEARANCE_FLAG not in player.flags:
        return INTERSTELLAR_CLEARANCE
    return None
