import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

FORMATTER = logging.Formatter('[%(asctime)s] — [%(name)s] — [%(levelname)s] — [%(message)s]')
LOG_FILE = Path('logs/lightshot.log')
GLOBAL_LOGGER_NAME = 'lightshot_main'


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    console_handler.name = 'global_handler'
    return console_handler

def get_file_handler():
    file_handler = TimedRotatingFileHandler(LOG_FILE, when='midnight')
    file_handler.setFormatter(FORMATTER)
    return file_handler

def get_logger(logger_name=GLOBAL_LOGGER_NAME):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG) # better to have too much log than not enough

    if not (len(logger.handlers) > 0 and logger.handlers[0].name == 'global_handler'):
        logger.addHandler(get_console_handler())

    # with this pattern, it's rarely necessary to propagate the error up to parent
    logger.propagate = False
    return logger

if not os.path.exists('logs'):
    try:
        os.mkdir('logs')
    except NotADirectoryError as e:
        print('Could not instantiate global logger')



