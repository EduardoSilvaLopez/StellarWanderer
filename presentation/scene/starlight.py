"""Starlight, atmosphere and heat on the cockpit, drawn on the overlay after the cockpit.

Starlight: the opaque cockpit pixels (hull, struts, console) get the star's colour added, by
STARLIGHT_TINT_MAX * min(1, (default_death_radius / distance) ** 2): full at the star's death radius and nearer, about a
hundredth of it at the heat radius (about ten times the death radius), nothing to see far away. Only the colour is
added, so the glass panes (transparent) stay so. Inside the gas of a giant the star's light is dimmed by the gas above.

Atmosphere: inside the gas of a giant the cockpit also gets the colour of the clouds (`AtmosphereLight`), as much as
there is gas above and sunlight left in it.

Heat: a red vignette on the edges of the whole view, its opacity the hot side of the temperature's stress (see
`resource_bars.temperature_stress`): none at the ideal temperature or colder, full at Ship.TEMP_MAX.

The vignette follows `ship.temperature`, so it changes when the temperature does.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Optional, Tuple
import math
import numpy as np
import pygame
from galaxies.jovian_world import JovianWorld
from .constants import (
    STARLIGHT_TINT_MAX, HEAT_VIGNETTE_COLOUR, HEAT_VIGNETTE_MAX_ALPHA, HEAT_VIGNETTE_INNER,
    ATMOSPHERE_TINT_MAX,
    GIANT_LIGHT_PENETRATION,
)
from .instruments.resource_bars import TEMPERATURE_IDEAL, temperature_stress
from .lit_worlds import LitWorlds

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from game_environment import GameEnvironment


def sunlight_in_gas(environment: GameEnvironment, ship: Ship) -> Optional[Tuple[float, float]]:
    """In the atmosphere of a giant: the share of the star's light that reaches the ship (as the shader lights the gas
    around it, the diffuse light feeling only GIANT_LIGHT_PENETRATION of the column above), and how much gas is above
    it (0 to 1, from nothing to opaque). None anywhere else."""
    giant = environment.fixed_body
    if ship.navigation.ambient() is None or not isinstance(giant, JovianWorld):
        return None
    date_time = environment.date_time
    relative_position = ship.position.as_vector() - giant.calculate_stellar_position(date_time)
    distance = relative_position.length()
    if distance <= 0.0:
        return 0.0, 1.0
    to_star = ship.navigation.direction_to_star(giant, date_time)
    cosine = relative_position.dot(to_star) / (distance * to_star.length())
    column = giant.column_depth_at(relative_position)
    horizon = min(1.0, max(0.0, (cosine + 0.02) / 0.17))
    sun = horizon * horizon * (3.0 - 2.0 * horizon) * math.exp(-GIANT_LIGHT_PENETRATION * column / max(cosine, 0.05))
    return sun, 1.0 - math.exp(-column)


class Starlight:
    """The star's colour on the cockpit, stronger as the ship gets near it, and weaker under the gas of a giant."""

    @staticmethod
    def strength(environment: GameEnvironment, ship: Ship) -> float:
        """The share of the star's colour added to the cockpit (0 to STARLIGHT_TINT_MAX)."""
        star = environment.nearest_system.star
        distance = ship.navigation.stellar_position(environment.date_time).length()  # the star is at the origin
        strength = STARLIGHT_TINT_MAX * min(1.0, (star.default_death_radius / max(distance, 1.0)) ** 2)
        gas = sunlight_in_gas(environment, ship)
        return strength if gas is None else strength * gas[0]

    @staticmethod
    def tint_cockpit(overlay: pygame.Surface, environment: GameEnvironment, ship: Ship) -> None:
        strength = Starlight.strength(environment, ship)
        added = tuple(int(c * strength) for c in environment.nearest_system.star.color)
        if any(added):
            overlay.fill(added, special_flags=pygame.BLEND_RGB_ADD)  # the colour only: transparent pixels stay so


class AtmosphereLight:
    """The colour of the clouds on the cockpit, in the atmosphere of a giant: the light the gas around the ship
    scatters, the colour the giant is drawn in. It grows with the gas above and fades as the sunlight is used up, so it
    is strongest in the upper layers and gone in the dark below."""

    @staticmethod
    def tint_cockpit(overlay: pygame.Surface, environment: GameEnvironment, ship: Ship) -> None:
        gas = sunlight_in_gas(environment, ship)
        giant = environment.fixed_body
        if gas is None or not isinstance(giant, JovianWorld):
            return
        colour = LitWorlds.light_tint(environment.nearest_system.star.color, giant.surface_colour)
        share = ATMOSPHERE_TINT_MAX * gas[0] * gas[1]
        added = tuple(int(c * share) for c in colour)
        if any(added):
            overlay.fill(added, special_flags=pygame.BLEND_RGB_ADD)


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


