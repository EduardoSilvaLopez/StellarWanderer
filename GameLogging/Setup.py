"""Configure and initialize the logging system."""

import logging
import logging.handlers
import os
from .Constants import (
    LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT, LOG_DIR, LOG_FILE_NAME,
    LOG_MAX_BYTES, LOG_BACKUP_COUNT
)


def configure_logging():
    """Set up logging with both console and rotating file handlers.

    Configures the root logger to write to console (StreamHandler) and to a
    rotating log file (RotatingFileHandler) in the Logs/ directory.
    Should be called once at application startup, before any other logging.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler
    log_file_path = os.path.join(LOG_DIR, LOG_FILE_NAME)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
