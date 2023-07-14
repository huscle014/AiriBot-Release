import asyncio

from plugin.musicbot import setup as musicbotsetup
from plugin.minigame import setup as minigamesetup
from plugin.utilities import setup as utilitiessetup
from plugin.administration import setup as administrationsetup
from plugin.scoreboard import setup as scoreboardsetup

import utils.constant as const
from utils import logger
from utils.cutils import retrieve_configuration

class CogSetup:
    def __init__(self, bot):
        self.bot = bot

    def setup(self, load_config = True):
        data = None
        if load_config:
            data = retrieve_configuration()
        
        if data is None:
            logger.debug(f"configuration file not found, default deploying all the available functions (commands)")
            self.enable_all_features()
        else:
            features = data["configurations"]["features"]
            for feature in features:
                if feature["enabled"]:
                    logger.debug(f"enable plugin {feature['name']} to {feature['enabled']}")
                    _invoke = getattr(self, const.FEATURE_MAPPING[feature["name"]])
                    _invoke()
            logger.debug("complete enabled plugin based on configuration file..")

    def enable_all_features(self):
        self.musicbot()
        self.minigame()
        self.utilities()
        self.admin()
        self.scoreboard()

    def musicbot(self):
        asyncio.run(musicbotsetup(self.bot))

    def minigame(self):
        asyncio.run(minigamesetup(self.bot))

    def utilities(self):
        asyncio.run(utilitiessetup(self.bot))

    def admin(self):
        asyncio.run(administrationsetup(self.bot))

    def scoreboard(self):
        asyncio.run(scoreboardsetup(self.bot))