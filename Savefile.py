import json
from datetime import datetime

from GameEnvironment import GameEnvironment

class Savefile:
    lastName = ''

    def __init__(self):
        self.playerDateTime = None

    def load(self):
        with open(Savefile.lastName, 'r', encoding='utf-8') as f:
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
        Savefile.lastName = file_name
        return self
