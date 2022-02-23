"""
DISP - DIstributed Structure Prediction
"""
import logging
from logging.handlers import WatchedFileHandler

__version__ = '1.0.0'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


# Set console handler level
def setconsolelevel(level):
    # Console handler
    console_handler.setLevel(level)


# Set the level of console handler (default)
setconsolelevel(logging.INFO)


# WatchedFileHandler
def setlogfile(filename, level=logging.INFO):
    """
    Set watched file handler for the logger
    filename : name of the file
    level : level of the logger. Default is the same as the
    module's logger
    """
    _ = level
    watched_file = WatchedFileHandler(filename)
    watched_file.setFormatter(formatter)
    logger.addHandler(watched_file)


