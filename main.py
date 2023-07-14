import discord

from discord.ext import commands

import utils.constant as const
from utils import logger

import plugin.commandsetup as cogcommandsetup
from plugin.event import setup as eventsetup
import plugin.event as event

intents = discord.Intents.all()
intents.message_content = True

def get_prefixes(bot, message):
    cog_prefixes = (cog.prefix for cog in bot.cogs.values() if hasattr(cog, 'prefix'))
    default_prefixes = ('!')
    return (*cog_prefixes, *default_prefixes)

bot = commands.Bot(command_prefix=get_prefixes, intents=intents)

if __name__ == "__main__":
    try:
        cogcommandsetup.CogSetup(bot).setup()
        eventsetup(bot)
        
        bot.run(const.BOT_TOKEN)
    finally:
        logger.debug("The bot had complete the startup")