import logging
import logging.handlers as lhandler
import os
import datetime as dt

from enum import Enum
from utils.constant import Constant as const
 
class Level(Enum):
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4

class Logger:

    """
    Create logging instance
    """
    LOG_PATH = "\\log\\"
    LOG_FILE_PREFIX = f"log{'_' + const.LOGGING_FILENAME if not const.LOGGING_FILENAME == '' else '_' + const.APPNAME}"
    LOG_FILE_EXT = "log"
    LOGGING_PATH = f"{os.curdir}\\{LOG_PATH}"

    rootLogger: logging.Logger = None

    @staticmethod
    def load_root_logger():
        if Logger.rootLogger == None:
            Logger.rootLogger = logging.getLogger()
            Logger.rootLogger.name = const.APPNAME
            if not os.path.isdir(Logger.LOGGING_PATH):
                os.makedirs(Logger.LOGGING_PATH)

            LOGLEVEL = logging._nameToLevel[const.LOGGING_LEVEL.upper()]

            logging.basicConfig(filemode='a',
                                format='[%(asctime)s,%(msecs)-3d] [%(threadName)-20.20s] %(name)s %(levelname)-5.5s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S',
                                level=LOGLEVEL,
                                encoding="utf-8")

            logFormatter = logging.Formatter("[%(asctime)s,%(msecs)-3d] [%(threadName)-20.20s] %(name)s %(levelname)-5.5s %(message)s",
                                            datefmt='%Y-%m-%d %H:%M:%S')
            
            def filer():
                now = dt.datetime.now()
                return f"{Logger.LOG_FILE_PREFIX}_{now.strftime('%Y-%m-%d_%H:%M:%S')}.{Logger.LOG_FILE_EXT}"

            ## fix log update issue
            if const.LOGGING_DAYCHANGE:
                fileHandler = lhandler.TimedRotatingFileHandler("{0}/{1}.{2}".format(Logger.LOGGING_PATH, Logger.LOG_FILE_PREFIX, Logger.LOG_FILE_EXT),
                                            when="D", backupCount=30, interval=1, encoding='utf-8')
                fileHandler.rotation_filename(filer)
            else:
                fileHandler = logging.FileHandler("{0}/{1}.{2}".format(Logger.LOGGING_PATH, Logger.LOG_FILE_PREFIX, Logger.LOG_FILE_EXT),
                                            encoding='utf-8')

            fileHandler.setFormatter(logFormatter)
            Logger.rootLogger.addHandler(fileHandler)

    def __init__(self, name: str = None):
        Logger.load_root_logger()
        self.logger = Logger.rootLogger.getChild(const.APPNAME if name == None else name)

    """
    function for logging, default logging level is info
    """ 
    def log(self, msg = '', level: Level = Level.INFO):
        self.logger.log(level = logging._nameToLevel[level.name], msg = msg)

    def debug(self, msg = ''):
        self.logger.debug(msg = msg)

    def info(self, msg = ''):
        self.logger.info(msg = msg)

    def error(self, msg = ''):
        self.logger.error(msg = msg)

    def warning(self, msg = ''):
        self.logger.warn(msg = msg)