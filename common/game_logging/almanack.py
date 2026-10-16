"""Writes the almanacks in the Logs folder (temp/Logs from source): the galaxy's (almanack.galaxy.md, at game start or load) and the people's
(almanack.people.md, blank at game start or load, then one entry per person as each is created).

The text is always built in the calling thread, from the objects as they are now (cheap, no I/O), so the
background thread never touches game objects. Every exception is ignored: the almanacks are a diagnostic aid and
must never disturb the game."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import os
import queue
import threading

from .constants import LOG_DIR, ALMANACK_FILE_NAME, ALMANACK_PEOPLE_FILE_NAME
from common.paths import data_path

if TYPE_CHECKING:
    from galaxies.galaxy import Galaxy
    from galaxies.people.person import Person

# One worker does every write, in the order they were asked for, so a reset can never overtake the entries that
# follow it. It is a daemon thread: it never keeps the game from closing.
_jobs: queue.Queue = queue.Queue()
_worker_lock = threading.Lock()
_worker: Optional[threading.Thread] = None


def _submit(file_name: str, text: str, append: bool) -> None:
    global _worker
    _jobs.put((file_name, text, append))
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, name='almanack', daemon=True)
            _worker.start()


def _work() -> None:
    while True:
        file_name, text, append = _jobs.get()
        try:
            os.makedirs(data_path(LOG_DIR), exist_ok=True)
            with open(data_path(LOG_DIR, file_name), 'a' if append else 'w', encoding='utf-8') as file:
                file.write(text)
        except Exception:
            pass
        finally:
            _jobs.task_done()


def write_almanack_async(galaxy: Galaxy) -> None:
    """Writes the galaxy's almanack in the background, replacing any previous file. Fire and forget."""
    try:
        _submit(ALMANACK_FILE_NAME, galaxy.almanack(), append=False)
    except Exception:
        pass


def reset_people_almanack() -> None:
    """Blanks the people's almanack. Called when a game starts or loads, before any person exists."""
    try:
        _submit(ALMANACK_PEOPLE_FILE_NAME, '', append=False)
    except Exception:
        pass


def append_person_almanack(person: Person) -> None:
    """Adds the person's entry to the people's almanack, as soon as the person is created."""
    try:
        _submit(ALMANACK_PEOPLE_FILE_NAME, person.almanack(), append=True)
    except Exception:
        pass


def relative_path_from_logs(path: str) -> str:
    """`path` as seen from the Logs folder, with forward slashes, for the links in the almanacks."""
    relative = os.path.relpath(os.path.abspath(path), os.path.abspath(data_path(LOG_DIR)))
    return relative.replace(os.sep, '/')
