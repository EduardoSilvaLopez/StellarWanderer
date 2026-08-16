import json
from datetime import datetime
from logging import setLogRecordFactory
from xmlrpc.client import DateTime

from GameEnvironment import GameEnvironment

class Savefile:
    lastName = ''

    def __init__(self):
        self.playerDateTime = None

    def load(self):
        with open(Savefile.lastName, 'r', encoding='utf-8') as f:
            load_object = json.load(f)
        GameEnvironment.curEnv = GameEnvironment(load_object['environment']['galacticSeed'])
        print("Loaded seed: " + str(GameEnvironment.curEnv.galacticSeed))
        self.playerDateTime = datetime.strptime(load_object['player']['dateTime'], '%Y-%m-%d %H:%M:%S.%f')
        return self

    def save(self, environment, playerDateTime ):
        data = {
            'environment': {
                'galacticSeed': environment.galacticSeed
            },
            'player': {
                'dateTime': str(playerDateTime)
            }
        }
        fileName = str(playerDateTime)
        fileName = fileName.replace(' ', 'T').replace(':', '_')[:19]
        fileName = 'Savefile ' + str(environment.galacticSeed) + ' ' + fileName + '.json'
        print("New savefile's name: " + fileName)
        with open(fileName, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        Savefile.lastName = fileName
        return self
