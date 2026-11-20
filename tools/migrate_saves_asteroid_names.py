"""One-off conversion of the savefiles made before the asteroids were named when their offer is made (see
Asteroid.draw_name): the name each asteroid had is written into the save, so the pilot keeps the names already seen.

    python tools/migrate_saves_asteroid_names.py SOURCE_DIR TARGET_DIR

SOURCE_DIR holds one folder per galactic seed, with the savefiles of each (as data/Savefiles does). The converted files
go to TARGET_DIR at the same places, replacing the files there: keep a copy of SOURCE_DIR first.

The old name is replayed from the asteroid's seed, with the draws the old naming made. Nothing in a save records a name,
so this is not checked against one; an asteroid whose system or belt is gone from the galaxy is dropped with its mission.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import game_environment as gem  # noqa: E402  (first: it loads the galaxy package in the order the game does)
from universe.structure import seeds  # noqa: E402
from universe.bodies.asteroids.asteroid import Asteroid, AsteroidKey  # noqa: E402
from universe.society.people import knowledge  # noqa: E402
from universe.society.people.person import _pick_name  # noqa: E402
from universe.structure.asteroid_belt import AsteroidBelt  # noqa: E402
from universe.structure.orbit_layout import SystemScales  # noqa: E402
from universe.structure.stellar_system import StellarSystem  # noqa: E402

DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


def _old_name(my_random: random.Random) -> str:
    """The old naming: a random discoverer from the name lists, and a number up to 1000."""
    gender = 'female' if my_random.random() < 0.55 else 'male'
    language = 'chinese' if my_random.random() < 0.6 else 'english'
    discoverer = _pick_name(my_random, f'{language}_{gender}_surnames.txt')
    number = min(my_random.randint(1, 1000), my_random.randint(1, 1000))
    return f"{discoverer.capitalize()}-{number}"


def _belt_name(belt: AsteroidBelt, key: AsteroidKey) -> str:
    """The name of a belt's asteroid: the draws of its eccentricity and inclination, its three angles, then the name."""
    my_random = random.Random(seeds.derive(belt.seed, 'asteroid', str(key)))
    my_random.gauss(0.0, Asteroid.ECCENTRICITY_SIGMA)
    my_random.gauss(0.0, Asteroid.INCLINATION_SIGMA_DEGREES)
    for _ in range(3):
        my_random.random()
    return _old_name(my_random)


def _free_name(system: StellarSystem, offer_seed: int) -> str:
    """The name of a free-living asteroid: the draws of Asteroid.free_living up to its diameter, then its three angles,
    then the name."""
    my_random = random.Random(seeds.derive(system.seed, 'free asteroid', offer_seed))
    scales = SystemScales.of(system.star)
    low, high = (scales.snow_line * ratio for ratio in Asteroid.FREE_SNOW_LINES)
    my_random.uniform(math.log(low), math.log(high))
    my_random.gauss(0.0, Asteroid.FREE_ECCENTRICITY_SIGMA)
    my_random.gauss(0.0, Asteroid.FREE_INCLINATION_SIGMA_DEGREES)
    tiers = [tier for tier, _ in Asteroid.FREE_TIERS]
    weights = [weight for _, weight in Asteroid.FREE_TIERS]
    my_random.choices(tiers, weights)
    my_random.getrandbits(64)  # the generator of the diameter
    for _ in range(3):
        my_random.random()
    return _old_name(my_random)


class Migration:
    """The names of one savefile's asteroids. `messages` tell what was dropped."""

    def __init__(self, data: dict) -> None:
        self.data: dict = data
        self.messages: list[str] = []
        environment: dict = data['environment']
        knowledge.current_knowledge = knowledge.Knowledge()
        gem.current_environment = gem.GameEnvironment(
            environment['galactic_seed'], datetime.strptime(environment['date_time'], DATE_FORMAT), None, None)

    def _system(self, key: str) -> StellarSystem | None:
        return gem.current_environment.galaxy.system_of_key(key)

    def migrate_galaxy(self) -> None:
        """The names of the belts' relevant asteroids and of the systems' free-living ones."""
        for system_key, alterations in self.data['environment']['galaxy_alterations'].items():
            if system_key == 'date_time':
                continue
            system = self._system(system_key)
            if system is None:
                self.messages.append(f"system {system_key} is gone: its asteroids are dropped with it")
                continue
            for key, value in alterations.items():
                if key == 'free_asteroids':
                    for offer_seed, saved in value.items():
                        if 'name' not in saved:
                            saved['name'] = _free_name(system, int(offer_seed))
                elif isinstance(value, dict) and 'asteroids' in value:
                    belt = system.get_orbit(float(key))
                    if not isinstance(belt, AsteroidBelt):
                        self.messages.append(f"orbit {key} of {system_key} is no belt any more")
                        continue
                    for text, saved in value['asteroids'].items():
                        if 'name' not in saved:
                            saved['name'] = _belt_name(belt, AsteroidKey.from_ints(text.split()))

    def _site_name(self, system: StellarSystem, site: dict) -> str | None:
        """The name of the asteroid of a site in `system`, None if the belt is gone."""
        if site['belt'] is None:
            return _free_name(system, int(site['seed']))
        belt = system.get_orbit(float(site['belt']))
        if not isinstance(belt, AsteroidBelt):
            return None
        return _belt_name(belt, AsteroidKey.from_ints(site['key'].split()))

    def migrate_player(self) -> None:
        """The names of the ship's fixed asteroid and of the missions' asteroids. A site without its asteroid is dropped."""
        player: dict = self.data['player']
        if player['asteroid'] is not None:
            system = self._fixed_system(player['stellar_system'])
            name = None if system is None else self._site_name(system, player['asteroid'])
            if name is None:
                self.messages.append("the asteroid the ship was fixed to is gone: the ship is not fixed to it")
                player['asteroid'] = None
            else:
                player['asteroid'].setdefault('name', name)
        kept = []
        for mission in player['missions']:
            site = mission.get('asteroid_site')
            if site is None or 'name' in site:
                kept.append(mission)
                continue
            system = self._system(site['system'])
            name = None if system is None else self._site_name(system, site)
            if name is None:
                self.messages.append(f"the mission {mission['kind']} of an asteroid that is gone is dropped")
                continue
            site['name'] = name
            kept.append(mission)
        player['missions'] = kept

    def _fixed_system(self, position: dict) -> StellarSystem | None:
        """The system of the ship's stellar system, from its galactic position."""
        try:
            star = gem.current_environment.galaxy.fixed_star_at((position['x'], position['y'], position['z']))
        except ValueError:
            return None
        return self._system(" ".join(str(c) for c in star.cell))


def migrate_file(source: str, target: str) -> list[str]:
    """Converts the savefile `source` into `target`, which it replaces. Returns what was dropped, in words."""
    with open(source, encoding='utf-8') as file:
        data = json.load(file)
    migration = Migration(data)
    migration.migrate_galaxy()
    migration.migrate_player()
    with open(target, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    os.utime(target, (os.path.getatime(source), os.path.getmtime(source)))
    return migration.messages


def main(source_dir: str, target_dir: str) -> None:
    for folder in sorted(os.listdir(source_dir)):
        source_folder = os.path.join(source_dir, folder)
        if not os.path.isdir(source_folder):
            continue
        target_folder = os.path.join(target_dir, folder)
        os.makedirs(target_folder, exist_ok=True)
        for name in sorted(os.listdir(source_folder)):
            if not name.endswith('.json'):
                continue
            print(os.path.join(folder, name))
            for message in migrate_file(os.path.join(source_folder, name), os.path.join(target_folder, name)):
                print(f"    {message}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
