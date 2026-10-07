import json
import os
import glob

import logging; logger = logging.getLogger(__name__)
from datetime import datetime

from Spaceships.Ship import Ship
import GameEnvironment as gem
import Player as pem

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
        gem.current_environment = gem.GameEnvironment(
            load_object['environment']['galactic_seed'],
            game_date_time,
            load_object['environment']['galaxy_alterations']
            )
        logger.debug("Loaded seed: " + str(gem.current_environment.galaxy.seed))

        from Galaxies.StellarSystem import StellarSystem
        gem.current_environment.nearest_system = gem.current_environment.galaxy.add_stellar_system(
            load_object['player']['stellar_system.x'],
            load_object['player']['stellar_system.y'],
            load_object['player']['stellar_system.z']
            )
        gem.current_environment.nearest_world = gem.current_environment.nearest_system.get_orbit(
                float(load_object['player']['orbit.number'])
                ).worlds[load_object['player']['world.world_idx']]
        gem.current_environment.nearest_world.update_surroundings(
            load_object['player']['position.y'],
            load_object['player']['position.x'],
            load_object['player']['position.z'],
            game_date_time
            )

        pem.current_player = pem.Player.deserialize(load_object['player'])

    @staticmethod
    def load_last() -> None:
        '''Loads the most recent savefile directly into GameEnvironment and Player singletons.

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        savefiles = glob.glob('Savefiles/Savefile *.json')
        
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
        environment = gem.current_environment
        player = pem.current_player

        data = {
            'environment': {
                'galactic_seed': environment.galaxy.seed,
                'date_time': str(environment.date_time),
                'galaxy_alterations': gem.current_environment.galaxy.get_alterations()
            }
            , 'player': player.serialize()
        }
        file_name = str(environment.date_time)
        file_name = file_name.replace(' ', 'T').replace(':', '_')[:19]
        file_name = 'Savefile ' + str(environment.galaxy.seed) + ' ' + file_name + '.json'
        file_name = 'Savefiles/' + file_name
        logger.info("New savefile's name: " + file_name)
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
