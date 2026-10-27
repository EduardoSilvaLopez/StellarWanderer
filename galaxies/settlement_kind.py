"""The kinds of settlement. A settlement says which kind it is (`Settlement.kind`), and what a mission or a rule depends on
is looked up by it (the terms of each mission kind, see galaxies/missions/terms.py). A city will be one more kind."""

from __future__ import annotations
from enum import Enum


class SettlementKind(Enum):
    OUTPOST = 'outpost'
    PORTAL_BASE = 'portal_base'
