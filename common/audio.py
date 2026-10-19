"""Sound effects (not music). Game code names an event with `play(name)`; this module does the rest.

The game is in vacuum: only what the pilot hears inside the ship exists here (the cockpit and its dialogs, the ship's systems,
the radio and the alarms), never a sound from space itself. A sound is a WAV in `common/resources/sounds`, made by
`tools/generate_sounds.py` (a file of the same name can replace any of them). SOUNDS gives each one's volume, and whether it
keeps silent while time is compressed above x1: the interface and the alerts do not, the one-shots of the game will.

The same sound is not repeated within MIN_GAP_MS (scrolling or a held key would machine-gun it). Without a sound device, or
without the file, `play` does nothing: sound must never disturb the game."""

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
}

MIN_GAP_MS = 80  # the least time between two plays of the same sound

_loaded: Dict[str, Optional[pygame.mixer.Sound]] = {}  # None for a sound that could not be loaded
_last_played_at: Dict[str, int] = {}


def play(name: str) -> None:
    """Plays the sound `name` (a key of SOUNDS), unless there is no mixer, it was played less than MIN_GAP_MS ago, or it keeps
    silent while time is compressed and it is."""
    spec = SOUNDS[name]
    if not pygame.mixer.get_init():
        return
    now = pygame.time.get_ticks()
    if now - _last_played_at.get(name, -MIN_GAP_MS) < MIN_GAP_MS:
        return
    if spec.silent_when_fast:
        import galaxies.people.player as player_module  # local: the player's module imports this package's users
        player = player_module.current_player
        if player is not None and player.time_scale > player.TIME_SCALE_MIN:
            return
    if name not in _loaded:
        try:
            _loaded[name] = pygame.mixer.Sound(resource_path('sounds', spec.file))
        except (FileNotFoundError, pygame.error) as error:
            logger.warning(f"Sound {spec.file} not available ({error}).")
            _loaded[name] = None
    sound = _loaded[name]
    if sound is not None:
        sound.set_volume(spec.volume)
        sound.play()
        _last_played_at[name] = now
