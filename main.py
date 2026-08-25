"""Stellar Wanderer — first-person cockpit view.

Controls:
    Keypad +   compress time 10x further, up to 1 000 000 s/s
    Keypad -   step back down, no slower than 1 s/s
    Esc        quit
"""

from datetime import datetime, timedelta

import pygame

from FontCache import FontCache
from Player import Player
from Savefile import Savefile
from GameEnvironment import GameEnvironment

import Gui

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1280, 720)
MIN_SIZE = (640, 400)
FPS = 60

# Ship clock. Rendered with an unpadded year so it reads "500-01-01", as spec'd.
EPOCH = datetime(500, 1, 1)

# datetime tops out at year 9999; stop there rather than raising mid-frame.
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - EPOCH).total_seconds()

STAR_COUNT = 260
STAR_SEED = 20270101

def main():
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    fonts = FontCache()
    stars = Gui.make_starfield(STAR_COUNT, STAR_SEED)
    elapsed = 0.0  # seconds of ship time since EPOCH
    time_scale = Gui.TIME_SCALE_MIN

    # Create all seeds and random objects and calculate the initial planet's radius.
    print("Give the galactic Seed: ")
    galacticSeed = 1 # galacticSeed = input()
    game_environment = GameEnvironment(galacticSeed)
    player = Player().set_in_environment(game_environment)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_KP_PLUS:
                    time_scale = min(time_scale * Gui.TIME_SCALE_STEP, Gui.TIME_SCALE_MAX)
                elif event.key == pygame.K_KP_MINUS:
                    time_scale = max(time_scale // Gui.TIME_SCALE_STEP, Gui.TIME_SCALE_MIN)
                elif event.key == pygame.K_F5:
                    Savefile().save(game_environment, player, EPOCH + timedelta(seconds=elapsed))
                elif event.key == pygame.K_F6:
                    loaded_savefile = Savefile().load()
                    elapsed = (loaded_savefile.playerDateTime - EPOCH).total_seconds()
            elif event.type == pygame.VIDEORESIZE:
                size = (max(event.w, MIN_SIZE[0]), max(event.h, MIN_SIZE[1]))
                screen = pygame.display.set_mode(size, pygame.RESIZABLE)

        dt = clock.tick(FPS) / 1000.0
        elapsed = min(elapsed + dt * time_scale, MAX_ELAPSED)

        Gui.draw(screen, fonts, stars, EPOCH + timedelta(seconds=elapsed), game_environment, player, time_scale)
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    print('Starting game.')
    main()
    print('Ending game.')
