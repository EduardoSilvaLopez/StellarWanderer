"""Why an outpost does what it does: the odds of each focus for an outpost on a given world.

A world leans its outposts toward some focuses (its surface, its ore, its temperature, how ordinary its surface is for
its place, where it is in its system), and so does the entity that founded it. The factors multiply and only lean: no
focus is ever impossible, so the pilot cannot read the focus off the world. The draw itself is the outpost's own
(Outpost.__init__)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from universe.artifacts.settlements.settlement import SettlementFocus
from universe.bodies.rock import Rock
from universe.bodies.rocky_world import RockyWorld
from universe.bodies.world_surface import SurfaceType, surface_probability

if TYPE_CHECKING:
    from universe.society.politics.political_entity import PoliticalEntity

Weights = Dict[SettlementFocus, float]

STRONG = 2.0
MILD = 1.4
SLIGHT = 1.2
AGAINST = 0.7
STRONGLY_AGAINST = 0.4

EXTRACTION = SettlementFocus.RESOURCE_EXTRACTION
INDUSTRY = SettlementFocus.INDUSTRY
DEFENCE = SettlementFocus.DEFENCE
RESEARCH = SettlementFocus.RESEARCH
ADMINISTRATION = SettlementFocus.ADMINISTRATION
LIFE_SUPPORT = SettlementFocus.LIFE_SUPPORT

ENTITY_LEAN = 1.6  # what an entity's two favourite focuses are multiplied by
# The weight each focus starts from. Few factors lean toward administration or life support, so without this they
# would be the rarest foci and an entity's lean for them would hardly show. Research gathers many leans, and is meant
# to be as rare as administration; industry takes what it gives up.
BASE_WEIGHT: Weights = {RESEARCH: 0.7, INDUSTRY: 1.25, ADMINISTRATION: 1.25, LIFE_SUPPORT: 1.1}

# What each surface leans toward: dark basalt and sulphur are mined, regolith is easy to dig and build with, old
# highlands are geology, rust-red worlds are the first farms and habitats, and ice is water for air and food.
SURFACE_LEAN: Dict[SurfaceType, Weights] = {
    SurfaceType.BASALT: {EXTRACTION: STRONG, INDUSTRY: MILD, LIFE_SUPPORT: AGAINST},
    SurfaceType.HIGHLAND: {RESEARCH: MILD, ADMINISTRATION: MILD},
    SurfaceType.REGOLITH: {EXTRACTION: MILD, INDUSTRY: STRONG},
    SurfaceType.RUST: {LIFE_SUPPORT: STRONG},
    SurfaceType.OCHRE: {EXTRACTION: STRONG, INDUSTRY: MILD, DEFENCE: AGAINST, RESEARCH: STRONG,
                        ADMINISTRATION: AGAINST, LIFE_SUPPORT: STRONGLY_AGAINST},
    SurfaceType.ICE: {RESEARCH: SLIGHT, LIFE_SUPPORT: STRONG},
}

COLD = 190.0  # K: below it, research
HABITABLE_FROM, HABITABLE_TO = 250.0, 320.0  # K: between them, life support
HOT = 420.0  # K: above it, industry and extraction (light and heat to use)
COLD_RESEARCH = 1.2
HABITABLE_LIFE_SUPPORT = 1.7
HOT_INDUSTRY, HOT_EXTRACTION = 1.5, 1.2
RARE_SURFACE = 0.10  # a surface this unlikely for its temperature draws research strongly, up to UNUSUAL_SURFACE mildly
UNUSUAL_SURFACE = 0.20
RARE_RESEARCH, UNUSUAL_RESEARCH = 1.6, 1.2
MOON_INDUSTRY = 1.3  # a moon's weak gravity makes launching cheap
# Extraction is multiplied by the first of these on a world without ore, and by their sum on the richest.
ORE_FACTOR_MIN, ORE_FACTOR_RANGE = 0.5, 1.5
INNER_DEFENCE_BONUS = 1.0  # the innermost orbit gets 1 + this times the weight of defence
OUTER_RESEARCH_BONUS = 0.5  # the outermost, the same of research
# Moons of a jovian planet: the nearest get this more industry (to scoop the giant) and extraction, the farthest this
# more research.
GIANT_MOON_BONUS = {INDUSTRY: 0.6, EXTRACTION: 0.3, RESEARCH: 0.6}


def _lean(weights: Weights, factors: Weights) -> None:
    for focus, factor in factors.items():
        weights[focus] *= factor


def _entity_favourites(entity: PoliticalEntity) -> tuple[SettlementFocus, ...]:
    # local: the entities import the people, who import the settlements
    from universe.society.politics import political_entity
    if entity is political_entity.THOSE_WHO_SHARE:
        return EXTRACTION, INDUSTRY
    if entity is political_entity.UNITED_DIVERSITY:
        return DEFENCE, RESEARCH
    if entity is political_entity.THE_SHINING_THRONE:
        return LIFE_SUPPORT, ADMINISTRATION
    return ()


def _orbit_position(world: RockyWorld) -> float:
    """0 for the innermost orbit of the world's system to 1 for the outermost; a moon takes its planet's."""
    orbits = world.stellar_system.orbits
    return orbits.index(world.parent_orbit) / (len(orbits) - 1) if len(orbits) > 1 else 0.5


def _giant_moon_position(world: RockyWorld) -> float | None:
    """For a moon of a jovian planet: 0 for its nearest moon to 1 for its farthest; None for any other world."""
    giant = world.parent_planet
    if giant is None or isinstance(giant, RockyWorld):
        return None
    distances = sorted(moon.distance_to_parent for moon in giant.moons)
    return distances.index(world.distance_to_parent) / (len(distances) - 1) if len(distances) > 1 else 0.5


def focus_weights(world: RockyWorld, entity: PoliticalEntity) -> Weights:
    """The odds of each focus (relative) for an outpost of `entity` on `world`."""
    weights: Weights = {focus: BASE_WEIGHT.get(focus, 1.0) for focus in SettlementFocus}
    for focus in _entity_favourites(entity):
        weights[focus] *= ENTITY_LEAN
    _lean(weights, SURFACE_LEAN[world.surface_type])

    temperature = world.equilibrium_temperature
    if temperature < COLD:
        weights[RESEARCH] *= COLD_RESEARCH
    elif HABITABLE_FROM <= temperature <= HABITABLE_TO:
        weights[LIFE_SUPPORT] *= HABITABLE_LIFE_SUPPORT
    elif temperature > HOT:
        weights[INDUSTRY] *= HOT_INDUSTRY
        weights[EXTRACTION] *= HOT_EXTRACTION

    ordinariness = surface_probability(world.surface_type, temperature)
    if ordinariness < RARE_SURFACE:
        weights[RESEARCH] *= RARE_RESEARCH
    elif ordinariness < UNUSUAL_SURFACE:
        weights[RESEARCH] *= UNUSUAL_RESEARCH

    if world.parent_planet is not None:
        weights[INDUSTRY] *= MOON_INDUSTRY

    ore_richness = world.ore_prevalence / (1.0 - Rock.ORE_RICH_THRESHOLD)  # 0 to 1
    weights[EXTRACTION] *= ORE_FACTOR_MIN + ORE_FACTOR_RANGE * ore_richness

    position = _orbit_position(world)
    weights[DEFENCE] *= 1.0 + INNER_DEFENCE_BONUS * (1.0 - position)
    weights[RESEARCH] *= 1.0 + OUTER_RESEARCH_BONUS * position

    giant_position = _giant_moon_position(world)
    if giant_position is not None:
        weights[INDUSTRY] *= 1.0 + GIANT_MOON_BONUS[INDUSTRY] * (1.0 - giant_position)
        weights[EXTRACTION] *= 1.0 + GIANT_MOON_BONUS[EXTRACTION] * (1.0 - giant_position)
        weights[RESEARCH] *= 1.0 + GIANT_MOON_BONUS[RESEARCH] * giant_position
    return weights
