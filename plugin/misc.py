import discord
from discord.ext import commands
from discord import app_commands
import time, datetime
import psutil

import utils.logger as logger
import staticrunner as sr
from utils.discord.utils import context, response

class Misc(commands.Cog):
    """Misc commands"""

    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot
        self.logger = logger.Logger("Misc")

    @commands.Cog.listener()
    async def on_ready(self):
        global startTime            # global variable to be used later in cog
        startTime = time.time()     # snapshot of time when listener sends on_ready

    @commands.is_owner()
    @app_commands.command(name="status")
    async def status(self, ctx:discord.Interaction| commands.Context):
        """Show the uptime of the service"""
        self.logger.debug("===== status =====")

        ctx = await context(ctx)

        embed = discord.Embed(
            color=discord.Color.from_rgb(255, 170, 204))
        uptime = str(datetime.timedelta(seconds=int(round(time.time()-startTime))))
        latency = round(self.bot.latency * 1000)

        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory()[2]
        ram_usage_gb = psutil.virtual_memory()[3]/1000000000
        
        ts = f"<t:{int(sr.StaticRunner.time_deploy_start)}:R>"
        embed = discord.Embed(title="Airi's status observation", description="", color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.datetime.now())
        embed.set_footer(icon_url=self.bot.user.avatar, text=f"AiriBot | EN")

        embed.add_field(name="Reaction", value=f"{latency} ms")
        embed.add_field(name="Since", value=ts)
        embed.add_field(name="Alive for", value=uptime)

        embed.add_field(name="Processing", value=f"{cpu_usage}%")
        embed.add_field(name="Memory", value=f"{ram_usage_gb} ({ram_usage}%)")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Misc(bot))