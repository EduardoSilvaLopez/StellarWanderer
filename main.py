"""Stellar Wanderer — first-person cockpit view.

Controls:
    Keypad +   compress time 10x further, up to 1 000 000 s/s
    Keypad -   step back down, no slower than 1 s/s
    Numpad +   increase altitude (speed depends on time scale)
    Numpad -   decrease altitude (speed depends on time scale)
    Q          turn counterclockwise (speed depends on time scale)
    E          turn clockwise (speed depends on time scale)
    SPACE      fire the laser
    Esc        quit
"""

from datetime import datetime, timedelta

import pygame

from Graphics.FontCache import FontCache
import GameEnvironment as game_environment_module
import Player as player_module
from Persistency.Savefile import Savefile
from Persistency.StartDialog import StartDialog
from Graphics.OpenGLGui import OpenGLGui
from Graphics.Stars import Stars
from Updating.UpdateQueue import update_queue

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1280, 720)
MIN_SIZE = (640, 400)
FPS = 60

STAR_COUNT = 260
STAR_SEED = 20270101

# Altitude change control
ALTITUDE_CHANGE_PER_SECOND = 1  # meters per second at time_scale 1
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - game_environment_module.GameEnvironment.EPOCH).total_seconds() # datetime tops out at year 9999;
EPOCH = game_environment_module.GameEnvironment.EPOCH

def main():
    pygame.init()

    # Create temporary display for startup dialog
    temp_screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption(WINDOW_TITLE)

    # Show startup dialog to load or create a new game
    dialog = StartDialog(surface=temp_screen)
    choice = dialog.run()

    # Now create the main OpenGL display
    screen = pygame.display.set_mode(
        WINDOW_SIZE, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
    )
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    fonts = FontCache()
    elapsed = 0.0  # seconds of ship time since EPOCH

    if choice is None:
        pygame.quit()
        return

    action, value = choice

    if action == 'load':
        # Load existing savefile
        Savefile.load_from_file(value)
        elapsed = (game_environment_module.current_environment.date_time - EPOCH).total_seconds()
    elif action == 'new':
        print(f"Starting new game with seed: {value}")
        game_environment_module.current_environment = game_environment_module.GameEnvironment(
            value,
            EPOCH
            , None
            )
        game_environment_module.current_environment.generate_default()

        # Spawn player in the first world they encounter
        player_module.current_player = player_module.Player()
        player_module.current_player.spawn_in_environment(game_environment_module.current_environment)

        print("New game started")
        elapsed = 0.0

    gui = OpenGLGui()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_KP_PLUS:
                    player_module.current_player.increase_time_scale()
                elif event.key == pygame.K_KP_MINUS:
                    player_module.current_player.decrease_time_scale()
                elif event.key == pygame.K_F5:
                    Savefile.save()
                elif event.key == pygame.K_F6:
                    update_queue.clear()
                    Savefile.load_last()
                    elapsed = (game_environment_module.current_environment.date_time - EPOCH).total_seconds()
                        # Handle continuous altitude adjustment with numpad +/- (time-scale dependent)
            elif event.type == pygame.VIDEORESIZE:
                size = (max(event.w, MIN_SIZE[0]), max(event.h, MIN_SIZE[1]))
                screen = pygame.display.set_mode(
                    size, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
                )

        dt = clock.tick(FPS) / 1000.0
        elapsed = min(elapsed + dt * player_module.current_player.time_scale, MAX_ELAPSED)
        game_environment_module.current_environment.date_time = EPOCH + timedelta(seconds=elapsed)

        keys = pygame.key.get_pressed()
        player_module.current_player.update_orientation(
            dt * player_module.current_player.time_scale,
            1 if keys[pygame.K_q] else 0,
            1 if keys[pygame.K_e] else 0
        )
        if (keys[pygame.K_a] or keys[pygame.K_d] or keys[pygame.K_w] or keys[pygame.K_s] or
            keys[pygame.K_KP_9] or keys[pygame.K_KP_3]):
            player_module.current_player.update_position(
                dt * player_module.current_player.time_scale,
                1 if keys[pygame.K_d] else (-1 if keys[pygame.K_a] else 0),
                1 if keys[pygame.K_KP_9] else (-1 if keys[pygame.K_KP_3] else 0),
                1 if keys[pygame.K_w] else (-1 if keys[pygame.K_s] else 0)
            )
        if (keys[pygame.K_SPACE]):
            player_module.current_player.ship.laser.fire()
            if (player_module.current_player.ship.laser.hitting_rock):
                player_module.current_player.ship.laser.hitting_rock.increase_temperature(
                    elapsed, game_environment_module.current_environment.date_time
                    )
        elif (player_module.current_player.ship.laser.firing):
            player_module.current_player.ship.laser.cease_fire()

        update_queue.update(game_environment_module.current_environment.date_time)

        gui.draw(screen, fonts, game_environment_module.current_environment, player_module.current_player)
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    print('Starting game.')
    main()
    print('Ending game.')