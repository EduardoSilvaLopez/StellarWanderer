import json

from GameEnvironment import GameEnvironment

class Savefile:
    lastName = ''
    lastSavefile = None

    @classmethod
    def new(cls, environment, playerDateTime):
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
            cls.lastName = f.name

    def __init__(self):
        self.name = Savefile.lastName

    @classmethod
    def load(cls):
        with open(Savefile.lastName, 'r', encoding='utf-8') as f:
            loadObject = json.load(f)
            GameEnvironment.curEnv = GameEnvironment(loadObject['environment']['galacticSeed'])
            print("Loaded seed: " + str(GameEnvironment.curEnv.galacticSeed))
