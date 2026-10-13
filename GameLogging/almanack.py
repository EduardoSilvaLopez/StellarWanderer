"""Writes the galaxy's almanack (Logs/almanack.galaxy.md) when a game starts or loads."""

from __future__ import annotations
from typing import TYPE_CHECKING
import os
import threading

from .constants import LOG_DIR, ALMANACK_FILE_NAME
from paths import data_path

if TYPE_CHECKING:
    from Galaxies.galaxy import Galaxy


def write_almanack_async(galaxy: Galaxy) -> None:
    '''Writes the galaxy's almanack in the background, replacing any previous file. Fire and forget.

    The text is built here, in the calling thread, from the objects as they are now (cheap, no I/O),
    so the background thread never touches game objects; only the disk write is left to it.
    Every exception is ignored: the almanack is a diagnostic aid and must never disturb the game.'''
    try:
        text: str = galaxy.almanack()
        threading.Thread(target=_write_file, args=(text,), name='almanack', daemon=True).start()
    except Exception:
        pass


def _write_file(text: str) -> None:
    try:
        os.makedirs(data_path(LOG_DIR), exist_ok=True)
        with open(data_path(LOG_DIR, ALMANACK_FILE_NAME), 'w', encoding='utf-8') as file:
            file.write(text)
    except Exception:
        pass
