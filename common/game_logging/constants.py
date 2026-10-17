import logging
from common.paths import LOGS_DIR

LOG_LEVEL = logging.DEBUG
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
LOG_DIR = LOGS_DIR
LOG_FILE_NAME = 'stellar_wanderer.log'
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3
ALMANACK_FILE_NAME = 'almanack.galaxy.md'  # written on every game start or load, in the data folder (not in LOG_DIR)
ALMANACK_PEOPLE_FILE_NAME = 'almanack.people.md'  # blank on every game start or load, then one entry per person, in the data folder
ALMANACK_IMAGE_WIDTH = 128  # pixels, for the portraits in the people's almanack (they are 512 x 768)
