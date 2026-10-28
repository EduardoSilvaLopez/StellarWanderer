"""One-off conversion of the savefiles made before the rocky worlds got a density (see RockyWorld): their mass, density
and radius are drawn first now, so every planet's radius changed, and with it the keys of its outposts ("lon lat"), the
number of its outposts and moons, and the rocks of its Km2s. The game reads only the current format, so the saves are
converted here, to new files; the originals are never touched.

    python tools/migrate_saves_density.py SOURCE_DIR TARGET_DIR

What is kept and what is not, per planet and moon:
- Ore fields and mines always: a Km2 outside the new, smaller surface is moved to its edge (reported).
- Outposts: the old key is found by replaying the old draws (the planet's old radius, then the outpost's own draws), which
  gives the outpost's index, and the same index is the same outpost (seed, name and staff) at its new key. An outpost
  that no longer exists loses its alterations and, with it, the missions that mention it. The people (saved by seed)
  stay.
- Rocks and molten rocks of a Km2: kept only where the same rock is generated again.
- Missions: their outposts get the new keys; a mission of a vanished outpost, or an open scan of a rock that is no
  longer there, is dropped. So is `inside_settlement` of a vanished outpost.
- The knowledge loses the moons that no longer exist, and the target of an unbound ship is forgotten (the order of the
  bodies by distance changed).
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import game_environment as gem  # noqa: E402  (first: it loads the galaxy package in the order the game does)
from galaxies import seeds  # noqa: E402
from galaxies.km2 import Km2  # noqa: E402
from galaxies.people import knowledge  # noqa: E402
from galaxies.rocky_world import RockyWorld  # noqa: E402
from galaxies.stellar_system import StellarSystem  # noqa: E402

OLD_MAX_OUTPOSTS = 6  # the old draw, int(abs(gauss(1.5, 0.5))), never gave more than a few
DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


class Migration:
    """The conversion of one savefile's data. `messages` tell what was dropped or moved."""

    def __init__(self, data: dict) -> None:
        self.data: dict = data
        self.messages: List[str] = []
        environment: dict = data['environment']
        knowledge.current_knowledge = knowledge.Knowledge()
        gem.current_environment = gem.GameEnvironment(
            environment['galactic_seed'], datetime.strptime(environment['date_time'], DATE_FORMAT), None, None)
        self._old_outposts: Dict[int, Dict[str, int]] = {}  # by the planet's seed: old key -> index

    # region The new galaxy
    def _system(self, key: str) -> Optional[StellarSystem]:
        return gem.current_environment.galaxy.system_of_key(key)

    def _planet(self, system_key: str, orbit_key: str, planet_key: str) -> Optional[RockyWorld]:
        """The rocky planet of the keys in the new galaxy, None if there is none."""
        system = self._system(system_key)
        if system is None:
            return None
        try:
            planets = system.get_orbit(float(orbit_key)).planets
        except (KeyError, ValueError, AttributeError, StopIteration):
            return None
        index = int(planet_key)
        return planets[index] if index < len(planets) and isinstance(planets[index], RockyWorld) else None

    def _old_outpost_indices(self, planet: RockyWorld) -> Dict[str, int]:
        """The keys the planet's outposts had before the change, with their index: the old radius is the first draw that
        follows the name in the planet's own generator, and each outpost draws its name, its longitude (0 for the first)
        and its latitude from its own seed."""
        if planet.seed not in self._old_outposts:
            my_random = random.Random(planet.seed)
            planet._generate_planet_name(my_random)
            radius = 0.0
            while radius < RockyWorld.WORLD_MIN_RADIUS:
                radius = my_random.gauss(5000000, 1000000)
            radius = int(radius)
            keys: Dict[str, int] = {}
            for index in range(OLD_MAX_OUTPOSTS):
                outpost_random = random.Random(seeds.derive(planet.seed, 'outpost', index))
                planet.stellar_system.political_entity.generate_outpost_name(outpost_random)
                longitude = 0 if index == 0 else outpost_random.randint(int(-radius * math.pi), int(radius * math.pi))
                latitude = outpost_random.randint(int(-radius * math.pi / 2), int(radius * math.pi / 2))
                keys[f"{longitude} {latitude}"] = index
            self._old_outposts[planet.seed] = keys
        return self._old_outposts[planet.seed]

    def _new_outpost_key(self, planet: RockyWorld, old_key: str) -> Optional[str]:
        index = self._old_outpost_indices(planet).get(old_key)
        return next((key for key, outpost in planet.outposts.items() if outpost.index == index), None)

    def new_settlement_keys(self, old_full_keys: str) -> Optional[str]:
        """The full keys (see Outpost.full_keys) that an old outpost has now, None if it is gone; a portal base keeps
        its own (the pilot inside it is saved as plain 'portal_base')."""
        if old_full_keys == 'portal_base' or old_full_keys.endswith('|portal_base'):
            return old_full_keys
        system_key, orbit_key, planet_key, outpost_key = old_full_keys.split('|')
        planet = self._planet(system_key, orbit_key, planet_key)
        new_key = None if planet is None else self._new_outpost_key(planet, outpost_key)
        return None if new_key is None else '|'.join((system_key, orbit_key, planet_key, new_key))
    # endregion

    # region The alterations of the galaxy
    def migrate_galaxy(self) -> None:
        alterations: dict = self.data['environment']['galaxy_alterations']
        for system_key in list(alterations):
            if self._system(system_key) is None:
                self.messages.append(f"system {system_key} does not exist: dropped")
                del alterations[system_key]
                continue
            for orbit_key, orbit_alterations in list(alterations[system_key].items()):
                if orbit_key == 'portal_base' or 'asteroids' in orbit_alterations:
                    continue  # the portal base and the belts did not change
                for planet_key in list(orbit_alterations):
                    planet = self._planet(system_key, orbit_key, planet_key)
                    if planet is None:
                        self.messages.append(f"planet {system_key}|{orbit_key}|{planet_key} does not exist: dropped")
                        del orbit_alterations[planet_key]
                    else:
                        orbit_alterations[planet_key] = self._migrate_planet(
                            f"{system_key}|{orbit_key}|{planet_key}", planet, orbit_alterations[planet_key])
                if not orbit_alterations:
                    del alterations[system_key][orbit_key]

    def _migrate_planet(self, label: str, planet: RockyWorld, saved: dict) -> dict:
        result: dict = {}
        km2s: dict = {}
        self._add_km2s(km2s, self.migrate_km2s(label, planet, saved.get('Km2s', {})))
        moons: dict = {}
        for moon_key, moon_saved in saved.get('moons', {}).items():
            moon_index = int(moon_key)
            moon_km2s = moon_saved.get('Km2s', {})
            if moon_index < len(planet.moons):
                moons.setdefault(moon_key, {}).setdefault('Km2s', {})
                self._add_km2s(moons[moon_key]['Km2s'],
                               self.migrate_km2s(f"{label} moon {moon_key}", planet.moons[moon_index], moon_km2s))
            elif planet.moons:
                self.messages.append(f"{label} moon {moon_key} is gone: its ground is now that of moon 0")
                moons.setdefault('0', {}).setdefault('Km2s', {})
                self._add_km2s(moons['0']['Km2s'], self.migrate_km2s(f"{label} moon 0", planet.moons[0], moon_km2s))
            else:
                self.messages.append(f"{label} moon {moon_key} is gone: its ground is now the planet's")
                self._add_km2s(km2s, self.migrate_km2s(label, planet, moon_km2s))
        outposts: dict = {}
        for old_key, outpost_saved in saved.get('outposts', {}).items():
            new_key = self._new_outpost_key(planet, old_key)
            if new_key is None:
                self.messages.append(f"outpost {label}|{old_key} is gone: its alterations are dropped")
            else:
                outposts[new_key] = outpost_saved
        if km2s:
            result['Km2s'] = km2s
        moons = {key: value for key, value in moons.items() if value['Km2s']}
        if moons:
            result['moons'] = moons
        if outposts:
            result['outposts'] = outposts
        return result

    @staticmethod
    def _add_km2s(target: dict, km2s: dict) -> None:
        """Puts `km2s` into `target`, joining the Km2s that land on the same key."""
        for key, content in km2s.items():
            if key not in target:
                target[key] = content
                continue
            joined = target[key]
            joined['rocks'].update(content['rocks'])
            joined['molten_rocks'].extend(rock for rock in content['molten_rocks'] if rock not in joined['molten_rocks'])
            joined['ore_fields'].extend(content['ore_fields'])

    def migrate_km2s(self, label: str, world: RockyWorld, km2s: dict) -> dict:
        """The Km2s of a world as they stand in the new one. A Km2 that is not wholly inside the new surface moves to
        the edge, its ore fields and mines with it, and loses its rocks."""
        half_turn = int(math.pi * world.radius) // Km2.SIZE * Km2.SIZE
        half_height = int(math.pi * world.radius / 2.0) // Km2.SIZE * Km2.SIZE
        result: dict = {}
        for key, content in km2s.items():
            longitude, latitude = (int(value) for value in key.split())
            new_longitude = max(-half_turn, min(half_turn - Km2.SIZE, longitude))
            new_latitude = max(-half_height, min(half_height - Km2.SIZE, latitude))
            moved = (new_longitude, new_latitude) != (longitude, latitude)
            if moved:
                self.messages.append(f"{label} Km2 {key} is outside the new surface: moved to "
                                     f"{new_longitude} {new_latitude}, with {len(content['ore_fields'])} ore fields")
                content = self._shifted(content, new_longitude - longitude, new_latitude - latitude)
            else:
                content = self._with_rocks_of_the_new_world(world, longitude, latitude, content)
            self._add_km2s(result, {f"{new_longitude} {new_latitude}": content})
        return result

    @staticmethod
    def _shifted(content: dict, delta_longitude: int, delta_latitude: int) -> dict:
        """The Km2's ore fields and mines moved by the distance, without rocks."""
        fields: List[dict] = []
        for field in content['ore_fields']:
            moved = dict(field, longitude=field['longitude'] + delta_longitude,
                         latitude=field['latitude'] + delta_latitude)
            moved['mines'] = [dict(mine, longitude=mine['longitude'] + delta_longitude,
                                   latitude=mine['latitude'] + delta_latitude) for mine in field['mines']]
            fields.append(moved)
        return {'rocks': {}, 'molten_rocks': [], 'ore_fields': fields}

    @staticmethod
    def _with_rocks_of_the_new_world(world: RockyWorld, longitude: int, latitude: int, content: dict) -> dict:
        """The Km2's content with only the rocks and the molten rocks that the new world generates again there."""
        probe = Km2(world, longitude, latitude, {'Km2s': {f"{longitude} {latitude}": {
            'molten_rocks': content['molten_rocks']}}})
        generated = {rock.get_alterations_key() for rock in probe.rocks}
        return {'rocks': {key: value for key, value in content['rocks'].items() if key in generated},
                'molten_rocks': list(probe.molten_rocks),
                'ore_fields': content['ore_fields']}
    # endregion

    # region The player
    def migrate_player(self) -> None:
        player: dict = self.data['player']
        player['missions'] = [mission for mission in player['missions'] if self._migrate_mission(mission)]
        inside = player['inside_settlement']
        if inside is not None:
            player['inside_settlement'] = self.new_settlement_keys(inside)
            if player['inside_settlement'] is None:
                self.messages.append(f"the pilot was inside {inside}, which is gone: now outside")
        self._migrate_location(player)
        self.data['environment']['target_index'] = -1  # the bodies' order by distance changed

    def _migrate_mission(self, mission: dict) -> bool:
        """Gives the mission the new keys of its outposts; False if it must go."""
        issuer = self.new_settlement_keys(mission['issuer'])
        destination = self.new_settlement_keys(mission['destination'])
        if issuer is None or destination is None:
            self.messages.append(f"mission {mission['kind']} ({mission['status']}) of a vanished outpost: dropped")
            return False
        if mission['kind'] == 'scan_rock' and mission['status'] == 'open' and not self._rock_is_there(mission, issuer):
            self.messages.append("open mission scan_rock whose rock is no longer there: dropped")
            return False
        mission['issuer'], mission['destination'] = issuer, destination
        return True

    def _rock_is_there(self, mission: dict, issuer_keys: str) -> bool:
        system_key, orbit_key, planet_key, _ = issuer_keys.split('|')
        planet = self._planet(system_key, orbit_key, planet_key)
        site: dict = mission['rock_site']
        if planet is None or (site['world'] is not None and site['world'] >= len(planet.moons)):
            return False
        world = planet if site['world'] is None else planet.moons[site['world']]
        km2 = Km2(world, *site['km2'], None)
        return any([rock.longitude, rock.latitude] == site['rock'] for rock in km2.rocks)

    def _migrate_location(self, player: dict) -> None:
        """The world the ship was around, and its place on it, which must exist and be inside the new surface."""
        if player['orbit'] is None or player['asteroid'] is not None:
            return
        system = player['stellar_system']
        planet = self._planet(f"{system['x']:.0f} {system['y']:.0f} {system['z']:.0f}", str(int(player['orbit'])),
                              str(player['planet']))
        if planet is None:
            self.messages.append("the world of the ship does not exist any more: left as it is")
            return
        if player['moon'] is not None and player['moon'] >= len(planet.moons):
            self.messages.append(f"the moon {player['moon']} of the ship is gone: it is around the planet now")
            player['moon'] = None
        world = planet if player['moon'] is None else planet.moons[player['moon']]
        position = player['ship']['position']
        if player['ship']['is_bound']:
            half_turn = math.pi * world.radius
            position['x'] = (position['x'] + half_turn) % (2.0 * half_turn) - half_turn
            position['z'] = max(-half_turn / 2.0, min(half_turn / 2.0, position['z']))
    # endregion

    # region The knowledge
    def migrate_knowledge(self) -> None:
        """Takes out of the knowledge the bodies that the new galaxy does not have."""
        bodies: dict = self.data['knowledge']['bodies']
        for system_key in list(bodies):
            system = self._system(system_key)
            if system is None:
                del bodies[system_key]
                continue
            for orbit_key in list(bodies[system_key]):
                for planet_key in list(bodies[system_key][orbit_key]):
                    try:
                        planets = system.get_orbit(float(orbit_key)).planets
                    except (KeyError, ValueError, AttributeError, StopIteration):
                        planets = []
                    if int(planet_key) >= len(planets):
                        del bodies[system_key][orbit_key][planet_key]
                        continue
                    moons = bodies[system_key][orbit_key][planet_key]
                    moons[:] = [moon for moon in moons if int(moon) < len(planets[int(planet_key)].moons)]
                if not bodies[system_key][orbit_key]:
                    del bodies[system_key][orbit_key]
    # endregion


def migrate_file(source: str, target: str) -> List[str]:
    """Converts the savefile `source` into the new file `target` (which must not exist). Returns what was dropped or
    moved, in words."""
    if os.path.exists(target):
        raise FileExistsError(target)
    with open(source, encoding='utf-8') as file:
        data = json.load(file)
    migration = Migration(data)
    migration.migrate_galaxy()
    migration.migrate_player()
    migration.migrate_knowledge()
    with open(target, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    os.utime(target, (os.path.getatime(source), os.path.getmtime(source)))
    return migration.messages


def main(source_dir: str, target_dir: str) -> None:
    os.makedirs(target_dir, exist_ok=True)
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith('.json'):
            continue
        print(name)
        for message in migrate_file(os.path.join(source_dir, name), os.path.join(target_dir, name)):
            print(f"    {message}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
