import json
import os
import glob

import logging; logger = logging.getLogger(__name__)
from datetime import datetime

from spaceships.ship import Ship
import game_environment as gem
import galaxies.people.player as pem
from common.paths import data_path, SAVEFILES_DIR

# A save's file name is the name typed in the starting dialog (or the default), plus ".json".
SAVE_NAME_FORBIDDEN = '\\/:*?"<>|'
SAVE_NAME_MAX_LENGTH = 40


class Savefile:

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

    @staticmethod
    def load_from_file(filepath: str) -> None:
        '''Loads a specific savefile into GameEnvironment and Player singletons.

        Args:
            filepath: Path to the savefile to load

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        logger.info(f"Loading savefile: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            load_object = json.load(f)

        game_date_time = datetime.strptime(load_object['environment']['date_time'], '%Y-%m-%d %H:%M:%S.%f')
        # JSON keys are text; the people are looked up by their float seed.
        people_alterations = {float(seed): values for seed, values in load_object['environment']['persons'].items()}
        gem.current_environment = gem.GameEnvironment(
            load_object['environment']['galactic_seed'],
            game_date_time,
            load_object['environment']['galaxy_alterations'],
            people_alterations
            )
        logger.debug("Loaded seed: " + str(gem.current_environment.galaxy.seed))

        player_data: dict = load_object['player']
        system_data: dict = player_data['stellar_system']
        gem.current_environment.nearest_system = gem.current_environment.galaxy.add_stellar_system(
            system_data['x'], system_data['y'], system_data['z']
            )
        from galaxies.orbit import Orbit
        current_orbit: Orbit = gem.current_environment.nearest_system.get_orbit(float(player_data['orbit']))
        planet_idx: int = player_data['planet']
        moon_idx: int = player_data['moon']
        if moon_idx is None:
            gem.current_environment.nearest_world = current_orbit.planets[planet_idx]
        else:
            gem.current_environment.nearest_world = current_orbit.planets[planet_idx].moons[moon_idx]

        position_data: dict = player_data['ship']['position']
        gem.current_environment.nearest_world.update_surroundings(
            position_data['y'], position_data['x'], position_data['z'], game_date_time
            )

        pem.current_player = pem.Player.deserialize(load_object['player'])

    @staticmethod
    def load_last() -> None:
        '''Loads the most recent savefile directly into GameEnvironment and Player singletons.

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        savefiles = glob.glob(data_path(SAVEFILES_DIR, '*.json'))
        
        if not savefiles:
            raise FileNotFoundError("No savefiles found.")
        
        # Parse datetime from filename and find the most recent
        # Filename format: "Savefile {seed} {datetime}.json"
        # DateTime format in filename: "YYYY-MM-DDTHH_MM_SS"
        latest_file = None
        latest_datetime = None
        
        for filepath in savefiles:
            file_datetime = os.path.getmtime(filepath)
            
            if latest_datetime is None or file_datetime > latest_datetime:
                latest_datetime = file_datetime
                latest_file = filepath
        
        if latest_file is None:
            raise FileNotFoundError("No valid savefiles found with datetime information.")
        
        Savefile.load_from_file(latest_file)

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

        persons_dict = {}
        for key, person_dict in env.persons.items():
            persons_dict[key] = person_dict

        data = {
            'environment': {
                'galactic_seed': env.galaxy.seed,
                'date_time': env.date_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'galaxy_alterations': env.galaxy.get_alterations(),
                'persons': persons_dict
            }
            , 'player': player.serialize()
        }
        os.makedirs(data_path(SAVEFILES_DIR), exist_ok=True)
        file_path = data_path(SAVEFILES_DIR, name + '.json')
        logger.info("New savefile's name: " + file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
