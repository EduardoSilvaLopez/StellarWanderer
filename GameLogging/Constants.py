import logging

LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
LOG_DIR = 'Logs'
LOG_FILE_NAME = 'stellar_wanderer.log'
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3
