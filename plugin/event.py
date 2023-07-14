import discord
from discord.ext import commands, tasks

import asyncio
from time import time
import traceback
import sys

from utils import logger
import staticrunner as sr

from pretty_help import PrettyHelp, EmojiMenu, AppMenu

class Event(commands.Cog):

    __slots__ = ('bot')

    sttime = int(time())
    botactivity = [
        discord.Activity(
            type=discord.ActivityType.playing, 
            name="跟MMJ的大家一起約會喲\n偷偷跟你說之後私訊會有驚喜喲", 
            large_image='https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg',
            large_text = "Airi",
            small_image = "https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg",
            small_text = "Airi",
            timestamps={
                'end':sttime,
                'start':sttime+60*60*24*365
            },
            buttons=["play"])
    ]

    def __init__(self, bot):
        self.bot = bot

    # async def __local_check(self, ctx):
    #     """A local check which applies to all commands in this cog."""
    #     if not ctx.guild:
    #         raise commands.NoPrivateMessage
    #     return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('這個指令無法在私訊使用哦~')
            except discord.HTTPException:
                pass

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    runloop = 1
    @tasks.loop(seconds=20)
    async def updateStatus(self):
        global runloop
        if self.runloop % 2 == 0:
            await self.bot.change_presence(activity=discord.Activity(
                    type=discord.ActivityType.watching, 
                    name=f"愛莉目前在 {len(self.bot.guilds)} 伺服器裏應援大家喲"
                ), status=discord.Status.do_not_disturb)
        else:
            await self.bot.change_presence(activity=self.botactivity[0], status=discord.Status.do_not_disturb)
        
        self.runloop = self.runloop + 1

    # EVENT LISTENER FOR WHEN THE BOT HAS SWITCHED FROM OFFLINE TO ONLINE.
    @commands.Cog.listener()
    async def on_ready(self):
        # await discord.app_commands.CommandTree(self.bot).sync()
        logger.info("Deployed and goes online")
        
        if not self.updateStatus.is_running():
            self.updateStatus.start()

        guild_count = len(self.bot.guilds)

        for guild in self.bot.guilds:
            logger.info(f"- {guild.id} (name: {guild.name.encode('utf8')})")

            sr.StaticRunner.setDefaultRoleOnUserJoin[guild.id] = True

        logger.info("Currently serve in " + str(guild_count) + " guilds.")

    ###when new user joined the server
    @commands.Cog.listener()
    async def on_member_join(self, member):
        #logger.info(f"新成員加入， {member.guild.name}")
        if member.guild.id in sr.StaticRunner.setDefaultRoleOnUserJoin:
            boolDefRole = sr.StaticRunner.setDefaultRoleOnUserJoin[member.guild.id]
            if boolDefRole and member.guild.id not in sr.StaticRunner.defaultRole:
                guild_owner = self.bot.get_user(int(member.guild.owner.id))
                await guild_owner.send(f"有新成員加入 **{member.guild.name}**，但沒有設置預設身份組喲，沒辦法自動幫新成員設置身份！")
            elif boolDefRole:
                await member.add_roles(sr.StaticRunner.defaultRole[member.guild.id])
            else:
                logger.info(f"沒設置任何東西呢！")
        await member.send(f"歡迎加入 **{member.guild.name}**！記得查閲規章喲")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        sr.StaticRunner.setDefaultRoleOnUserJoin[guild.me] = False
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embedHi = discord.Embed(
                            title="嗨嗨，大家好，我是桃井愛莉！很高興認識大家",
                            description=
                            f"我支援不少的指令，以下都是我可以支援的指令喲！",
                    url="https://github.com/huscle014/AiriBot",
                            colour=discord.Colour.from_rgb(255, 170, 204))
                embedHi.set_thumbnail(
                            url="https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg"
                        )
                embedHi.set_image(url="https://storage.sekai.best/sekai-assets/character/member/res007_no024_rip/card_after_training.webp")
                embedHi.set_footer(
                            text="© Huscle - Momoi Airi discord assistance bot")
                await channel.send(embed=embedHi, view=self.RenderViewJoinGuild())
            break

    ###this region for command

    @commands.Cog.listener()
    async def on_message(self, message :discord.Message):
        # logger.debug(message.content)
        if message.author.bot:
            return
        elif isinstance(message.channel, discord.channel.DMChannel):
            #handle for dm (planned to do ai chatbot)
            logger.info("received message from dm")
            pass
        elif message.type == discord.MessageType.premium_guild_subscription:
            logger.info(str(message.author))
        elif self.bot.user.mention in message.content:
            await message.channel.send(f"嗨嗨，有什麽需要幫助的嗎？\n可以使用 **愛莉幫幫我** 來獲得指令資訊喲！", reference=message)
        else:
            # await self.bot.process_commands(message)
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error: Exception):
        if isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.BadArgument):
            pass
        elif isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"缺少了重要的參數哦 \n```css\n- {error}```")
        else:
            await ctx.send(f"指令似乎有誤呢 我沒法辦理解（納悶）")
            raise error

    #send a message when join a server
    class RenderViewJoinGuild(discord.ui.View):
        def __init__(self):
            super().__init__()
            button1 = discord.ui.Button(label="更深入的認識我", style=discord.ButtonStyle.grey, url=f'https://zh.moegirl.org.cn/zh-hant/%E6%A1%83%E4%BA%95%E7%88%B1%E8%8E%89')
            self.add_item(button1)
            button2 = discord.ui.Button(label="把愛莉帶走吧", style=discord.ButtonStyle.grey, url=f"https://discord.com/api/oauth2/authorize?client_id=1123081408529842206&permissions=8&scope=bot%20applications.commands")
            self.add_item(button2)

        @discord.ui.select( # the decorator that lets you specify the properties of the select menu
            placeholder = "支援的指令！", # the placeholder text that will be displayed if nothing is selected
            min_values = 1, # the minimum number of values that must be selected by the users
            max_values = 1, # the maximum number of values that can be selected by the users
            options = [ # the list of options from which users can choose, a required field
                discord.SelectOption(
                    value="預設身份組",
                    label="預設身份組 【僅管管能使用！!】",
                    description="設置預設身份組，如已設置開啓自動發放身分組，此身份會給予新加入的成員"
                ),
                discord.SelectOption(
                    value="查看預設身份組",
                    label="查看預設身份組 【僅管管能使用！！】",
                    description="查看預設身份組，需提前設置 **預設身份組** "
                ),
                discord.SelectOption(
                    value="移除預設身份組",
                    label="移除預設身份組 【僅管管能使用！！】",
                    description="移除已設置的預設身份組"
                )
            ]
        )
        async def select_callback(self, interaction:discord.Interaction, select: discord.ui.Select): # the function called when the user is done selecting options
            await interaction.response.send_message(
                f"已選取指令 **{select.values[0]}**\n可以將這個指令複製到對話框後發送來使用喲~ \\\(ᵔᵕᵔ)/",ephemeral=True)

def setup(bot):
    event = Event(bot)
    attributes = {
        'name': "help",
        'aliases': ["愛莉幫幫我", "關於愛莉"],
        'cooldown': commands.CooldownMapping.from_cooldown(3, 5, commands.BucketType.user),
    }

    menu = AppMenu(ephemeral=True)
    bot.help_command = PrettyHelp(menu=menu, 
                                  color=discord.Color.from_rgb(255, 170, 204), 
                                  thumbnail_url="https://cdn.discordapp.com/attachments/1123128693187940472/1125267359314235463/109185147_p0.jpg",
                                  image_url="https://storage.sekai.best/sekai-assets/character/member/res007_no024_rip/card_after_training.webp",
                                  delete_invoke=True
                                  )
    asyncio.run(bot.add_cog(event))