import os
import json

class Constant:

    RSC_PUB_PATH = f"{os.getcwd()}\\resources\\public\\images"
    CONF_NAME = ["conf.json", "configuration.json", "setup.json"]
    FEATURE_MAPPING={
        "music":"musicbot",
        "minigame":"minigame",
        "utilities":"utilities",
        "admin":"admin",
        "scoreboard":"scoreboard",
        "bluearchive":"bluearchive"
    }

    CONF_KEY_MAPPING = {
        "APPNAME" : ["appname"],
        "ENV": ["environment"],
        "BOT_TOKEN": ["configurations","token"],
        "SUPPORTED_LANGUAGE": ["configurations","supported_languages"],
        ### Logging configuration
        "LOGGING_FILENAME" : ["configurations","log","filename"],
        "LOGGING_LEVEL" : ["configurations","log","level"],
        "LOGGING_DAYCHANGE" : ["configurations","log","by_date"],
        ### Scoreboard
        "DEFAULT_SCOREBOARD_SHEET" : ["configurations","gspread","default_spreadsheet_id"],
        ### Email
        "SMTP_SERVER" : ["configurations","email","server","proxy"],
        "SMTP_PORT" : ["configurations","email","server","port"],
        "SMTP_SENDER" : ["configurations","email","sender","email"],
        "SMTP_APPLICATION_SECRET" : ["configurations","email","sender","secret"],
        "SMTP_RCV" : ["configurations","email","recipients"],
        ### Developer config
        "DEVP_NOTIFICATION_CHANNEL" : ["developer","notification","channels"],
    }

    APPNAME = ""
    ENV = "DEVP"
    BOT_TOKEN = ""
    LOGGING_FILENAME = ""
    LOGGING_LEVEL = ""
    LOGGING_DAYCHANGE = False
    DEFAULT_SCOREBOARD_SHEET = ""
    SUPPORTED_LANGUAGE = ["en_US"]

    ### Email configuration
    SMTP_SERVER = ""
    SMTP_PORT = ""
    SMTP_SENDER = ""
    SMTP_APPLICATION_SECRET = ""
    SMTP_RCV = ""

    ### developer
    DEVP_NOTIFICATION_CHANNEL = ""
    
    @classmethod
    def load_configuration(cls):
        ### Safe retrieval key
        configuration = Constant.retrieve_configuration()
        if configuration:
            print(f"DEBUG Start to load configuration..")
            for k, v in Constant.CONF_KEY_MAPPING.items():
                dic = configuration
                res = None
                for d in v:
                    dic = dic.get(d, None)
                    res = dic
                
                if not res == None:
                    print(f"DEBUG Load key {','.join(v)} as {k} with value :: {res}")
                    setattr(cls, k, res)
                else:
                    print(f"WARN Unable to load key {v}")
                    pass
            print(f"DEBUG Complete loaded configuration..")

    @staticmethod
    def retrieve_configuration():
        data = None
        for f in Constant.CONF_NAME:
            path = f"{os.getcwd()}\\{f}" or f"{os.getcwd()}\\conf\\{f}"
            if not os.path.exists(path):
                continue
            f = open(f)
            data = json.load(f)
            break
        return data