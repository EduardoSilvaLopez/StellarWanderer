import json
import os
import glob

import logging
from datetime import datetime

import game_environment as gem
import knowledge
import galaxies.people.player as pem
from common.paths import data_path, SAVEFILES_DIR

logger = logging.getLogger(__name__)

# A save's file name is the name typed in the starting dialog (or the default), plus ".json".
SAVE_NAME_FORBIDDEN = '\\/:*?"<>|'
SAVE_NAME_MAX_LENGTH = 40


class Savefile:

    # region Names
    @staticmethod
    def clean_name(text: str) -> str:
        '''A typed name made safe for a file name: printable, no path or reserved characters, no ".json" ending,
        at most SAVE_NAME_MAX_LENGTH characters. Empty when nothing usable is left.'''
        cleaned = ''.join(c for c in text if c.isprintable() and c not in SAVE_NAME_FORBIDDEN).strip()
        if cleaned.lower().endswith('.json'):
            cleaned = cleaned[:-len('.json')].strip()
        return cleaned[:SAVE_NAME_MAX_LENGTH].strip()

    @staticmethod
    def default_name() -> str:
        '''The name of a save when none is typed: the seed and the game's date and time, to the second.'''
        env = gem.current_environment
        time_text = env.date_time.strftime('%Y-%m-%d %H:%M:%S').replace(' ', 'T').replace(':', '_')[:19]
        return 'Savefile ' + str(env.galaxy.seed) + ' ' + time_text

    @staticmethod
    def exists(name: str) -> bool:
        return os.path.exists(data_path(SAVEFILES_DIR, name + '.json'))
    # endregion

    # region Saving
    @staticmethod
    def save() -> bool:
        '''F5: saves the game under the default name. If that name is taken (another save in the same game second),
        nothing is saved. Returns whether it saved.'''
        name = Savefile.default_name()
        if Savefile.exists(name):
            return False
        Savefile.save_as(name)
        return True

    @staticmethod
    def save_as(name: str) -> None:
        '''Saves the current state of the game to `name` (a clean name, see clean_name), from the GameEnvironment and
        Player singletons. Replaces a save of that name.'''
        env = gem.current_environment
        player = pem.current_player

        data = {
            'environment': {
                'galactic_seed': env.galaxy.seed,
                'date_time': env.date_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'galaxy_alterations': env.galaxy.get_alterations(),
                'persons': dict(env.persons)
            }
            , 'player': player.serialize()
            , 'knowledge': knowledge.current_knowledge.serialize()
        }
        os.makedirs(data_path(SAVEFILES_DIR), exist_ok=True)
        file_path = data_path(SAVEFILES_DIR, name + '.json')
        logger.info("New savefile's name: " + file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    # endregion

    # region Loading
    @staticmethod
    def load_last() -> None:
        '''Loads the most recently written savefile directly into GameEnvironment and Player singletons.

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        savefiles = glob.glob(data_path(SAVEFILES_DIR, '*.json'))
        if not savefiles:
            raise FileNotFoundError("No savefiles found.")
        Savefile.load_from_file(max(savefiles, key=os.path.getmtime))

    @staticmethod
    def load_from_file(filepath: str) -> None:
        '''Loads a specific savefile into GameEnvironment and Player singletons.

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        from common.updating import update_queue
        update_queue.clear()

        logger.info(f"Loading savefile: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            load_object = json.load(f)

        # Before the environment: the systems it generates add to the knowledge.
        knowledge.current_knowledge = knowledge.Knowledge.deserialize(load_object['knowledge'])
        game_date_time = datetime.strptime(load_object['environment']['date_time'], '%Y-%m-%d %H:%M:%S.%f')
        # JSON keys are text; the people are looked up by their int seed.
        people_alterations = {int(seed): values for seed, values in load_object['environment']['persons'].items()}
        gem.current_environment = gem.GameEnvironment(
            load_object['environment']['galactic_seed'],
            game_date_time,
            load_object['environment']['galaxy_alterations'],
            people_alterations
            )
        logger.debug("Loaded seed: " + str(gem.current_environment.galaxy.seed))

        player_data: dict = load_object['player']
        system_data: dict = player_data['stellar_system']
        galaxy = gem.current_environment.galaxy
        gem.current_environment.nearest_system = galaxy.add_stellar_system(
            galaxy.fixed_star_at((system_data['x'], system_data['y'], system_data['z']))
            )
        if player_data['orbit'] is None:  # the star was the last fixed body
            body = gem.current_environment.nearest_system.star
        else:
            current_orbit = gem.current_environment.nearest_system.get_orbit(float(player_data['orbit']))
            planet_idx: int = player_data['planet']
            moon_idx: int = player_data['moon']
            if moon_idx is None:
                body = current_orbit.planets[planet_idx]
            else:
                body = current_orbit.planets[planet_idx].moons[moon_idx]
        # The target is not saved: it starts as the body the ship was last fixed to. A bound ship is fixed to its world;
        # an unbound one is fixed only if it is in a fixed zone, which the next frame works out (refresh_fixed_body).
        gem.current_environment.targeted_body = gem.current_environment.last_fixed_body = body
        gem.current_environment.fixed_body = body if player_data['ship']['is_bound'] else None

        position_data: dict = player_data['ship']['position']
        world = gem.current_environment.fixed_world  # None for the star: no surroundings to load
        if world is not None:
            world.update_surroundings(position_data['y'], position_data['x'], position_data['z'], game_date_time)

        pem.current_player = pem.Player.deserialize(load_object['player'])
    # endregion
