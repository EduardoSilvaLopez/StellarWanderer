import json
import os
import glob
from datetime import datetime

from  Galaxies.Galaxy import Galaxy
from  Galaxies.World import World
from  Galaxies.Km2 import Km2
from GameEnvironment import GameEnvironment
from Player import Player

class Savefile:

    @staticmethod
    def load():
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
        
        # Load the most recent savefile
        print(f"Loading savefile: {latest_file}")
        with open(latest_file, 'r', encoding='utf-8') as f:
            load_object = json.load(f)

        GameEnvironment.singleton = GameEnvironment(load_object['environment']['galactic_seed'], load_object['environment']['galaxy_alterations'])
        print("Loaded seed: " + str(GameEnvironment.singleton.galaxy.seed))

        GameEnvironment.singleton.current_world = GameEnvironment.singleton.galaxy.add_stellar_system(
            load_object['player']['stellar_system.x'],
            load_object['player']['stellar_system.y'],
            load_object['player']['stellar_system.z']).add_orbit(
                load_object['player']['orbit.distance_from_star']).add_world(
                    load_object['player']['world.degrees_in_orbit']
                    )
        GameEnvironment.singleton.current_world.ensure_surroundings(load_object['player']['km2.longitude'], load_object['player']['km2.latitude'])
        GameEnvironment.singleton.date_time = datetime.strptime(load_object['environment']['date_time'], '%Y-%m-%d %H:%M:%S.%f')

        player = Player()
        player.time_scale = load_object['player']['time_scale']
        player.orientation = load_object['player'].get('orientation', 0.0)
        player.position.x = load_object['player']['x']
        player.position.y = load_object['player']['y']
        player.position.z = load_object['player']['z']
        player.position.Km2 = player.find_km2_in(GameEnvironment.singleton.current_world)
        Player.singleton = player

        # Apply the alterations in the surroundings of the player.
        GameEnvironment.singleton.saved_alterations = load_object['environment']['galaxy_alterations']

    @staticmethod
    def save():
        '''Saves the current state of the game to a JSON file, from the GameEnvironment and Player singletons.'''
        environment = GameEnvironment.singleton
        player = Player.singleton

        data = {
            'environment': {
                'galactic_seed': environment.galaxy.seed,
                'date_time': str(environment.date_time),
                'galaxy_alterations': GameEnvironment.singleton.galaxy.get_alterations()
            }
            , 'player': {
                'time_scale': player.time_scale,
                'orientation': player.orientation,
                'stellar_system.x': player.position.Km2.parent_world.parent_orbit.parent_stellar_system.x,
                'stellar_system.y': player.position.Km2.parent_world.parent_orbit.parent_stellar_system.y,
                'stellar_system.z': player.position.Km2.parent_world.parent_orbit.parent_stellar_system.z,
                'orbit.distance_from_star': player.position.Km2.parent_world.parent_orbit.distance_from_star,
                'world.degrees_in_orbit': player.position.Km2.parent_world.degrees_in_orbit,
                'km2.longitude': player.position.Km2.longitude,
                'km2.latitude': player.position.Km2.latitude,
                'x': player.position.x,
                'y': player.position.y,
                'z': player.position.z
            }
        }
        file_name = str(environment.date_time)
        file_name = file_name.replace(' ', 'T').replace(':', '_')[:19]
        file_name = 'Savefile ' + str(environment.galaxy.seed) + ' ' + file_name + '.json'
        file_name = 'Savefiles/' + file_name
        print("New savefile's name: " + file_name)
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
