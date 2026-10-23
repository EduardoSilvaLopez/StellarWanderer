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
    SPACE      switch the scanner beam on (heats a targeted rock, collects ore from a targeted mine); on a targeted
               outpost, enter it (the ship must be landed): a screen over the whole window, the other state of the
               game, where it goes on; its Leave button leaves it
    M          place mine
    O          show or hide the orbit of the targeted body
    Esc       open the starting dialog (new game, load, save, exit game), in the cockpit and inside an outpost; Esc
               again resumes. Game time is paused while a dialog is open.
"""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from functools import partial
from typing import Optional, Tuple
import os
import sys

from galaxies.politics.political_entity import THOSE_WHO_SHARE

# The compiled bytecode goes to temp/pycache, not next to each source file. Set before the project's imports.
if not getattr(sys, 'frozen', False):
    sys.pycache_prefix = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp', 'pycache')

import pygame
import logging
from common.game_logging import configure_logging
from graphics.font_cache import FontCache
import game_environment as gem
from galaxies.people import knowledge
from common import audio
from common.paths import resource_path
import galaxies.people.player as player_module
from common.savefile import Savefile
from common.dialogs import (
    Dialog, DialogResult, KnownSystemsDialog, Message, MessageDialog, KnownPeopleDialog, ShipSpecificationsDialog,
    StartingDialog, PilotIdentityDialog, confirm,
    PendingMissionsDialog, OutpostScreenDialog, next_pending_message, run_in_window, show_message
)
from galaxies.outpost import Outpost
from spaceships.long_distance_advice import LongDistanceAdvisor
from graphics.opengl_gui import OpenGLGui
from graphics.orbit_path import OrbitPath
from graphics.instruments.clock import Clock
from graphics.instruments.cockpit_buttons import MISSIONS, SHIP, SYSTEMS, CockpitButtons
from graphics.instruments.world_map import WorldMap
from common.updating import update_queue

logger = logging.getLogger(__name__)

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1920, 1080)
WINDOW_ICON_SIZE = (32, 32)  # the installer's icon (presentation/game_icon.png), reduced for the title bar and taskbar
MIN_SIZE = (640, 400)
FPS = 60

# datetime tops out at year 9999
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - gem.GameEnvironment.EPOCH).total_seconds()
EPOCH = gem.GameEnvironment.EPOCH
# the keyboard while the outpost screen is open: no key is held, so the ship is not flown
NO_KEYS = defaultdict(bool)


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
    audio.stop_loops()
    audio.play(dialog.OPEN_SOUND)

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
                 top_layer=dialog.compose_overlay(pygame.display.get_window_size()))
        pygame.display.flip()
        clock.tick(FPS)
    clock.tick()  # restart the frame timer, so the time spent in the dialog is not part of the next dt
    audio.play(dialog.CLOSE_SOUND)
    return result, screen


def draw_outpost_view(outpost_screen: OutpostScreenDialog, fonts: FontCache, size: Tuple[int, int]) -> pygame.Surface:
    """What the window shows while the pilot is inside an outpost: its screen, with the clock over its name, on the left
    (OutpostScreenDialog.clock_topleft). The gui draws it (OpenGLGui.full_screen_source), and the dialogs over it."""
    layer = outpost_screen.compose_overlay(size)
    Clock.draw(layer, fonts, gem.current_environment.date_time, player_module.current_player.time_scale, *size,
               topleft=outpost_screen.clock_topleft(size))
    return layer


def sync_outpost_screen(
        player: player_module.Player, outpost_screen: Optional[OutpostScreenDialog], gui: OpenGLGui, fonts: FontCache
        ) -> Optional[OutpostScreenDialog]:
    """The screen of the outpost the pilot is inside (`Player.inside`), or None in the cockpit: it is made when they
    have just gone in, or a load or a new game has put them somewhere else, and the gui is told to draw it in place of
    the cockpit. Call it after anything that may change where the pilot is."""
    inside = player.inside
    if inside is None:
        outpost_screen = None
    elif outpost_screen is None or outpost_screen.outpost is not inside:
        outpost_screen = OutpostScreenDialog(inside)
    gui.full_screen_source = None if outpost_screen is None else partial(draw_outpost_view, outpost_screen, fonts)
    return outpost_screen


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


def manage_missions(
        screen: pygame.Surface, gui: OpenGLGui, fonts: FontCache, clock: pygame.time.Clock
        ) -> Tuple[bool, pygame.Surface]:
    """The missions of the pilot (the cockpit's MISSIONS button). Forgetting the asteroid of a finished mission asks
    first (its message is shown, then the missions open again). Returns (keep running, window)."""
    while True:
        result, screen = run_modal_dialog(
            PendingMissionsDialog(player_module.current_player.missions), screen, gui, fonts, clock)
        if result[0] != 'forget':
            return result[0] != 'exit', screen
        mission = result[1]
        confirm(
            title='FORGET ASTEROID?',
            text='Forget this asteroid?',
            confirm_label='Forget',
            on_confirm=mission.forget,
        )
        keep_running, screen = show_pending_messages(screen, gui, fonts, clock)
        if not keep_running:
            return False, screen


def start_game(action: str, value: object) -> float:
    """Replace the current game with a new one ('new', seed) or a saved one ('load', path).

    Returns the elapsed ship seconds since EPOCH of the game that starts."""
    update_queue.clear()
    audio.stop_loops()
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
    player = player_module.current_player
    player.ship.notification.set(f"Welcome, {player.get_title()} Pilot.")
    return elapsed


def show_welcome(player: player_module.Player) -> None:
    """Xi's farewell message, queued for a new game once the pilot has said who they are (PilotIdentityDialog)."""
    fixed_world = gem.current_environment.fixed_world
    planet = fixed_world.parent_planet.name
    moon = fixed_world.name
    xis_title = THOSE_WHO_SHARE.title_for(1500)
    show_message(Message(
        title=f"Welcome, {player.get_title()} Pilot!",
        text=(
            f"{xis_title} Xi, the famous pilot trainer, has closed the communication with his last message."
            " Happy New Year indeed. Now he will train other Pioneer Pilots. You are ready."
            f"\n\n{moon} extends in front of you. Your main task is to find the best ore-rich rocks, melt them"
            f" and install those precious mines on the resulting fields. Then wait, days if needed, and collect"
            f" the ore, bringing it to the outpost in the planet, {planet}. The better you work, the more your"
            " reputation will rise."
            "\n\nThe State of \"Those-Who-Share\" will provide everything you need there, as they provided"
            " you this ship, as long as you need it."
            "\n\nYou trained years for this."
            "\n\nNow it is the time to decide what you do with your new freedom."
        ),
        buttons=["Understood"],
    ))


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
    game day). A name in use asks first; Overwrite saves, Cancel does nothing. Returns (keep running, window)."""
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
    # Above the frozen game. With game_running False (after a death) there is no resuming: only a new game, a load,
    # or exit.
    result, screen = run_modal_dialog(StartingDialog(game_running=game_running), screen, gui, fonts, clock)
    if result[0] == 'exit':
        return False, screen, elapsed
    if result[0] == 'save':
        keep_running, screen = save_from_menu(result[1], screen, gui, fonts, clock)
        return keep_running, screen, elapsed
    if result[0] in ('new', 'load'):
        elapsed = start_game(*result)
    return True, screen, elapsed


def main() -> None:
    configure_logging()
    pygame.init()
    pygame.display.set_icon(pygame.transform.smoothscale(
        pygame.image.load(resource_path('presentation', 'game_icon.png')), WINDOW_ICON_SIZE))

    # Create temporary display for the starting dialog
    temp_screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption(WINDOW_TITLE)

    # Show the starting dialog to load or create a new game, or to exit
    choice = run_in_window(StartingDialog(game_running=False), temp_screen)
    if choice is None or choice[0] == 'exit':
        pygame.quit()
        return

    logger.info("================================================================================")
    logger.info("Game started.")
    logger.info("================================================================================")
    # Now create the main OpenGL display
    screen = resize_window(*WINDOW_SIZE)
    pygame.display.set_caption(WINDOW_TITLE)
    center_window_on_screen(WINDOW_TITLE, WINDOW_SIZE)
    clock = pygame.time.Clock()

    fonts = FontCache()
    elapsed = start_game(*choice)  # seconds of ship time since EPOCH
    gui = OpenGLGui()

    running = True
    outpost_screen: Optional[OutpostScreenDialog] = None  # the inside of an outpost, while it is open
    while running:
        # Messages asked for by game code (show_message) open here, at the start of a frame.
        running, screen = show_pending_messages(screen, gui, fonts, clock)
        if not running:
            break

        # A new game or a load replaces the pilot (start_game), so it is read again each frame and after those.
        player = player_module.current_player

        # A new game: the pilot says who they are first, then Xi's message follows (shown at the next frame's start).
        if not player.first_name:
            result, screen = run_modal_dialog(PilotIdentityDialog(), screen, gui, fonts, clock)
            if result[0] == 'exit':
                break
            player.first_name, player.surname, player.gender = result[1]
            show_welcome(player)
            continue

        # A death: once its message is closed, the game is over and the starting dialog takes over.
        if player.is_dead:
            running, screen, elapsed = open_start_menu(screen, gui, fonts, clock, elapsed, game_running=False)
            continue

        outpost_screen = sync_outpost_screen(player, outpost_screen, gui, fonts)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # the time scale, the save and the load work in the outpost screen too
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_KP_PLUS:
                player.increase_time_scale()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_KP_MINUS:
                player.decrease_time_scale()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F5:
                Savefile.save()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F6:
                audio.stop_loops()
                Savefile.load_last()
                player = player_module.current_player  # a load may put the pilot inside an outpost (synced below)
                elapsed = (gem.current_environment.date_time - EPOCH).total_seconds()
            # the starting dialog opens in both states of the game: in the cockpit, and inside an outpost
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running, screen, elapsed = open_start_menu(screen, gui, fonts, clock, elapsed, game_running=True)
                player = player_module.current_player
            # while the pilot is inside an outpost, its screen takes the events
            elif outpost_screen is not None:
                if event.type == pygame.VIDEORESIZE:
                    screen = resize_window(event.w, event.h)
                elif (result := outpost_screen.handle_event(event)) is not None:
                    running = result[0] != 'exit'
                    if result[0] == 'close':  # the Leave button: the pilot is back in the cockpit, which takes time too
                        leaving_seconds = outpost_screen.outpost.leave(player.ship, gem.current_environment.date_time)
                        player.leave_outpost()
                        audio.play(OutpostScreenDialog.CLOSE_SOUND)
                        elapsed = min(elapsed + leaving_seconds, MAX_ELAPSED)
            elif event.type == pygame.KEYDOWN:
                # the inside of the outpost in the scanner: the other state of the game (see Player.inside)
                if event.key == pygame.K_SPACE:
                    ship = player.ship
                    outpost = ship.scanner.targeted_outpost
                    if outpost is not None and not ship.navigation.is_landed():
                        ship.notification.set(f"[Com. Officer] Land the ship first, {player.get_title()}.")
                    elif outpost is not None:
                        player.enter_outpost(outpost)
                        elapsed = min(elapsed + Outpost.TIME_TO_ENTER, MAX_ELAPSED)  # going in takes time
                        audio.play(OutpostScreenDialog.OPEN_SOUND)
                elif event.key == pygame.K_o:  # shows or hides the orbit of the targeted body (on at the start)
                    OrbitPath.shown = not OrbitPath.shown
                # cycles the target (only outside every fixed zone); Shift+Tab goes back
                elif event.key == pygame.K_TAB:
                    step = -1 if event.mod & pygame.KMOD_SHIFT else 1
                    gem.current_environment.cycle_targeted_body(step, player.ship.position.as_vector())
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_m:
                    player.ship.place_mine()
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and (pressed := CockpitButtons.hit(event.pos)) is not None):
                if pressed == MISSIONS:
                    running, screen = manage_missions(screen, gui, fonts, clock)
                    continue
                if pressed == SHIP:
                    dialog = ShipSpecificationsDialog(player.ship)
                else:
                    dialog = KnownSystemsDialog() if pressed == SYSTEMS else KnownPeopleDialog()
                result, screen = run_modal_dialog(dialog, screen, gui, fonts, clock)
                running = result[0] != 'exit'
            elif event.type == pygame.MOUSEWHEEL:
                if player.ship.is_bound:  # the world map is only shown while bound
                    WorldMap.zoom(event.y)  # zooms the world map, if the mouse is over it
            elif event.type == pygame.VIDEORESIZE:
                screen = resize_window(event.w, event.h)

        outpost_screen = sync_outpost_screen(player, outpost_screen, gui, fonts)  # the events may have moved the pilot

        # The world map zooms while the mouse is over it, and drags with the left button (polled once per frame).
        focused = pygame.mouse.get_focused()
        left_pressed = focused and pygame.mouse.get_pressed()[0] and player.ship.is_bound
        WorldMap.set_mouse(pygame.mouse.get_pos(), focused, left_pressed)

        dt = clock.tick(FPS) / 1000.0

        ship = player.ship
        delta_game_seconds = dt * player.time_scale
        elapsed = min(elapsed + delta_game_seconds, MAX_ELAPSED)
        gem.current_environment.date_time = EPOCH + timedelta(seconds=elapsed)

        keys = pygame.key.get_pressed() if player.inside is None else NO_KEYS

        if player.time_scale == 1:  # Yaw, pitch, roll only at x1: disabled when faster.
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
        # reducing them automatically, only the rates that are not zero (a brake costs energy only while it acts).
        else:
            if ship.attitude.yaw_rate:
                ship.attitude.update_yaw(delta_game_seconds, 0, 0, 1)
            if ship.attitude.pitch_rate:
                ship.attitude.update_pitch(delta_game_seconds, 0, 0, 1)
            if ship.attitude.roll_rate:
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
        thrusting = (
            keys[pygame.K_w] or keys[pygame.K_x] or keys[pygame.K_a] or keys[pygame.K_d]
            or (ship.is_bound and (keys[pygame.K_KP_8] or keys[pygame.K_KP_2]))
            or (keys[pygame.K_s] and ship.navigation.has_motion_to_brake()))
        # the hull's hum: a thrust key held, or the brake while there is motion to brake
        audio.set_loop('thrust', thrusting)
        rotating = player.time_scale == 1 and (
            keys[pygame.K_KP_4] or keys[pygame.K_KP_6] or keys[pygame.K_e] or keys[pygame.K_q]
            or (not ship.is_bound and (keys[pygame.K_KP_2] or keys[pygame.K_KP_8])))
        # the same hum, softer: yaw, pitch (numpad 2/8 thrust while bound) or roll key held
        audio.set_loop('attitude', rotating)
        ship.scanner.update_target()
        if keys[pygame.K_SPACE]:
            ship.scanner.activate(delta_game_seconds)
        else:
            ship.scanner.release()  # SPACE is up: a scanned rock is announced again on the next press
            if ship.laser.firing:
                ship.scanner.deactivate()

        update_queue.update(gem.current_environment.date_time)
        LongDistanceAdvisor.update(player, gem.current_environment)

        gui.draw(screen, fonts, gem.current_environment, player)  # the outpost screen, if the pilot is inside one
        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
