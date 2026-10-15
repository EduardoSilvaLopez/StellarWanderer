import json
import os
import glob

import logging; logger = logging.getLogger(__name__)
from datetime import datetime

from Spaceships.ship import Ship
import game_environment as gem
import Galaxies.People.player as pem
from paths import data_path, SAVEFILES_DIR

class Savefile:

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
        from Galaxies.orbit import Orbit
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
        savefiles = glob.glob(data_path(SAVEFILES_DIR, 'Savefile *.json'))
        
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
    def save() -> None:
        '''Saves the current state of the game to a JSON file, from the GameEnvironment and Player singletons.'''
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
        file_name = env.date_time.strftime('%Y-%m-%d %H:%M:%S')
        file_name = file_name.replace(' ', 'T').replace(':', '_')[:19]
        file_name = 'Savefile ' + str(env.galaxy.seed) + ' ' + file_name + '.json'
        os.makedirs(data_path(SAVEFILES_DIR), exist_ok=True)
        file_name = data_path(SAVEFILES_DIR, file_name)
        logger.info("New savefile's name: " + file_name)
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
