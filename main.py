"""Stellar Wanderer — first-person cockpit view.

Controls:
    Keypad +   compress time 10x further, up to 1 000 000 s/s
    Keypad -   step back down, no slower than 1 s/s
    W/X        thrust forward/backward
    A/D        thrust left/right
    Numpad 8/2 pitch up/down (unbound only)
    Numpad 4/6 yaw left/right
    Q/E        roll left/right
    S          brake (linear and rotational)
    SPACE      fire the laser
    M          place mine
    Esc        quit
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Tuple
import os
import sys

import pygame
import logging; logger = logging.getLogger(__name__)
from GameLogging import configure_logging
from Graphics.FontCache import FontCache
import GameEnvironment as gem
import Player as player_module
from Persistency.Savefile import Savefile
from Persistency.StartDialog import StartDialog
from Graphics.OpenGLGui import OpenGLGui
from Updating.UpdateQueue import update_queue

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1920, 1080)
MIN_SIZE = (640, 400)
FPS = 60

STAR_COUNT = 260
STAR_SEED = 20270101

# Altitude change control
ALTITUDE_CHANGE_PER_SECOND = 1  # meters per second at time_scale 1
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - gem.GameEnvironment.EPOCH).total_seconds() # datetime tops out at year 9999;
EPOCH = gem.GameEnvironment.EPOCH


def center_window_on_screen(window_title: str, window_size: Tuple[int, int]) -> None:
    """Center a window on the screen. Windows only."""
    if sys.platform != 'win32':
        return

    try:
        import ctypes
        import ctypes.wintypes as wintypes

        # Get window handle by title
        hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
        if not hwnd:
            return

        # Get screen dimensions
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)

        # Calculate center position
        window_width, window_height = window_size
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        # Move window (SWP_NOZORDER = 0x0004)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, window_width, window_height, 0x0004)
    except Exception as e:
        logger.debug(f"Failed to center window: {e}")


def main() -> None:
    configure_logging()
    pygame.init()

    # Create temporary display for startup dialog
    temp_screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption(WINDOW_TITLE)

    # Show startup dialog to load or create a new game
    dialog = StartDialog(surface=temp_screen)
    choice = dialog.run()
    if choice is None:
        pygame.quit()
        return

    logger.info("Game started.")
    # Now create the main OpenGL display
    screen = pygame.display.set_mode(
        WINDOW_SIZE, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
    )
    pygame.display.set_caption(WINDOW_TITLE)
    center_window_on_screen(WINDOW_TITLE, WINDOW_SIZE)
    clock = pygame.time.Clock()

    fonts = FontCache()
    elapsed = 0.0  # seconds of ship time since EPOCH

    action, value = choice

    if action == 'load':
        # Load existing savefile
        Savefile.load_from_file(value)
        elapsed = (gem.current_environment.date_time - EPOCH).total_seconds()
    elif action == 'new':
        logger.info(f"New game with seed: {value}")
        gem.current_environment = gem.GameEnvironment(
            value,
            EPOCH
            , None
            )
        gem.current_environment.generate_default()

        # Spawn player in the first world they encounter
        player_module.current_player = player_module.Player()
        player_module.current_player.spawn_in_environment(gem.current_environment)

        logger.debug("New game created.")
        elapsed = 0.0
    gui = OpenGLGui()
    
    running = True
    player_module.current_player.ship.set_notification(f"Welcome, {player_module.current_player.get_title()} Pilot.")
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
                    elapsed = (gem.current_environment.date_time - EPOCH).total_seconds()
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_m:
                    player_module.current_player.ship.set_mine_pressed()
            elif event.type == pygame.VIDEORESIZE:
                size = (max(event.w, MIN_SIZE[0]), max(event.h, MIN_SIZE[1]))
                screen = pygame.display.set_mode(
                    size, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
                )

        dt = clock.tick(FPS) / 1000.0
        elapsed = min(elapsed + dt * player_module.current_player.time_scale, MAX_ELAPSED)
        gem.current_environment.date_time = EPOCH + timedelta(seconds=elapsed)

        keys = pygame.key.get_pressed()
        player = player_module.current_player

        # Yaw: Numpad 4 (left) and 6 (right)
        player.update_yaw(
            dt * player.time_scale,
            1 if keys[pygame.K_KP_4] else 0,
            1 if keys[pygame.K_KP_6] else 0,
            keys[pygame.K_s]
        )

        # Pitch: Numpad 8 (up) and 2 (down), only while unbound
        player.update_pitch(
            dt * player.time_scale,
            1 if (keys[pygame.K_KP_2] and not player.is_bound) else 0,
            1 if (keys[pygame.K_KP_8] and not player.is_bound) else 0,
            keys[pygame.K_s]
        )

        # Roll: Q (left) and E (right), only while unbound
        player.update_roll(
            dt * player.time_scale,
            1 if keys[pygame.K_q] else 0,
            1 if keys[pygame.K_e] else 0,
            keys[pygame.K_s]
        )

        # Always update position, even with no thrust keys held: W/A/D/X/KP_8/KP_2 now
        # control acceleration in all axes, so the ship keeps drifting on its
        # last velocity until thrust (or boundary clamp) changes it. Holding S
        # brakes instead, overriding all thrust keys in all three axes and stopping
        # all rotations (yaw, pitch, roll).
        player.update_position_and_velocity(
            dt * player.time_scale,
            1 if keys[pygame.K_d] else (-1 if keys[pygame.K_a] else 0),
            (1 if keys[pygame.K_KP_8] else (-1 if keys[pygame.K_KP_2] else 0)) if player.is_bound else 0,
            1 if keys[pygame.K_w] else (-1 if keys[pygame.K_x] else 0),
            keys[pygame.K_s]
        )
        player_module.current_player.ship.laser.update_aim()
        if (keys[pygame.K_SPACE]):
            player_module.current_player.ship.laser.fire()
            if (player_module.current_player.ship.laser.hitting_rock):
                player_module.current_player.ship.laser.hitting_rock.increase_temperature(
                    dt * player_module.current_player.time_scale, gem.current_environment.date_time
                    )
        elif (player_module.current_player.ship.laser.firing):
            player_module.current_player.ship.laser.cease_fire()

        update_queue.update(gem.current_environment.date_time)

        gui.draw(screen, fonts, gem.current_environment, player_module.current_player)
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    logger.debug('Starting application.')
    main()
    logger.debug('Ending application.')