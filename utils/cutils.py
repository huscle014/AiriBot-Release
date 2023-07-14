from apnggif import apnggif

import os
import requests
import string
import random
import json

from dateutil.parser import parse

import utils.constant as const
from utils import logger

TEMP_PATH = "\\temp\\apng_convert"

def apngtogif(url: str):
    r = requests.get(url, allow_redirects=True)
    path_to_temp = f"{os.getcwd()}{TEMP_PATH}"
    if not os.path.isdir(path_to_temp):
        os.makedirs(path_to_temp)
    tname = generateRandomStr(32)
    fpath_input = f"{path_to_temp}\\{tname}.png"
    open(fpath_input, 'wb').write(r.content)
    apnggif(png=fpath_input)
    logger.debug(f"name of file: {tname}, path: {fpath_input}")

    if os.path.exists(fpath_input):
        os.remove(fpath_input)
    return f"{path_to_temp}/{tname}.gif", f"{tname}.gif"

def generateRandomStr(len: int):
    res = ''.join(random.choices(string.ascii_uppercase +
                    string.digits, k=len))
    return str(res)

def convertSeconds(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
     
    return "%d:%02d:%02d" % (hour, minutes, seconds)

def retrieve_configuration():
    data = None
    for f in const.CONF_NAME:
        path = f"{os.getcwd()}\\{f}" or f"{os.getcwd()}\\conf\\{f}"
        logger.debug(f"scanning path :: {path}")
        if not os.path.exists(path):
            continue
        f = open(f)
        data = json.load(f)
        break
    return data

def is_date(string, fuzzy=False):
    """
    Return whether the string can be interpreted as a date.

    :param string: str, string to check for date
    :param fuzzy: bool, ignore unknown tokens in string if True
    """
    try: 
        parse(string, fuzzy=fuzzy)
        return True

    except ValueError:
        return False
    
def get_date(string) -> str:
    try: 
        return str(parse(string, yearfirst=True).date())

    except ValueError:
        return ''

def set_environment_variable(key, val):
    os.environ[key] = val
    
if __name__ == "__main__":
    apngtogif("https://cdn.discordapp.com/stickers/1071756412830617611.png")