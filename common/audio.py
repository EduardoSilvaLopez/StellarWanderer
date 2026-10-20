"""Sound effects (not music). Game code names an event with `play(name)`; this module does the rest.

The game is in vacuum: only what the pilot hears inside the ship exists here (the cockpit and its dialogs, the ship's systems,
the radio and the alarms), never a sound from space itself. A sound is a WAV in `common/resources/sounds`, made by
`tools/generate_sounds.py` (a file of the same name can replace any of them). SOUNDS gives each one's volume, and whether it
keeps silent while time is compressed above x1: the interface and the alerts do not, the one-shots of the game will.

The same sound is not repeated within MIN_GAP_MS (scrolling or a held key would machine-gun it). Without a sound device, or
without the file, `play` does nothing: sound must never disturb the game.

A loop (the laser, the thrust, the attitude) is switched with `set_loop(name, on)`, which may be called every frame; `stop_loops` ends them all
(a new game, a load, a dialog opening)."""

from __future__ import annotations
from typing import Dict, NamedTuple, Optional
import logging
import pygame

from common.paths import resource_path

logger = logging.getLogger(__name__)


class SoundSpec(NamedTuple):
    file: str
    volume: float  # 0 (silent) to 1
    silent_when_fast: bool  # not played above x1


SOUNDS: Dict[str, SoundSpec] = {
    'ui_open': SoundSpec('ui_open.wav', 0.5, False),  # a dialog opens
    'ui_close': SoundSpec('ui_close.wav', 0.5, False),  # a dialog closes, or Esc or a right-click goes back
    'ui_click': SoundSpec('ui_click.wav', 0.5, False),  # a button or a row is pressed
    'board_open': SoundSpec('board_open.wav', 0.5, False),  # the outpost's message board opens
    'mission_taken': SoundSpec('mission_taken.wav', 0.6, False),
    'mission_delivered': SoundSpec('mission_delivered.wav', 0.6, False),
    'mission_failed': SoundSpec('mission_failed.wav', 0.7, False),  # also when time is compressed: it is an alert
    'notify': SoundSpec('notify.wav', 0.4, False),  # a notification or a warning
    'alert': SoundSpec('alert.wav', 0.7, False),  # a CRITICAL notification
    'radio_open': SoundSpec('radio_open.wav', 0.5, False),  # a message of a conversation over the radio
    'ore_collected': SoundSpec('ore_collected.wav', 0.5, True),
    'mine_placed': SoundSpec('mine_placed.wav', 0.8, True),
    'mine_refused': SoundSpec('mine_refused.wav', 0.5, False),  # instead of the notification's own sound
    'bind': SoundSpec('bind.wav', 0.5, False),  # arriving to a world, instead of the notification's own sound
    'unbind': SoundSpec('unbind.wav', 0.5, False),  # leaving a world, instead of the notification's own sound
    'time_up': SoundSpec('time_up.wav', 0.4, False),
    'time_down': SoundSpec('time_down.wav', 0.4, False),
    'game_over': SoundSpec('game_over.wav', 0.7, False),  # the death message opens with it
    'laser': SoundSpec('laser.wav', 0.3, True),  # loop
    'thrust': SoundSpec('thrust.wav', 0.25, True),  # loop
    'attitude': SoundSpec('thrust.wav', 0.1, True),  # loop: the thrust's sound, softer, for yaw, pitch and roll
}

MIN_GAP_MS = 80  # the least time between two plays of the same sound

_loaded: Dict[str, Optional[pygame.mixer.Sound]] = {}  # None for a sound that could not be loaded
_last_played_at: Dict[str, int] = {}
LOOPS = ('laser', 'thrust', 'attitude')  # the sounds started with set_loop


def _is_fast() -> bool:
    """True while time is compressed above x1."""
    import galaxies.people.player as player_module  # local: the player's module imports this package's users
    player = player_module.current_player
    return player is not None and player.time_scale > player.TIME_SCALE_MIN


def _sound(name: str) -> Optional[pygame.mixer.Sound]:
    """The loaded sound `name`, loading it on first use; None if it could not be loaded."""
    if name not in _loaded:
        try:
            _loaded[name] = pygame.mixer.Sound(resource_path('sounds', SOUNDS[name].file))
        except (FileNotFoundError, pygame.error) as error:
            logger.warning(f"Sound {SOUNDS[name].file} not available ({error}).")
            _loaded[name] = None
    return _loaded[name]


def play(name: str) -> None:
    """Plays the sound `name` (a key of SOUNDS), unless there is no mixer, it was played less than MIN_GAP_MS ago, or it keeps
    silent while time is compressed and it is."""
    spec = SOUNDS[name]
    if not pygame.mixer.get_init():
        return
    now = pygame.time.get_ticks()
    if now - _last_played_at.get(name, -MIN_GAP_MS) < MIN_GAP_MS:
        return
    if spec.silent_when_fast and _is_fast():
        return
    sound = _sound(name)
    if sound is not None:
        sound.set_volume(spec.volume)
        sound.play()
        _last_played_at[name] = now


def set_loop(name: str, on: bool) -> None:
    """Starts (on) or stops the loop `name`; starting a loop that plays, or stopping one that does not, changes nothing. A loop
    that keeps silent while time is compressed does not start then.

    A loop is stopped through its Sound, never through a remembered Channel: the mixer reuses channels, and a stale one may
    already carry another sound."""
    if not pygame.mixer.get_init():
        return
    if on and SOUNDS[name].silent_when_fast and _is_fast():
        on = False
    sound = _sound(name)
    if sound is None:
        return
    if not on:
        sound.stop()
        return
    if sound.get_num_channels() == 0:
        sound.set_volume(SOUNDS[name].volume)
        sound.play(loops=-1)


def stop_loops() -> None:
    """Ends every loop."""
    for name in LOOPS:
        sound = _loaded.get(name)
        if sound is not None:
            sound.stop()
