"""Stellar Wanderer — first-person cockpit view.

Controls:
    Keypad +   compress time 10x further, up to 1 000 000 s/s
    Keypad -   step back down, no slower than 1 s/s
    Numpad +   increase altitude (speed depends on time scale)
    Numpad -   decrease altitude (speed depends on time scale)
    Esc        quit
"""

from datetime import datetime, timedelta

import pygame

from FontCache import FontCache
from Player import Player
from Savefile import Savefile
from GameEnvironment import GameEnvironment
from Graphics.Gui import Gui
from Graphics.Stars import Stars

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1280, 720)
MIN_SIZE = (640, 400)
FPS = 60

STAR_COUNT = 260
STAR_SEED = 20270101

# Altitude change control
ALTITUDE_CHANGE_PER_SECOND = 1  # meters per second at time_scale 1
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - Player.EPOCH).total_seconds() # datetime tops out at year 9999;

def main():
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    fonts = FontCache()
    stars = Stars.make_starfield(STAR_COUNT, STAR_SEED)
    elapsed = 0.0  # seconds of ship time since EPOCH

    # Create all seeds and random objects and calculate the initial planet's radius.
    print("Give the galactic Seed: ")
    galacticSeed = 1 # galacticSeed = input()
    game_environment = GameEnvironment(galacticSeed)
    player = Player().spawn_in_environment(game_environment)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_KP_PLUS:
                    player.increase_time_scale()
                elif event.key == pygame.K_KP_MINUS:
                    player.decrease_time_scale()
                elif event.key == pygame.K_F5:
                    Savefile.save()
                elif event.key == pygame.K_F6:
                    Savefile.load()
                    elapsed = (Player.singleton.date_time - Player.EPOCH).total_seconds()
            elif event.type == pygame.VIDEORESIZE:
                size = (max(event.w, MIN_SIZE[0]), max(event.h, MIN_SIZE[1]))
                screen = pygame.display.set_mode(size, pygame.RESIZABLE)

        # Handle continuous altitude adjustment with numpad +/- (time-scale dependent)
        keys = pygame.key.get_pressed()
        dt = clock.tick(FPS) / 1000.0

        player.update_position(
            dt * player.time_scale\
            , 1 if keys[pygame.K_d] else (- 1 if keys[pygame.K_a] else 0)
            , 1 if keys[pygame.K_KP_9] else (- 1 if keys[pygame.K_KP_3] else 0)
            , 1 if keys[pygame.K_w] else (- 1 if keys[pygame.K_s] else 0)
        )        
        
        elapsed = min(elapsed + dt * player.time_scale, MAX_ELAPSED)
        player.date_time = Player.EPOCH + timedelta(seconds=elapsed)

        gui = Gui()
        gui.draw(screen, fonts, game_environment, player)
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    print('Starting game.')
    main()
    print('Ending game.')