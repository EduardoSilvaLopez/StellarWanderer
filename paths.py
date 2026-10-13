"""Where the game keeps its writable data: savefiles and logs."""

import os
import sys

APP_NAME = 'StellarWanderer'
SAVEFILES_DIR = 'Savefiles'


def data_path(*parts: str) -> str:
    '''Returns a path inside the writable data folder.

    A packaged build (PyInstaller sets sys.frozen) keeps its data in %LOCALAPPDATA%\\StellarWanderer,
    because the install folder is read-only for normal users. A source run keeps the relative paths
    it always had (from the current directory), so existing saves and logs stay where they are.

    Args:
        parts: Folder and file names inside the data folder, e.g. ('Savefiles', 'Savefile 1 ....json')

    Returns:
        The joined path.'''
    if getattr(sys, 'frozen', False):
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return os.path.join(base, APP_NAME, *parts)
    return os.path.join(*parts)
