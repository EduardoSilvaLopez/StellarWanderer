import logging
from common.paths import LOGS_DIR

LOG_LEVEL = logging.DEBUG
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
LOG_DIR = LOGS_DIR
LOG_FILE_NAME = 'stellar_wanderer.log'
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3
HITCH_SECONDS = 0.1  # a frame whose work takes longer is logged as a hang (common.frame_watch)
GC_SECONDS = 0.02  # a garbage collection longer than this is logged
