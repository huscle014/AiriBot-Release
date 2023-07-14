import logging
import logging.handlers as lhandler
import os
import datetime as dt

from enum import Enum
from utils import constant as const
 
class Level(Enum):
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4

"""
Create logging instance
"""
LOG_PATH = "\\log\\"
LOG_FILE_PREFIX = f"log{'_' + const.LOGGING_FILENAME if not const.LOGGING_FILENAME == '' else '_' + const.APPNAME}"
LOG_FILE_EXT = "log"
LOGGING_PATH = f"{os.curdir}\\{LOG_PATH}"

if not os.path.isdir(LOGGING_PATH):
    os.makedirs(LOGGING_PATH)

# LOGGING_FILE = f"{LOGGING_PATH}{LOG_FILE_PREFIX}"
# if not os.path.exists(LOGGING_FILE):
#     open(LOGGING_FILE, 'a')

LOGLEVEL = logging._nameToLevel[const.LOGGING_LEVEL.upper()]

logging.basicConfig(filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=LOGLEVEL)

logFormatter = logging.Formatter("[%(asctime)s] [%(threadName)-12.12s] %(name)s [%(levelname)-5.5s]  %(message)s",
                                 datefmt='%Y-%m-%d %H:%M:%S')
rootLogger = logging.getLogger()

def filer(self):
    now = dt.datetime.now()
    return f"{LOG_FILE_PREFIX}_{now.strftime('%Y-%m-%d_%H:%M:%S')}.{LOG_FILE_EXT}"

## fix log update issue
if const.LOGGING_DAYCHANGE:
    fileHandler = lhandler.TimedRotatingFileHandler("{0}/{1}.{2}".format(LOGGING_PATH, LOG_FILE_PREFIX, LOG_FILE_EXT),
                                  when="D", backupCount=30, interval=1, encoding='utf-8')
    fileHandler.rotation_filename(filer)
else:
    fileHandler = logging.FileHandler("{0}/{1}.{2}".format(LOGGING_PATH, LOG_FILE_PREFIX, LOG_FILE_EXT),
                                  encoding='utf-8')

fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

"""
function for logging, default logging level is info
""" 
def log(msg = '', level: Level = Level.INFO):
    logging.log(level = logging._nameToLevel[level.name], msg = msg)

def debug(msg = '', level: Level = Level.DEBUG):
    log(msg, level)

def info(msg = '', level: Level = Level.INFO):
    log(msg, level)

def error(msg = '', level: Level = Level.ERROR):
    log(msg, level)

def warning(msg = '', level: Level = Level.WARNING):
    log(msg, level)