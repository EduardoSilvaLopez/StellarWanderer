"""The lead marker: a small diamond in the advice colour where the target will be when the ship gets there (the lead
of the long distance advice), or on the canopy's border toward it. Drawn while unbound, only with advice."""

from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import pygame
from common.vector3 import Vector3
from .constants import ADVICE_COLOR
from .target_marker import TargetMarker

if TYPE_CHECKING:
    from spaceships.ship import Ship


class LeadMarker:
    """Draws the diamond at `LongDistanceAdvisor.current.lead`, placed as the target marker is."""

    RADIUS = 5  # pixels, from the centre to each corner

    @staticmethod
    def draw(surface: pygame.Surface, w: int, h: int, ship: Ship) -> None:
        from spaceships.long_distance_advice import LongDistanceAdvisor
        advisory = LongDistanceAdvisor.current
        if ship.is_bound or advisory is None:
            return
        length = float(np.linalg.norm(advisory.lead))
        if length < 1.0:
            return
        point = TargetMarker.place(w, h, ship, Vector3(*(advisory.lead / length)))
        if point is None:
            return
        x, y = int(round(point[0])), int(round(point[1]))
        r = LeadMarker.RADIUS
        pygame.draw.polygon(surface, ADVICE_COLOR, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)], 2)
