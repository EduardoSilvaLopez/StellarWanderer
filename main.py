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
    SPACE      switch the scanner beam on (heats a targeted rock, collects ore from a targeted mine)
    M          place mine
    Esc        open the starting dialog (new game, load, exit game); Esc again resumes.
               Game time is paused while a dialog is open.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Tuple
import os
import sys

# The compiled bytecode goes to temp/pycache, not next to each source file. Set before the project's imports.
if not getattr(sys, 'frozen', False):
    sys.pycache_prefix = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp', 'pycache')

import pygame
import logging
from common.game_logging import configure_logging, write_almanack_async
from graphics.font_cache import FontCache
import game_environment as gem
import knowledge
import galaxies.people.player as player_module
from common.savefile import Savefile
from common.dialogs import (
    Dialog, DialogResult, KnownSystemsDialog, Message, MessageDialog, PeopleDialog, StartingDialog, confirm,
    next_pending_message, run_in_window, show_message
)
from galaxies.mission_board import MissionBoard
from graphics.opengl_gui import OpenGLGui
from graphics.instruments.cockpit_buttons import SYSTEMS, CockpitButtons
from graphics.instruments.world_map import WorldMap
from common.updating import update_queue

logger = logging.getLogger(__name__)

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1920, 1080)
MIN_SIZE = (640, 400)
FPS = 60

# Altitude change control
ALTITUDE_CHANGE_PER_SECOND = 1  # meters per second at time_scale 1
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - gem.GameEnvironment.EPOCH).total_seconds()  # datetime tops out at year 9999;
EPOCH = gem.GameEnvironment.EPOCH


def center_window_on_screen(window_title: str, window_size: Tuple[int, int]) -> None:
    """Center a window on the screen. Windows only."""
    if sys.platform != 'win32':
        return

    try:
        import ctypes

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
        knowledge.current_knowledge = knowledge.Knowledge()  # before the environment: its systems add to it
        gem.current_environment = gem.GameEnvironment(value, EPOCH, None, None)
        gem.current_environment.generate_default()

        # Spawn player in the first world they encounter
        player_module.current_player = player_module.Player()
        player_module.current_player.spawn_in_environment(gem.current_environment)

        logger.debug("New game created.")
        elapsed = 0.0
    write_almanack_async(gem.current_environment.galaxy)
    player = player_module.current_player
    player.ship.notification.set(f"Welcome, {player.get_title()} Pilot.")
    if action == 'new':
        fixed_world = gem.current_environment.fixed_world
        planet = fixed_world.parent_planet.name
        moon = fixed_world.name
        show_message(Message(
            title=f"Welcome, {player.get_title()} Pilot!",
            text=(
                "Speaker Xi, the famous pilot trainer, has closed the communication with his last message. "
                "Now he will train other Citizen Pilots. You are ready.\n\n"
                f"{moon} extends in front of you. Your task is to plant mines in this ore-rich moon and bring it "
                f"to the outpost in the planet, {planet}. The better you work, the more your reputation will increase.\n\n"
                "The State of \"Those-Who-Share\" will provide you everything you need there, as they provided you "
                "this ship as long as you need it to perform your tasks for the Community.\n\n"
                "You trained years for this. Now it is the time to decide what you do with your new freedom."
            ),
            buttons=["Understood"],
        ))
    return elapsed


def open_starting_dialog(
        screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock,
        game_running: bool = True
        ) -> Tuple[DialogResult, pygame.Surface]:
    """Show the starting dialog above the frozen game (see run_modal_dialog). With game_running False (after a death)
    there is no resuming: only a new game, a load, or exit."""
    return run_modal_dialog(StartingDialog(game_running=game_running), screen, gui, fonts, clock)


def show_pending_messages(
        screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock
        ) -> Tuple[bool, pygame.Surface]:
    """Show the queued messages in order (show_message), each answer going to its callback.
    Returns (keep running, window): closing the window while a message is open stops the game."""
    pending_message = next_pending_message()
    while pending_message is not None:
        result, screen = run_modal_dialog(MessageDialog(pending_message.message), screen, gui, fonts, clock)
        if result[0] == 'exit':
            return False, screen
        if pending_message.on_result is not None:
            pending_message.on_result(result[1])  # the pressed button's index, None for Esc
        pending_message = next_pending_message()
    return True, screen


def write_save(name: str) -> None:
    """Save the game as `name`; a file that cannot be written is reported in a message."""
    try:
        Savefile.save_as(name)
    except OSError as error:
        show_message(Message(
            title='SAVE FAILED',
            text=f"The game could not be saved as '{name}': {error.strerror or error}.",
            buttons=["OK"]
        ))


def save_from_menu(
        name: str, screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock
        ) -> Tuple[bool, pygame.Surface]:
    """Save from the starting dialog. '' is the default name, which is not saved over an existing file (the same
    game second). A name in use asks first; Overwrite saves, Cancel does nothing. Returns (keep running, window)."""
    if not name:
        if not Savefile.exists(Savefile.default_name()):
            write_save(Savefile.default_name())
    elif Savefile.exists(name):
        confirm(
            title='OVERWRITE SAVE?',
            text=f"A save named '{name}' already exists. Saving will overwrite it.",
            confirm_label='Overwrite',
            on_confirm=lambda: write_save(name),
        )
    else:
        write_save(name)
    return show_pending_messages(screen, gui, fonts, clock)


def open_start_menu(
        screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock,
        elapsed: float, game_running: bool
        ) -> Tuple[bool, pygame.Surface, float]:
    """The starting dialog, and the game it chooses. Returns (keep running, window, elapsed ship seconds)."""
    result, screen = open_starting_dialog(screen, gui, fonts, clock, game_running)
    if result[0] == 'exit':
        return False, screen, elapsed
    if result[0] == 'save':
        keep_running, screen = save_from_menu(result[1], screen, gui, fonts, clock)
        return keep_running, screen, elapsed
    if result[0] in ('new', 'load'):
        elapsed = start_game(*result)
    return True, screen, elapsed


def run_modal_dialog(
        dialog: Dialog, screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock
        ) -> Tuple[DialogResult, pygame.Surface]:
    """Show `dialog` above the frozen game until it returns a result.

    Game time is paused for as long as this runs: nothing that advances it (elapsed, date and
    time, movement, scanner, the update queue) is called here, the game frame behind the dialog
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
        running, screen = show_pending_messages(screen, gui, fonts, clock)
        if not running:
            break

        # A death: once its message is closed, the game is over and the starting dialog takes over.
        if player_module.current_player.is_dead:
            running, screen, elapsed = open_start_menu(screen, gui, fonts, clock, elapsed, game_running=False)
            continue

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running, screen, elapsed = open_start_menu(screen, gui, fonts, clock, elapsed, game_running=True)
                elif event.key == pygame.K_KP_PLUS:
                    player_module.current_player.increase_time_scale()
                elif event.key == pygame.K_KP_MINUS:
                    player_module.current_player.decrease_time_scale()
                elif event.key == pygame.K_KP5:  # the message board of the outpost in the scanner
                    outpost = player_module.current_player.ship.scanner.targeted_outpost
                    if outpost is not None and MissionBoard.is_available(player_module.current_player):
                        outpost.open_mission_board()
                elif event.key == pygame.K_F5:
                    Savefile.save()
                elif event.key == pygame.K_F6:
                    update_queue.clear()
                    Savefile.load_last()
                    write_almanack_async(gem.current_environment.galaxy)
                    elapsed = (gem.current_environment.date_time - EPOCH).total_seconds()
                elif event.key == pygame.K_TAB:  # cycles the target (only outside every fixed zone); Shift+Tab goes back
                    step = -1 if event.mod & pygame.KMOD_SHIFT else 1
                    gem.current_environment.cycle_targeted_body(step, player_module.current_player.ship.position.as_vector())
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_m:
                    player_module.current_player.ship.set_mine_pressed()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and CockpitButtons.hit(event.pos) is not None:
                dialog = KnownSystemsDialog() if CockpitButtons.hit(event.pos) == SYSTEMS else PeopleDialog()
                result, screen = run_modal_dialog(dialog, screen, gui, fonts, clock)
                running = result[0] != 'exit'
            elif event.type == pygame.MOUSEWHEEL:
                if player_module.current_player.ship.is_bound:  # the world map is only shown while bound
                    WorldMap.zoom(event.y)  # zooms the world map, if the mouse is over it
            elif event.type == pygame.VIDEORESIZE:
                screen = resize_window(event.w, event.h)

        # The world map zooms while the mouse is over it, and drags with the left button (polled once per frame).
        focused = pygame.mouse.get_focused()
        left_pressed = focused and pygame.mouse.get_pressed()[0] and player_module.current_player.ship.is_bound
        WorldMap.set_mouse(pygame.mouse.get_pos(), focused, left_pressed)

        dt = clock.tick(FPS) / 1000.0

        player = player_module.current_player
        ship = player.ship
        delta_game_seconds = dt * player.time_scale
        elapsed = min(elapsed + delta_game_seconds, MAX_ELAPSED)
        gem.current_environment.date_time = EPOCH + timedelta(seconds=elapsed)

        keys = pygame.key.get_pressed()

        if player.time_scale == 1:  # Yaw, pitch, scale disabled for > 1.
            # Yaw: Numpad 4 (left) and 6 (right)
            ship.attitude.update_yaw(
                delta_game_seconds,
                1 if keys[pygame.K_KP_4] else 0,
                1 if keys[pygame.K_KP_6] else 0,
                keys[pygame.K_s]
            )

            # Pitch: Numpad 2 (nose up) and 8 (nose down)
            ship.attitude.update_pitch(
                delta_game_seconds,
                1 if keys[pygame.K_KP_2] else 0,
                1 if keys[pygame.K_KP_8] else 0,
                keys[pygame.K_s]
            )

            # Roll: E (right) and Q (left)
            ship.attitude.update_roll(
                delta_game_seconds,
                1 if keys[pygame.K_e] else 0,
                1 if keys[pygame.K_q] else 0,
                keys[pygame.K_s]
            )
        else:  # reducing them automatically.
            ship.attitude.update_yaw(delta_game_seconds, 0, 0, 1)
            ship.attitude.update_pitch(delta_game_seconds, 0, 0, 1)
            ship.attitude.update_roll(delta_game_seconds, 0, 0, 1)

        # Always update position, even with no thrust keys held: W/A/D/X/KP_8/KP_2 now
        # control acceleration in all axes, so the ship keeps drifting on its
        # last velocity until thrust (or boundary clamp) changes it. Holding S
        # brakes instead, overriding all thrust keys in all three axes and stopping
        # all rotations (yaw, pitch, roll).
        ship.navigation.update_position_and_velocity(
            delta_game_seconds,
            1 if keys[pygame.K_d] else (-1 if keys[pygame.K_a] else 0),
            (1 if keys[pygame.K_KP_8] else (-1 if keys[pygame.K_KP_2] else 0)) if ship.is_bound else 0,
            1 if keys[pygame.K_w] else (-1 if keys[pygame.K_x] else 0),
            keys[pygame.K_s]
        )
        ship.scanner.update_target()
        if keys[pygame.K_SPACE]:
            ship.scanner.activate(delta_game_seconds)
        elif ship.laser.firing:
            ship.scanner.deactivate()

        update_queue.update(gem.current_environment.date_time)

        gui.draw(screen, fonts, gem.current_environment, player_module.current_player)
        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    logger.debug('----------------------------------------------------------------------------------------------------')
    logger.debug('Starting application.')
    logger.debug('----------------------------------------------------------------------------------------------------')
    main()
    logger.debug('Ending application.')
