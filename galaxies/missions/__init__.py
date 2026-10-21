"""Missions: what the outposts ask of the pilot. The base is in mission.py, each kind in its own module, and the board the
pilot opens in mission_board.py (not imported here: it needs the player, which needs this package).

Importing the package registers every kind, so Mission.deserialize can rebuild any saved mission."""

from .mission import Mission, OPEN, DONE, FAILED
from .deliver_ore import DeliverOre
from .deliver_package import DeliverPackage
from .scan_rock import ScanRock

__all__ = ['Mission', 'OPEN', 'DONE', 'FAILED', 'DeliverOre', 'DeliverPackage', 'ScanRock']
