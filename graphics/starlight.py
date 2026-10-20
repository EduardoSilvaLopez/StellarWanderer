"""Starlight and heat on the cockpit, drawn on the overlay after the cockpit.

Starlight: the opaque cockpit pixels (hull, struts, console) get the star's colour added, by
STARLIGHT_TINT_MAX * min(1, (default_death_radius / distance) ** 2): full at the star's death radius and nearer, about a hundredth
of it at the heat radius (about ten times the death radius), nothing to see far away. Only the colour is added, so the glass panes (transparent) stay so.

Heat: a red vignette on the edges of the whole view, its opacity the hot side of the temperature's stress (see
`resource_bars.temperature_stress`): none at the ideal temperature or colder, full at Ship.TEMP_MAX.

Frost: the cold side, a pale blue vignette, none at the ideal temperature or warmer, full at Ship.TEMP_MIN.

Both follow `ship.temperature`, so they change when the temperature does.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Tuple
import numpy as np
import pygame
from .constants import (
    STARLIGHT_TINT_MAX, HEAT_VIGNETTE_COLOUR, HEAT_VIGNETTE_MAX_ALPHA, HEAT_VIGNETTE_INNER,
    FROST_VIGNETTE_COLOUR, FROST_VIGNETTE_MAX_ALPHA, FROST_VIGNETTE_INNER,
)
from .instruments.resource_bars import TEMPERATURE_IDEAL, temperature_stress

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


class Starlight:
    """The star's colour on the cockpit, stronger as the ship gets near it."""

    @staticmethod
    def strength(environment: GameEnvironment, ship: Ship) -> float:
        """The share of the star's colour added to the cockpit (0 to STARLIGHT_TINT_MAX)."""
        star = environment.nearest_system.star
        distance = ship.navigation.stellar_position(environment.date_time).length()  # the star is at the origin
        return STARLIGHT_TINT_MAX * min(1.0, (star.default_death_radius / max(distance, 1.0)) ** 2)

    @staticmethod
    def tint_cockpit(overlay: pygame.Surface, environment: GameEnvironment, ship: Ship) -> None:
        strength = Starlight.strength(environment, ship)
        added = tuple(int(c * strength) for c in environment.nearest_system.star.color)
        if any(added):
            overlay.fill(added, special_flags=pygame.BLEND_RGB_ADD)  # the colour only: transparent pixels stay so


_masks: Dict[Tuple, pygame.Surface] = {}


def _edge_mask(w: int, h: int, colour: Tuple[int, int, int], max_alpha: int, inner: float) -> pygame.Surface:
    """A vignette at full strength for a window of w x h: transparent in the middle, opaque `colour` at the corners,
    starting at `inner` of the way from the centre to a corner. Built once per window size and colour."""
    key = (w, h, colour, max_alpha, inner)
    mask = _masks.get(key)
    if mask is None:
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        # 0 at the centre, 1 at the corners (an ellipse following the window's shape)
        distance = np.hypot((xs - w / 2) / (w / 2), (ys - h / 2) / (h / 2)) / np.sqrt(2.0)
        strength = np.clip((distance - inner) / (1.0 - inner), 0.0, 1.0) ** 2
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((*colour, 0))
        alphas = pygame.surfarray.pixels_alpha(mask)
        alphas[:] = (strength * max_alpha).astype(np.uint8).T
        del alphas
        _masks[key] = mask
    return mask


def _draw_vignette(overlay: pygame.Surface, w: int, h: int, ship: Ship,
                   colour: Tuple[int, int, int], max_alpha: int, inner: float) -> None:
    """The edge mask over the view, as opaque as the temperature's stress (see temperature_stress)."""
    stress = temperature_stress(ship)
    if stress <= 0.0:
        return
    mask = _edge_mask(w, h, colour, max_alpha, inner)
    mask.set_alpha(int(255 * stress))
    overlay.blit(mask, (0, 0))


class HeatVignette:
    """Red edges on the view as the ship heats up."""

    @staticmethod
    def draw(overlay: pygame.Surface, w: int, h: int, ship: Ship) -> None:
        if ship.temperature > TEMPERATURE_IDEAL:
            _draw_vignette(overlay, w, h, ship, HEAT_VIGNETTE_COLOUR, HEAT_VIGNETTE_MAX_ALPHA, HEAT_VIGNETTE_INNER)


class FrostVignette:
    """Pale blue edges on the view as the ship cools down."""

    @staticmethod
    def draw(overlay: pygame.Surface, w: int, h: int, ship: Ship) -> None:
        if ship.temperature < TEMPERATURE_IDEAL:
            _draw_vignette(overlay, w, h, ship, FROST_VIGNETTE_COLOUR, FROST_VIGNETTE_MAX_ALPHA, FROST_VIGNETTE_INNER)
