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
    Esc        open the starting dialog (new game, load, exit game); Esc again resumes.
               Game time is paused while a dialog is open.
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
from Dialogs import (
    Dialog, DialogResult, MessageDialog, StartingDialog, next_pending_message, run_in_window, show_message
)
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


def resize_window(width: int, height: int) -> pygame.Surface:
    """Re-create the OpenGL window at the requested size (never below MIN_SIZE)."""
    size = (max(width, MIN_SIZE[0]), max(height, MIN_SIZE[1]))
    return pygame.display.set_mode(size, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)


def start_game(action: str, value: object) -> float:
    """Replace the current game with a new one ('new', seed) or a saved one ('load', path).

    Returns the elapsed ship seconds since EPOCH of the game that starts."""
    update_queue.clear()
    if action == 'load':
        Savefile.load_from_file(value)
        elapsed = (gem.current_environment.date_time - EPOCH).total_seconds()
    else:
        logger.info(f"New game with seed: {value}")
        gem.current_environment = gem.GameEnvironment(value, EPOCH, None)
        gem.current_environment.generate_default()

        # Spawn player in the first world they encounter
        player_module.current_player = player_module.Player()
        player_module.current_player.spawn_in_environment(gem.current_environment)

        logger.debug("New game created.")
        elapsed = 0.0
    player = player_module.current_player
    player.ship.set_notification(f"Welcome, {player.get_title()} Pilot.")
    if action == 'new':
        show_message(
            'welcome',
            pilot_title=player.get_title(),
            world=gem.current_environment.nearest_world.name,
            system=gem.current_environment.nearest_system.name,
        )
    return elapsed


def open_starting_dialog(
        screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock
        ) -> Tuple[DialogResult, pygame.Surface]:
    """Show the starting dialog above the frozen game (see run_modal_dialog)."""
    return run_modal_dialog(StartingDialog(game_running=True), screen, gui, fonts, clock)


def run_modal_dialog(
        dialog: Dialog, screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock
        ) -> Tuple[DialogResult, pygame.Surface]:
    """Show `dialog` above the frozen game until it returns a result.

    Game time is paused for as long as this runs: nothing that advances it (elapsed, date and
    time, movement, laser, the update queue) is called here, the game frame behind the dialog
    is just re-rendered unchanged. Returns the result and the (possibly resized) window."""
    player = player_module.current_player
    if player.ship.laser.firing:
        player.ship.laser.cease_fire()

    result = None
    while result is None:
        for event in pygame.event.get():
            if event.type == pygame.VIDEORESIZE:
                screen = resize_window(event.w, event.h)
                continue
            result = dialog.handle_event(dialog.localize_event(event, pygame.display.get_window_size()))
            if result is not None:
                break
        gui.draw(screen, fonts, gem.current_environment, player,
                 dialog_surface=dialog.compose_overlay(pygame.display.get_window_size()))
        pygame.display.flip()
        clock.tick(FPS)
    clock.tick()  # restart the frame timer, so the time spent in the dialog is not part of the next dt
    return result, screen


def main() -> None:
    configure_logging()
    pygame.init()

    # Create temporary display for the starting dialog
    temp_screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption(WINDOW_TITLE)

    # Show the starting dialog to load or create a new game, or to exit
    choice = run_in_window(StartingDialog(game_running=False), temp_screen)
    if choice is None or choice[0] == 'exit':
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
    elapsed = start_game(*choice)  # seconds of ship time since EPOCH
    gui = OpenGLGui()

    running = True
    while running:
        # Messages asked for by game code (show_message) open here, at the start of a frame.
        pending_message = next_pending_message()
        while pending_message is not None and running:
            key, values = pending_message
            result, screen = run_modal_dialog(MessageDialog(key, values), screen, gui, fonts, clock)
            if result[0] == 'exit':
                running = False
            pending_message = next_pending_message()
        if not running:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    result, screen = open_starting_dialog(screen, gui, fonts, clock)
                    if result[0] == 'exit':
                        running = False
                    elif result[0] in ('new', 'load'):
                        elapsed = start_game(*result)
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
                screen = resize_window(event.w, event.h)

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