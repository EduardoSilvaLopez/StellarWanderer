"""The terms of a kind of mission at a kind of settlement: the numbers that depend on where the offer is made.

Each kind of mission keeps a map, `TERMS`, from each `SettlementKind` to its `Terms`, next to its other constants.
A kind
with a frequency of 0 at a kind of settlement is not offered there. A settlement kind with no entry is a bug, and
`check_terms` stops the game at start-up when one is missing.

The meaning of `reward` depends on the kind of mission (see its class); `failure_penalty` is what the mission
costs when it fails, and it is the issuer's terms that count.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Type

from galaxies.settlement_kind import SettlementKind


@dataclass(frozen=True)
class Terms:
    frequency: float  # the chance a kind makes an offer on a given day; 0: not offered at this kind of settlement
    taken_by_others: float  # the chance a day that somebody else takes an offer, which then leaves the board
    deadline_days_min: int  # the shortest and the longest deadline of an offer, in days
    deadline_days_max: int
    reward: float  # what a completed mission gives; its meaning is the kind's
    failure_penalty: float  # what a failed mission costs


def check_terms(kinds: Iterable[Type]) -> None:
    """Stops with an error if a mission kind has no terms for a kind of settlement: that is a bug, not an absence."""
    for kind in kinds:
        for settlement_kind in SettlementKind:
            if settlement_kind not in kind.TERMS:
                raise RuntimeError(f"Mission kind {kind.KIND} has no terms for {settlement_kind.value}")

