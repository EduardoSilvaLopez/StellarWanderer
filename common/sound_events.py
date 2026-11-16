"""The sounds the game world asks for, without knowing who plays them.

The universe says what happened (`play('mission_taken')`, `set_loop('laser', True)`); the sound itself belongs to the
presentation. The game layer connects the two once (`connect`); until then, and in the tools, the calls do nothing."""

from __future__ import annotations
from typing import Callable

_sinks: dict[str, Callable] = {}  # 'play' and 'set_loop', once connected


def connect(play: Callable[[str], None], set_loop: Callable[[str, bool], None]) -> None:
    """Sends every sound asked for from now on to `play` (a one-shot) and `set_loop` (a loop, on or off)."""
    _sinks['play'] = play
    _sinks['set_loop'] = set_loop


def play(name: str) -> None:
    """Asks for the one-shot sound `name`."""
    if 'play' in _sinks:
        _sinks['play'](name)


def set_loop(name: str, on: bool) -> None:
    """Asks for the loop `name` to be on or off; may be called every frame."""
    if 'set_loop' in _sinks:
        _sinks['set_loop'](name, on)
