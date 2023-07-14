import os
import json


RSC_PUB_PATH = f"{os.getcwd()}\\resources\\public\\images"
CONF_NAME = ["conf.json", "configuration.json", "setup.json"]
FEATURE_MAPPING={
    "music":"musicbot",
    "minigame":"minigame",
    "utilities":"utilities",
    "admin":"admin",
    "scoreboard":"scoreboard"
}

def retrieve_configuration():
    data = None
    for f in CONF_NAME:
        path = f"{os.getcwd()}\\{f}" or f"{os.getcwd()}\\conf\\{f}"
        if not os.path.exists(path):
            continue
        f = open(f)
        data = json.load(f)
        break
    return data

CONF = retrieve_configuration()

APPNAME = CONF["appname"]
BOT_TOKEN = CONF["configurations"]["token"]
LOGGING_FILENAME = CONF["configurations"]["log"]["filename"]
LOGGING_LEVEL = CONF["configurations"]["log"]["level"]
LOGGING_DAYCHANGE = CONF["configurations"]["log"]["by_date"]
DEFAULT_SCOREBOARD_SHEET = CONF["configurations"]["gspread"]["default_spreadsheet_id"]