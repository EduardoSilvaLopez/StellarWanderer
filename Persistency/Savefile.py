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

        gem.current_environment.current_world = gem.current_environment.galaxy.add_stellar_system(
            load_object['player']['stellar_system.x'],
            load_object['player']['stellar_system.y'],
            load_object['player']['stellar_system.z']
            ).add_orbit(
                load_object['player']['orbit.distance_from_star']
                ).add_world(
                    load_object['player']['world.initial_degrees_in_orbit']
                    )
        gem.current_environment.current_world.update_surroundings(
            load_object['player']['x'],
            load_object['player']['z'],
            game_date_time
            )

        pem.current_player = pem.Player()
        pem.current_player.time_scale = load_object['player']['time_scale']
        pem.current_player.orientation = load_object['player'].get('orientation', 0.0)
        pem.current_player.position.x = load_object['player']['x']
        pem.current_player.position.y = load_object['player']['y']
        pem.current_player.position.z = load_object['player']['z']
        pem.current_player.position.km2 = gem.current_environment.current_world.get_km2_at(pem.current_player.position.x, pem.current_player.position.z)

        pem.current_player.ship = Ship.load(pem.current_player, load_object['player']['ship'])

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
            , 'player': {
                'time_scale': player.time_scale,
                'orientation': player.orientation,
                'stellar_system.x': environment.current_world.parent_orbit.parent_stellar_system.x,
                'stellar_system.y': environment.current_world.parent_orbit.parent_stellar_system.y,
                'stellar_system.z': environment.current_world.parent_orbit.parent_stellar_system.z,
                'orbit.distance_from_star': environment.current_world.parent_orbit.distance_from_star,
                'world.initial_degrees_in_orbit': environment.current_world.initial_degrees_in_orbit,
                'x': player.position.x,
                'y': player.position.y,
                'z': player.position.z,
                'ship': player.ship.serialize()
            }
        }
        file_name = str(environment.date_time)
        file_name = file_name.replace(' ', 'T').replace(':', '_')[:19]
        file_name = 'Savefile ' + str(environment.galaxy.seed) + ' ' + file_name + '.json'
        file_name = 'Savefiles/' + file_name
        logger.info("New savefile's name: " + file_name)
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
