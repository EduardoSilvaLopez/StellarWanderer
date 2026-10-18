"""Where the game's files are: the writable data (saves and logs) and the read-only resources."""

import os
import sys

APP_NAME = 'StellarWanderer'
SAVEFILES_DIR = 'Savefiles'
LOGS_DIR = 'Logs'

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder, in a source run


def data_path(*parts: str) -> str:
    '''Returns a path inside the writable data folder.

    A packaged build (PyInstaller sets sys.frozen) keeps its data in %LOCALAPPDATA%\\StellarWanderer,
    because the install folder is read-only for normal users. A source run keeps it in data/, below the project
    folder, whatever the current directory is.

    Args:
        parts: Folder and file names inside the data folder, e.g. ('Savefiles', 'my save.json')

    Returns:
        The joined path.'''
    if getattr(sys, 'frozen', False):
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return os.path.join(base, APP_NAME, *parts)
    return os.path.join(ROOT, 'data', *parts)


def resource_path(*parts: str) -> str:
    '''Returns a path inside the read-only resources (fonts, textures, people names, portraits): common/resources in
    the project, and the same folder inside a packaged build.

    Args:
        parts: Folder and file names inside the resources folder, e.g. ('fonts', 'Orbitron.ttf')

    Returns:
        The joined path.'''
    base = getattr(sys, '_MEIPASS', ROOT)
    return os.path.join(base, 'common', 'resources', *parts)
