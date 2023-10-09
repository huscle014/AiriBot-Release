from utils.constant import Constant as const
import utils.logger as logger
from utils.cutils import retrieve_configuration

class CogSetup:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logger.Logger("CogSetup")

    async def setup(self, load_config = True):
        self.logger.debug("==== CogSetup :: setup :: start ====")
        data = None
        if load_config:
            data = retrieve_configuration()
        
        if data is None:
            self.logger.debug(f"configuration file not found, default deploying all the available functions (commands)")
            await self.enable_all_features()
        else:
            features = data["configurations"]["features"]
            for feature in features:
                self.logger.debug(f"enable plugin {feature['name']} to {feature['enabled']}")
                if feature["enabled"]:
                    _invoke = getattr(self, const.FEATURE_MAPPING[feature["name"]])
                    await _invoke()
            self.logger.debug("complete enabled plugin based on configuration file..")
        await self.misc()
        self.logger.debug("==== CogSetup :: setup :: complete ====")

    async def enable_all_features(self):
        await self.musicbot()
        await self.minigame()
        await self.utilities()
        await self.admin()
        await self.scoreboard()
        await self.bluearchive()

    async def musicbot(self):
        await self.bot.load_extension("plugin.musicbot")

    async def minigame(self):
        await self.bot.load_extension("plugin.minigame")

    async def utilities(self):
        await self.bot.load_extension("plugin.utilities")

    async def admin(self):
        await self.bot.load_extension("plugin.administration")

    async def scoreboard(self):
        await self.bot.load_extension("plugin.scoreboard")

    async def bluearchive(self):
        await self.bot.load_extension("plugin.bluearchive")

    async def misc(self):
        await self.bot.load_extension("plugin.misc")