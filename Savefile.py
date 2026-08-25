import json
import os
import glob
from datetime import datetime

from GameEnvironment import GameEnvironment

class Savefile:
    def __init__(self):
        self.playerDateTime = None

    def load(self):
        # Find all savefiles matching the pattern
        savefiles = glob.glob('Savefile *.json')
        
        if not savefiles:
            raise FileNotFoundError("No savefiles found.")
        
        # Parse datetime from filename and find the most recent
        # Filename format: "Savefile {seed} {datetime}.json"
        # DateTime format in filename: "YYYY-MM-DDTHH_MM_SS"
        latest_file = None
        latest_datetime = None
        
        for filepath in savefiles:
            try:
                # Extract datetime part from filename
                # Format: "Savefile {seed} YYYY-MM-DDTHH_MM_SS.json"
                filename = os.path.basename(filepath)
                # Remove "Savefile " prefix and ".json" suffix
                datetime_part = filename.replace('Savefile ', '').rsplit(' ', 1)[-1].replace('.json', '')
                # Convert "YYYY-MM-DDTHH_MM_SS" back to datetime object
                file_datetime = datetime.strptime(datetime_part, '%Y-%m-%dT%H_%M_%S')
                
                if latest_datetime is None or file_datetime > latest_datetime:
                    latest_datetime = file_datetime
                    latest_file = filepath
            except (ValueError, IndexError):
                # Skip files that don't match the expected format
                continue
        
        if latest_file is None:
            raise FileNotFoundError("No valid savefiles found with datetime information.")
        
        # Load the most recent savefile
        print(f"Loading savefile: {latest_file}")
        with open(latest_file, 'r', encoding='utf-8') as f:
            load_object = json.load(f)
        GameEnvironment.curEnv = GameEnvironment(load_object['environment']['galacticSeed'])
        print("Loaded seed: " + str(GameEnvironment.curEnv.galaxy.seed))
        self.playerDateTime = datetime.strptime(load_object['player']['dateTime'], '%Y-%m-%d %H:%M:%S.%f')
        return self

    def save(self, environment, playerDateTime ):
        data = {
            'environment': {
                'galacticSeed': environment.galaxy.seed
            },
            'player': {
                'dateTime': str(playerDateTime)
            }
        }
        file_name = str(playerDateTime)
        file_name = file_name.replace(' ', 'T').replace(':', '_')[:19]
        file_name = 'Savefile ' + str(environment.galaxy.seed) + ' ' + file_name + '.json'
        print("New savefile's name: " + file_name)
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return self