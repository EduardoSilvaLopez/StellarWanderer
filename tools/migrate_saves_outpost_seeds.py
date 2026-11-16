"""Re-keys the outposts of the saves to their seeds of the current code. An outpost's seed used to count the outposts of
its planet (`len(planet.outposts)`), so two settlements could share one; now it is derived from the settlement's number
in its system's history. That changes the seed, and so the place (longitude and latitude are drawn from it), the staff
seeds and the mission keys of every outpost.

The old outposts are replayed here with the old rule, so the old seed and place of each one are known; the saved place
keys must match the replay, which the script checks. Each saved reference is then rewritten: the outposts' place keys,
the full keys in the missions, the staff people (their records, their seeds in `staff_on_duty`) and the interaction keys
that hold an outpost's seed.

Run it from the project folder, on the new code: python tools/migrate_saves_outpost_seeds.py <savefiles folder> <output folder>
The output folder receives the migrated saves with the same paths; the originals are not touched."""

import copy
import json
import math
import os
import random
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import game_environment  # noqa: E402, F401  (first, as in main: the modules import each other in this order)
from universe.structure import seeds  # noqa: E402
from universe.structure.galaxy import Galaxy  # noqa: E402
from universe.artifacts.settlements.outpost import Outpost  # noqa: E402
from universe.society.people import knowledge  # noqa: E402

MAX_HIRES = 1000  # the staff seeds per outpost are tried up to this index
SYSTEM_KEY_PATTERN = re.compile(r'^-?\d+ -?\d+ -?\d+$')
DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

created: list[Outpost] = []  # every outpost made by the new code, in creation order, the ones overwritten too
_original_init = Outpost.__init__


def _recording_init(self: Outpost, *args, **kwargs) -> None:
    _original_init(self, *args, **kwargs)
    created.append(self)


Outpost.__init__ = _recording_init  # type: ignore[method-assign]


def old_place(planet, old_seed: int, old_index: int) -> str:
    """The place key the old code gave an outpost with that seed and index (name, then longitude, then latitude)."""
    my_random = random.Random(old_seed)
    entity = planet.parent_orbit.parent_stellar_system.political_entity
    entity.generate_outpost_name(my_random)
    longitude = 0 if old_index == 0 else \
        my_random.randint(int(-planet.radius * math.pi), int(planet.radius * math.pi))
    latitude = my_random.randint(int(-planet.radius * math.pi / 2), int(planet.radius * math.pi / 2))
    return f"{longitude} {latitude}"


def replay_old(outposts_of_system: list[Outpost]) -> list[tuple[Outpost, int, str]]:
    """The outposts the old code left in the game: (new outpost, old seed, old place). The old index was the count of
    the planet's outposts at the time, and a later outpost with the same place replaced the earlier one."""
    by_planet: dict[int, list[Outpost]] = {}
    for outpost in sorted(outposts_of_system, key=lambda o: o.number):
        by_planet.setdefault(outpost.planet.seed, []).append(outpost)
    survivors: list[tuple[Outpost, int, str]] = []
    for planet_seed, outposts in by_planet.items():
        table: dict[str, tuple[Outpost, int, str]] = {}
        for outpost in outposts:
            old_index = len(table)
            old_seed = seeds.derive(planet_seed, 'outpost', old_index)
            place = old_place(outpost.planet, old_seed, old_index)
            table[place] = (outpost, old_seed, place)
        survivors.extend(table.values())
    return survivors


def planet_path_of(path: list) -> str:
    """The planet's full keys (system|orbit|planet, and the moon) from the path of its outposts' dict."""
    after = path[path.index('galaxy_alterations') + 1:]
    return '|'.join(token for token in after if token != 'moons')


def migrate_save(data: dict) -> tuple[dict, dict]:
    """The migrated save, and the counts of what was rewritten and what could not be matched."""
    # The generation works on a copy: it may add to what it reads, and the saves are rewritten from the original.
    generated = copy.deepcopy(data)
    knowledge.current_knowledge = knowledge.Knowledge.deserialize(generated['knowledge'])  # the systems learn it
    environment = generated['environment']
    date_time = datetime.strptime(environment['date_time'], DATE_FORMAT)
    alterations: dict = environment['galaxy_alterations']
    alterations['date_time'] = date_time  # as GameEnvironment gives it
    galaxy = Galaxy(environment['galactic_seed'], alterations, date_time)
    created.clear()
    for key in alterations:
        if SYSTEM_KEY_PATTERN.match(key):
            galaxy.system_of_key(key)

    full_map: dict[str, str] = {}
    seed_map: dict[str, str] = {}
    person_map: dict[int, int] = {}
    systems_outposts: dict[int, list[Outpost]] = {}
    for outpost in created:
        systems_outposts.setdefault(id(outpost.planet.parent_orbit.parent_stellar_system), []).append(outpost)
    survivors: list[tuple[Outpost, int, str]] = []
    for group in systems_outposts.values():
        survivors.extend(replay_old(group))
    for outpost, old_seed, old_place in survivors:
        new_full = outpost.full_keys()
        planet_path = new_full.rsplit('|', 1)[0]
        full_map[planet_path + '|' + old_place] = new_full
        seed_map[str(old_seed)] = str(outpost.seed)
        for index in range(MAX_HIRES):
            person_map[seeds.derive(old_seed, 'person', index)] = seeds.derive(outpost.seed, 'person', index)

    counts = {'place keys': 0, 'unmatched place keys': 0, 'people': 0, 'strings': 0, 'full keys': 0}

    def mapped_string(text: str) -> str:
        if text in full_map:
            counts['full keys'] += 1
            return full_map[text]
        for old, new in seed_map.items():
            if old in text:
                new_text = re.sub(rf'(?<!\d){old}(?!\d)', new, text)
                if new_text != text:
                    counts['strings'] += 1
                    text = new_text
        return text

    def transform(node, path: list):
        if isinstance(node, dict):
            result = {}
            for key, value in node.items():
                new_key = key
                if path and path[-1] == 'outposts':
                    counts['place keys'] += 1
                    new_key = full_map.get(planet_path_of(path[:-1]) + '|' + key)
                    if new_key is None:
                        counts['unmatched place keys'] += 1
                        new_key = key
                    else:
                        new_key = new_key.rsplit('|', 1)[1]
                elif path and path[-1] == 'persons' and key.isdigit() and int(key) in person_map:
                    counts['people'] += 1
                    new_key = str(person_map[int(key)])
                elif isinstance(key, str):
                    new_key = mapped_string(key)
                result[new_key] = transform(value, path + [key])
            return result
        if isinstance(node, list):
            return [transform(item, path) for item in node]
        if isinstance(node, bool):
            return node
        if isinstance(node, int) and node in person_map:
            counts['people'] += 1
            return person_map[node]
        if isinstance(node, str):
            return mapped_string(node)
        return node

    return transform(data, []), counts


def migrate(source: str, target: str) -> None:
    for folder in sorted(os.listdir(source)):  # one folder per galactic seed; the other folders are the player's
        if not folder.isdigit():
            continue
        for name in sorted(os.listdir(os.path.join(source, folder))):
            if not name.endswith('.json'):
                continue
            path = os.path.join(source, folder, name)
            with open(path, encoding='utf-8') as file:
                data = json.load(file)
            migrated, counts = migrate_save(data)
            out_path = os.path.join(target, folder, name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as file:
                json.dump(migrated, file, ensure_ascii=False, indent=4)
            print(f"{folder}/{name}: {counts}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python tools/migrate_saves_outpost_seeds.py <savefiles folder> <output folder>")
    migrate(sys.argv[1], sys.argv[2])
