import pygame
import json

class Savefile:
    def __init__(self):
        print('Savefile init')

    @classmethod
    def new(cls, galacticSeed, gameDateTime):
        data = {
            'galacticSeed': galacticSeed,
            'gameDateTime': str(gameDateTime)
        }
        fileName = str(gameDateTime)
        fileName = fileName.replace(' ', 'T').replace(':', '_')[:19]
        fileName = 'Savefile ' + str(galacticSeed) + ' ' + fileName + '.json'
        print("Filename: " + fileName)
        with open(fileName, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        pass