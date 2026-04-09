import logging

LOG_DIR = "/home/alekcoleman/Desktop/SystemLogger.log"

logger = logging.getLogger("SystemLogger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_DIR, encoding="utf-8")
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
