import json
import os
import glob
from datetime import datetime

from  Galaxies.Galaxy import Galaxy
from GameEnvironment import GameEnvironment
from Player import Player

class Savefile:

    @staticmethod
    def load():
        '''Loads the most recent savefile directly into GameEnvironment and Player singletons.'''
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

        GameEnvironment.singleton.galaxy = Galaxy(load_object['environment']['GalacticSeed'])
        print("Loaded seed: " + str(GameEnvironment.singleton.galaxy.seed))

        GameEnvironment.singleton.current_world = GameEnvironment.singleton.galaxy.add_stellar_system(
            load_object['player']['StellarSystem.x'],
            load_object['player']['StellarSystem.y'],
            load_object['player']['StellarSystem.z']).add_orbit(
                load_object['player']['Orbit.DistanceFromStar']).add_world(
                    load_object['player']['World.DegreesInOrbit']
                    )
        GameEnvironment.singleton.current_world.ensure_surroundings(load_object['player']['Km2.Longitude'], load_object['player']['Km2.Latitude'])

        player = Player.singleton     
        player.date_time = datetime.strptime(load_object['player']['dateTime'], '%Y-%m-%d %H:%M:%S.%f')
        player.time_scale = load_object['player']['timeScale']
        player.position.x = load_object['player']['x']
        player.position.y = load_object['player']['y']
        player.position.z = load_object['player']['z']
        player.position.Km2 = player.find_km2_in(GameEnvironment.singleton.current_world)

    @staticmethod
    def save():
        '''Saves the current state of the game to a JSON file, from the GameEnvironment and Player singletons.'''
        environment = GameEnvironment.singleton
        player = Player.singleton

        data = {
            'environment': {
                'GalacticSeed': environment.galaxy.seed,
            }
            , 'player': {
                'dateTime': str(player.date_time),
                'timeScale': player.time_scale,
                'StellarSystem.x': player.position.Km2.parent_world.parent_orbit.parent_stellar_system.x,
                'StellarSystem.y': player.position.Km2.parent_world.parent_orbit.parent_stellar_system.y,
                'StellarSystem.z': player.position.Km2.parent_world.parent_orbit.parent_stellar_system.z,
                'Orbit.DistanceFromStar': player.position.Km2.parent_world.parent_orbit.distance_from_star,
                'World.DegreesInOrbit': player.position.Km2.parent_world.degrees_in_orbit,
                'Km2.Longitude': player.position.Km2.longitude,
                'Km2.Latitude': player.position.Km2.latitude,
                'x': player.position.x,
                'y': player.position.y,
                'z': player.position.z
            }
        }
        file_name = str(player.date_time)
        file_name = file_name.replace(' ', 'T').replace(':', '_')[:19]
        file_name = 'Savefile ' + str(environment.galaxy.seed) + ' ' + file_name + '.json'
        file_name = 'Savefiles/' + file_name
        print("New savefile's name: " + file_name)
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
