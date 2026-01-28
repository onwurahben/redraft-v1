import logging
import os

LOG_FILE = "redraft.log"

from logging.handlers import RotatingFileHandler

# Configure logging with the specified format and handlers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(LOG_FILE, encoding='utf-8', maxBytes=1_000_000, backupCount=5),
        logging.StreamHandler()
    ]
)

def get_logger(name):
    """
    Returns a logger with the specified name.
    """
    return logging.getLogger(name)
