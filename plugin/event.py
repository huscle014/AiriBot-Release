import discord
from discord.ext import commands, tasks

import asyncio
import traceback
import sys
import datetime, time
import threading

import utils.logger as logger
from utils.cutils import check_send_email, load_server_setting, _gettext, get_server_locale
import staticrunner as sr
from utils.constant import Constant as const
from utils.google.gmailclient import GmailClient as gc
from utils.database.connection import raw

from pretty_help import PrettyHelp, AppMenu

class Event(commands.Cog):

    __slots__ = ('bot')

    sttime = int(time.time())
    botactivity = [
        # discord.Activity(
        #     type=discord.ActivityType.playing, 
        #     name="MMJ下課後的時間", 
        #     state="Waiting in lobby",
        #     description="跟MMJ的大家一起約會喲\n偷偷跟你說之後私訊會有驚喜喲",
        #     large_image='https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg',
        #     large_text = "Airi",
        #     small_image = "https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg",
        #     small_text = "Airi",
        #     timestamps={
        #         'end':sttime,
        #         'start':sttime+60*60*24*365
        #     },
        #     buttons=["play"])
        discord.Activity(
            type=discord.ActivityType.playing, 
            name="跟MMJ的大家一起約會喲\n偷偷跟你說之後私訊會有驚喜喲"
        )
    ]

    def __init__(self, bot):
        self.bot = bot
        self.logger = logger.Logger("Event")

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('這個指令無法在私訊使用哦~')
            except discord.HTTPException:
                pass

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    runloop = True
    @tasks.loop(seconds=30)
    async def updateStatus(self):
        global runloop
        if self.runloop:
            await self.bot.change_presence(activity=discord.Activity(
                    type=discord.ActivityType.watching, 
                    name=f"愛莉目前在 {len(self.bot.guilds)} 伺服器裏應援大家喲"
                ), status=discord.Status.do_not_disturb)
        else:
            await self.bot.change_presence(activity=self.botactivity[0], status=discord.Status.do_not_disturb)
        
        self.runloop = not self.runloop

    # async def setup_hook(self):
    @commands.Cog.listener()
    async def on_connect(self):
        self.logger.debug("==== setup ====")
        await self.bot.tree.sync()
        
        if not self.updateStatus.is_running():
            self.updateStatus.start()

        guild_count = len(self.bot.guilds)

        self.logger.info(f"Currently serve in {guild_count} guilds.")
        self.logger.debug("==== setup ====")

    # EVENT LISTENER FOR WHEN THE BOT HAS SWITCHED FROM OFFLINE TO ONLINE.
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Deployed and goes online")
        sr.StaticRunner.time_taken_deployment = datetime.timedelta(seconds=int(round(time.time()-sr.StaticRunner.time_deploy_start)))

        if check_send_email(): 
            thread_send_email_notification = threading.Thread(target=self.send_email_notification)
            thread_send_email_notification.start()
            thread_send_email_notification.join()

        thread_load_server_info = threading.Thread(target=self.load_server_info)
        thread_load_server_info.start()
        thread_load_server_info.join()

        self.logger.debug(f"Time taken for deployment :: {sr.StaticRunner.time_taken_deployment}")
        self.logger.debug(f"Connected as :: {self.bot.user.name}")
        self.logger.info("==== startup completed ====")

    def send_email_notification(self):
        self.logger.info("==== startup - send email notification ====")
        time_taken_deploy = str(sr.StaticRunner.time_taken_deployment)
        try:
            timestamp = datetime.datetime.now()
            gc.ApplicationCredSender.send_email(subject=f"ALERT : Complete startup of {const.APPNAME} at {timestamp}", 
                                                recipients=const.SMTP_RCV, body=f'<h3>This message indicate the application {const.APPNAME} had completed that startup</h3><p><table style="border-collapse:collapse;border-spacing:0;border:none" class="tg"><thead><tr><th style="border-style:solid;border-width:0px;font-family:Arial, sans-serif;font-size:14px;font-weight:bold;overflow:hidden;padding:10px 5px;text-align:right;vertical-align:top;word-break:normal">Time taken for deployment:</th><th style="border-style:solid;border-width:0px;font-family:Arial, sans-serif;font-size:14px;font-weight:normal;overflow:hidden;padding:10px 5px;text-align:left;vertical-align:top;word-break:normal">{time_taken_deploy}</th></tr></thead><tbody><tr><td style="border-style:solid;border-width:0px;font-family:Arial, sans-serif;font-size:14px;font-weight:bold;overflow:hidden;padding:10px 5px;text-align:right;vertical-align:top;word-break:normal">Timestamp:</td><td style="border-style:solid;border-width:0px;font-family:Arial, sans-serif;font-size:14px;overflow:hidden;padding:10px 5px;text-align:left;vertical-align:top;word-break:normal">{timestamp}</td></tr></tbody></table>')
        except Exception as ex:
            self.logger.warning(f"Failed to send email with exception :: {ex}")
        self.logger.info("==== startup - send email notification ====")

    def load_server_info(self):
        self.logger.info("==== startup - load server info ====")
        # for guild in self.bot.guilds:
        #     self.logger.debug(f"- {guild.id} (name: {guild.name.encode('utf8')})")
        load_server_setting()
        self.logger.info("==== startup - load server info ====")
            

    ###when new user joined the server
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        #self.logger.info(f"新成員加入， {member.guild.name}")
        locale = get_server_locale(member.guild.id)

        if member.guild.id in sr.StaticRunner.setDefaultRoleOnUserJoin:
            boolDefRole = sr.StaticRunner.setDefaultRoleOnUserJoin[member.guild.id]
            if boolDefRole and member.guild.id not in sr.StaticRunner.defaultRole:
                guild_owner = self.bot.get_user(int(member.guild.owner.id))
                await guild_owner.send(_gettext('msg_event_member_join_no_default', locale).format(guild_name=member.guild.name))
            elif boolDefRole:
                await member.add_roles(sr.StaticRunner.defaultRole[member.guild.id])
            else:
                self.logger.info(f"沒設置任何東西呢！")
        if not member.bot:
            await member.send(_gettext('msg_event_member_join', locale).format(guild_name=member.guild.name))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        locale = get_server_locale(guild.id)

        sr.StaticRunner.setDefaultRoleOnUserJoin[guild.me] = False
        affect = raw(f"INSERT OR REPLACE INTO DC_SERVER(SERVER_ID,SERVER_NAME) VALUES('{guild.id}','{guild.name}')")[1]
        affect = raw(f"INSERT OR REPLACE INTO DC_SERVER_SETTING(SERVER_ID,LOCALE,EN_DEF_ROLE) VALUES('{guild.id}','en_US','0')")[1]
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embedHi = discord.Embed(
                            title=_gettext('msg_event_guild_join_title', locale),
                            description=_gettext('msg_event_guild_join_desc', locale),
                    url="https://github.com/huscle014/AiriBot",
                            colour=discord.Colour.from_rgb(255, 170, 204))
                embedHi.set_thumbnail(
                            url="https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg"
                        )
                embedHi.set_image(url="https://storage.sekai.best/sekai-assets/character/member/res007_no024_rip/card_after_training.webp")
                embedHi.set_footer(
                            text="© Huscle - Momoi Airi discord assistance bot")
                await channel.send(embed=embedHi, view=self.RenderViewJoinGuild(locale))
            break

    ###this region for command

    @commands.Cog.listener()
    async def on_message(self, message :discord.Message):
        if message.author.bot:
            return
        elif isinstance(message.channel, discord.channel.DMChannel):
            #handle for dm (planned to do ai chatbot)
            pass
        elif message.type == discord.MessageType.premium_guild_subscription:
            self.logger.info(str(message.author))
        elif self.bot.user.mention in message.content:
            locale = get_server_locale(message.guild.id)
            await message.channel.send(_gettext('msg_event_mentioned_1', locale) + "\n" + _gettext('msg_event_mentioned_2', locale), reference=message)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        try:
            if ctx.interaction is not None and ctx.interaction.is_expired():
                ctx = ctx.interaction.followup
            if isinstance(error, commands.CommandNotFound):
                return await ctx.defer()
            
            locale = get_server_locale(ctx.guild.id)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            if isinstance(error, commands.BadArgument) or isinstance(error, commands.CheckFailure):
                await ctx.send(f"{error}")
            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(_gettext('msg_error_missing_parameter', locale) + f"\n```\n- {error}```", delete_after=30)
            else:
                await ctx.send(_gettext('msg_error_common', locale), delete_after=30)
        except:
            pass
        finally:
            await ctx.message.delete(delay=2)

    #send a message when join a server
    class RenderViewJoinGuild(discord.ui.View):
        def __init__(self, locale):
            self.locale = locale
            super().__init__()
            button1 = discord.ui.Button(label=_gettext('msg_event_guild_join_btn_1', locale), style=discord.ButtonStyle.grey, url=f'https://zh.moegirl.org.cn/zh-hant/%E6%A1%83%E4%BA%95%E7%88%B1%E8%8E%89')
            self.add_item(button1)
            button2 = discord.ui.Button(label=_gettext('msg_event_guild_join_btn_2', locale), style=discord.ButtonStyle.grey, url=f"https://discord.com/api/oauth2/authorize?client_id=1123081408529842206&permissions=8&scope=bot%20applications.commands")
            self.add_item(button2)

            button3 = discord.ui.Button(label=_gettext('msg_event_guild_join_btn_3', locale), style=discord.ButtonStyle.primary)
            button3.callback(self.button_callback)
            self.add_item(button3)

        async def button_callback(self, interaction:discord.Interaction, button: discord.Button):
            await interaction.response.send_message(_gettext('msg_event_guild_join_btn_3_resp', self.locale))

class CustomHelp(PrettyHelp):

    @discord.app_commands.command(name="help")
    async def _app_command_callback(
        self, interaction: discord.Interaction, command: str = None
    ):
        """Application help command for AiriBot"""
        bot = interaction.client
        ctx = await commands.Context.from_interaction(interaction)
        ctx.bot = bot
        await ctx.invoke(bot.get_command("help"), command=command)

def setup(bot):
    event = Event(bot)

    menu = AppMenu(ephemeral=True)
    bot.help_command = CustomHelp(menu=menu, 
                                  color=discord.Color.from_rgb(255, 170, 204), 
                                  thumbnail_url="https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg",
                                  image_url="https://storage.sekai.best/sekai-assets/character/member/res007_no024_rip/card_after_training.webp",
                                  delete_invoke=True
                                  )
    asyncio.run(bot.add_cog(event))