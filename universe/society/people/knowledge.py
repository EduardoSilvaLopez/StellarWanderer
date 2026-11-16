"""What the player knows of the galaxy: the stellar bodies that have been generated (module-level `current_knowledge`).

Only keys are held, never objects: the ones the alterations use (`get_alterations_key`), nested as
system cell -> orbit number -> planet index -> moon indices:

    {"26010 10 10": {"3": {"0": ["0"]}}}

A system key present means its star and orbit layout are known (both regenerate from the seed); an orbit without worlds
(a belt, a jovian orbit) has no key. A planet without moons holds an empty list. Knowledge only grows, and adding what
is already there changes nothing, so it does not matter whether the saved knowledge or the generation comes first.

The bodies add themselves as they are generated (StellarSystem and World constructors). The savefile holds it at its
root, next to the environment and the player: it is loaded before the environment, so the systems it generates add to
it. The people are not here: `GameEnvironment.persons` holds those the player has talked to."""

from __future__ import annotations
import copy


class Knowledge:

    def __init__(self, bodies: dict | None = None) -> None:
        self.bodies: dict[str, dict[str, dict[str, list[str]]]] = bodies if bodies else {}

    def learn_system(self, system_key: str) -> dict[str, dict[str, list[str]]]:
        return self.bodies.setdefault(system_key, {})

    def learn_planet(self, system_key: str, orbit_key: str, planet_key: str) -> list[str]:
        return self.learn_system(system_key).setdefault(orbit_key, {}).setdefault(planet_key, [])

    def learn_moon(self, system_key: str, orbit_key: str, planet_key: str, moon_key: str) -> None:
        moons = self.learn_planet(system_key, orbit_key, planet_key)
        if moon_key not in moons:
            moons.append(moon_key)

    def serialize(self) -> dict:
        return {'bodies': copy.deepcopy(self.bodies)}

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Knowledge:
        return Knowledge(copy.deepcopy(loaded_attributes['bodies']))


current_knowledge: Knowledge = None
