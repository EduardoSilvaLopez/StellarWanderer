"""Configure and initialize the logging system."""

import logging
import logging.handlers
import os
from .constants import (
    LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT, LOG_DIR, LOG_FILE_NAME,
    LOG_MAX_BYTES, LOG_BACKUP_COUNT
)
from common.paths import data_path

_file_log: list[logging.handlers.RotatingFileHandler] = []  # the one that writes the file log now, once configured


def configure_logging() -> None:
    """Set up logging with both console and rotating file handlers.

    Configures the root logger to write to console (StreamHandler) and to a
    rotating log file (RotatingFileHandler) in the Logs directory (inside the
    data folder, see paths.data_path).
    Should be called once at application startup, before any other logging.
    """
    os.makedirs(data_path(LOG_DIR), exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler: the startup log, until a game has a seed (log_to_seed)
    _file_log[:] = [_rotating_file_handler(data_path(LOG_DIR, LOG_FILE_NAME))]
    root_logger.addHandler(_file_log[0])


def _rotating_file_handler(path: str) -> logging.handlers.RotatingFileHandler:
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    return handler


def log_to_seed(seed: int) -> None:
    """From now on the file log is the one of the game of `seed` (Logs/<seed>/), so each galaxy keeps its own history.
    The startup log keeps what came before: the dialogs and the choice of the game. Does nothing before
    configure_logging (tests and tools run without a file log)."""
    if not _file_log:
        return
    root_logger = logging.getLogger()
    path = data_path(LOG_DIR, str(seed), LOG_FILE_NAME)
    logging.getLogger(__name__).info(f"The log goes on in {path}")
    root_logger.removeHandler(_file_log[0])
    _file_log[0].close()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _file_log[:] = [_rotating_file_handler(path)]
    root_logger.addHandler(_file_log[0])
    logging.getLogger(__name__).info(f"Log of the game of seed {seed}")
