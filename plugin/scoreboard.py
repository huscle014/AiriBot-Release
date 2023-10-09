import discord
from discord.ext import commands
from discord.utils import get
from discord import app_commands
from typing import List
from discord.ext.commands import check, Context

import traceback
import sys
from datetime import date, datetime
import math
import asyncio
import re
import copy

import utils.logger as logger
from utils.constant import Constant as const
import utils.ocr as ocr
from utils.cutils import get_date, add_to_nested_dict, get_value_from_nested_dict, default_if_empty, generate_excel
from utils.discord.utils import context, response
from staticrunner import StaticRunner as sr
from utils.database.connection import select, raw
from utils.delayexecutor import setup_daily_scheduler
import utils.api.api as api

# from gspread_formatting import *
import utils.paginator as page
import validators
from fuzzywuzzy import process

"""
TODO: 
- 27-7-23 : Add permission assigning, originally some features should be available for certain roles only
- 4-8-23 : Auto load configuration from sheet upon startup (including database)
- 22-8-23 : Migrate processing to database (tend to reduce overhead and API latency)
            Threshold based on different club
            Allows permitted roles to download the excel
"""
class ScoreboardRecord:

    __slots__ = ('bot', 'current_event', 'is_active', 'threshold', 'default_award_rank', 'score_listening', 'listening_channel')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self.current_event = None
        self.is_active = False
        self.threshold = {}
        self.default_award_rank = {}
        self.score_listening = False
        self.listening_channel = None

class Scoreboard(commands.Cog):
    """Scoreboard related command."""

    __slots__ = ('bot', 'prefix')

    def __init__(self, bot):
        self.bot = bot
        self.scoreboard = {}
        self.logger = logger.Logger("Scoreboard")
        # self.prefix = 'scoreboard!'

        self.fetch_raid_boss()
        self.fetch_terrain()
        
        setup_daily_scheduler(daily_task=api.BlueArhieveAPI.fetch_ba_raid)
        
    # async def cog_check(self, ctx):
    #     return ctx.prefix == self.prefix

    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('這個指令無法在私訊使用哦~')
            except discord.HTTPException:
                pass

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_scoreboard(self, ctx) -> ScoreboardRecord:
        try:
            scoreboard = self.scoreboard[ctx.guild.id]
        except KeyError:
            scoreboard = ScoreboardRecord(ctx)

            # retrieve all configuration from database
            row, result = raw(f"SELECT GUILD_ID, DEFAULT_ROLE, RAID_TOP_ROLE, RAID_THRESHOLD FROM BA_GUILD WHERE SERVER_ID = '{ctx.guild.id}';")[1:]
            for r in result:
                add_to_nested_dict(scoreboard.threshold, [r['GUILD_ID']], r['RAID_THRESHOLD']) 
                add_to_nested_dict(scoreboard.default_award_rank, [r['GUILD_ID']], r['RAID_TOP_ROLE']) 
            
            self.scoreboard[ctx.guild.id] = scoreboard
            
        return scoreboard
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """ Handles command errors """

        if isinstance(error, commands.CheckFailure):
            pass

    # region !CRITICAL CHECKING! Check permited roles, in default only server owner, admin and bot owner
    async def permitted_to_execute(self, ctx: commands.Context, club: int = 0):
        return set(default_if_empty(get_value_from_nested_dict(sr.ba_club_manage_whitelist_roles, [ctx.guild.id, club]), [])) & set([role.id for role in ctx.author.roles]) or self.owner_only(ctx) or ctx.author.id in get_value_from_nested_dict(sr.ba_club_manage_whitelist_members, [ctx.guild.id, club])
    
    def owner_only(self, ctx: commands.Context):
        return ctx.author in [self.bot.application.owner, ctx.guild.owner]
    
    def admin_or_owner():
        async def predicate(ctx: Context):
            return ctx.author in [ctx.guild.owner] or ctx.message.author.guild_permissions.administrator
        return check(predicate)
    # endregion

    # region Fetch data from database
    def fetch_events(self, server_id):
        pass

    def fetch_raid_boss(self, force=False):
        if force or sr.ba_raid_boss is None:
            r = select('BA_RAID', ('ID', 'R_NAME'))[2]
            sr.ba_raid_boss = [(d['ID'], d['R_NAME']) for d in r]
        return sr.ba_raid_boss
    
    def fetch_terrain(self, force=False):
        if force or sr.ba_terrain is None:
            r = raw("SELECT NAME, DESCRIPTION FROM MISC WHERE TYPE = 'R_TYPE';")[2]
            sr.ba_terrain = [{d['NAME']: d['DESCRIPTION']} for d in r]
            sr.ba_terrain_names = [d['NAME'].title() for d in r]
        return sr.ba_terrain
    
    def update_setting(self, server, scoreboard):
        row, result = raw(f"SELECT GUILD_ID, DEFAULT_ROLE, RAID_TOP_ROLE, RAID_THRESHOLD FROM BA_GUILD WHERE SERVER_ID = '{server}';")[1:]
        for r in result:
            add_to_nested_dict(scoreboard.threshold, [r['GUILD_ID']], r['RAID_THRESHOLD']) 
            add_to_nested_dict(scoreboard.default_award_rank, [r['GUILD_ID']], r['RAID_TOP_ROLE']) 
    # endregion
    
    # region options
    async def whitelist_group_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = ['member', 'role']
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    async def show_option_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = ['member', 'myscore', 'raid']
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    async def sorting_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = ['name', 'rank']
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    async def listening_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = ['on', 'off']
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    async def raid_boss_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = self.fetch_raid_boss()
        return [
            app_commands.Choice(name=choice[1], value=choice[0])
            for choice in choices if current.lower() in choice[1].lower()
        ]
    
    async def raid_history_options(self,
        ctx: discord.Interaction|commands.Context,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        filter = [app_commands.Choice(name=f"Start typing for suggestion", value="*")]
        if current is not None and not current == '':
            filter = [
                app_commands.Choice(name=f"{choice[1]}, {choice[2]}", value=str(choice[1]))
                for choice in sr.ba_characters if str(choice[1]).lower().startswith(current.lower())
            ]
        return filter
    
    async def terrain_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = sr.ba_terrain_names
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    async def clubs_options(self,
        ctx: discord.Interaction|commands.Context,
        current: str,
    ) -> List[app_commands.Choice[int]]:
        choices = [(k, v.get('name')) for k, v in sr.ba_clubs.get(ctx.guild.id).items()]
        return [
            app_commands.Choice(name=choice[1], value=choice[0])
            for choice in choices if current in choice[1]
        ]
    # endregion
    
    scoreboard = app_commands.Group(name="scoreboard", description="scoreboard related functions")
    
    # region deprecated create event
    # @scoreboard.command(name='create-event', description="Create an raid event. The local current date will be use as default")
    # @app_commands.describe(boss="The raid boss")
    # @app_commands.describe(season="Which season of the raid")
    # @app_commands.describe(type="The terrain of the raid")
    # @app_commands.describe(date="The date of the event, default if not provided the local current date will be used")
    # @app_commands.autocomplete(boss=raid_boss_options)
    # @app_commands.autocomplete(type=terrain_options)
    # async def create(self, ctx: discord.Interaction|commands.Context, boss: int, season: int, type: str, date: str = str(date.today())):
    #     """
    #     Create an event. 
    #     The local current date will be use as default
    #     """
    #     self.logger.debug("===== scoreboard :: create-event =====")
    #     
    #         
    #     if not await self.permitted_to_execute(ctx):
    #         return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
            
    #     ctx = await context(ctx)

    #     scoreboard = self.get_scoreboard(ctx)
        
    #     try:
    #         row, bossname = raw(f"SELECT R_NAME FROM BA_RAID WHERE ID = '{boss}'")[1:]
    #         if row == 0:
    #             return await response(ctx, f"Raid boss not found")
    #         bossname = bossname[0]['R_NAME']

    #         name = f"{bossname} S-{season}"
    #         exist = raw(f"SELECT R_NAME, (SELECT DESCRIPTION FROM MISC WHERE TYPE = 'R_TYPE' AND ID = R_TYPE) AS TYPE FROM BA_RAID_RECORD WHERE SERVER_ID = '{ctx.guild.id}' AND R_NAME = '{name}';")[1]
    #         if not exist == 0:
    #             await ctx.send(embed=discord.Embed(title="", description=f"the event with name `{name}` already existed", color=discord.Color.from_rgb(255, 170, 204)))
    #             ## ask if the user want to create with alt name
    #         else:
    #             if not is_date(date):
    #                 return await ctx.send(embed=discord.Embed(title="", description=f"the date provided is not a valid format", color=discord.Color.from_rgb(255, 170, 204)))
                
    #             affect = raw(f"INSERT INTO BA_RAID_RECORD (R_ID, R_NAME, R_START_DATE, SERVER_ID, R_TYPE) VALUES ('{boss}', '{name}', '{date}', '{ctx.guild.id}', '{type}');")[1]
    #             scoreboard.current_event = name
    #             scoreboard.is_active = True
    #             await ctx.send(embed=discord.Embed(title="", description=f"the event, `{name}` had been created", color=discord.Color.from_rgb(255, 170, 204)))
    #     except Exception as e:
    #         raise 
    # endregion

    @scoreboard.command(name='set-score', description="Set the score to the scoreboard.")
    @app_commands.describe(score="The achieved score on the event")
    @app_commands.describe(rank="The achieved rank on the event")
    @app_commands.describe(member="The member to set the score to, usage in such /set-event-score [score] [rank] [@mention]")
    # @app_commands.describe(reference="The reply message to set the score, the score will be set that original poster or member mentioned")
    @app_commands.describe(image="The image to be perform automated extract score (experimental)")
    async def score(self, ctx: discord.Interaction|commands.Context, score: str = None, rank: str = None, member: discord.Member = None, reference: str = None, image: discord.Attachment = None):
        await self.score_method(ctx, score, rank, member, reference, image)
    
    async def score_method(self, ctx: discord.Interaction|commands.Context, score: str = None, rank: str = None, member: discord.Member = None, reference: str = None, image: discord.Attachment = None):
        """Set the score to the scoreboard. """
        self.logger.debug("===== scoreboard :: set-event-score =====")

        ctx = await context(ctx)

        ### check if there is active current event
        scoreboard = self.get_scoreboard(ctx)
        if not scoreboard.is_active:
            return await ctx.send(embed=discord.Embed(title="", description=f"there has no active event at the moment", color=discord.Color.from_rgb(255, 170, 204)))
        
        attch = None
        targeted_user = ctx.message.author
        mention_member = member is not None or len(ctx.message.mentions) > 0
        member_mentioned = member or ctx.message.mentions[0] if len(ctx.message.mentions) > 0 else None
        if mention_member:
            targeted_user = member
        
        reference = reference if reference is not None else None if ctx.message.reference is None else await ctx.fetch_message(ctx.message.reference.message_id)
        if mention_member and reference is not None:
            # fetch reference message
            reply_to: discord.Message = reference
            attch = reply_to.attachments

            if attch is None:
                return await ctx.send(embed=discord.Embed(title="", description=f"the reference message didn't include an attachment", color=discord.Color.from_rgb(255, 170, 204)))

        elif mention_member and reference is None:
            if not score is None and not rank is None:
                pass
            else:
                return await ctx.send(embed=discord.Embed(title="", description=f"hmmm seem like the way execute for this command is not correct", color=discord.Color.from_rgb(255, 170, 204)))
        elif validators.url(ctx.message.content) and ctx.message.content.endswith(('.jpg', '.png', '.gif', '.jpeg')):
            attch = ctx.message.content
        else:
            attch = image
        
        _ori_rank = rank
        _ori_score = score
        if attch:
            try:
                score, rank = self.__extract_score_from_image(attch)
            except Exception as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                if not member_mentioned and not score == None and not rank == None:
                    score = _ori_score
                    rank = _ori_rank
                else:
                    ## 10/7/2023: fallback to score manual update, wait for user input if originally not provided
                    embed=discord.Embed(title="Ummmhmmm, seem like I can't understand the image..", description=f"Feedback: {error}", color=discord.Color.from_rgb(255, 170, 204))
                    
                    embed.add_field(name="", value="\b", inline=False)
                    embed.add_field(name=":warning: Issue", value=f"hmmm.. unable to extract score and rank from the uploaded image..\nso kindly reply to this message with the rank and score, onegai!!", inline=False)
                    embed.add_field(name=":notepad_spiral: Format", value=f"Provide the input of rank and score using either one format as follow:\n- `rank#score` - seperate using a pound/hash sign or\n- `rank score` - seperate rank and score using a space", inline=False)
                    msgscore: discord.Message = await ctx.send(embed=embed)
                    def check(m):
                        if m.author == ctx.author and m.reference is not None:
                            if m.reference.message_id == msgscore.id:
                                return True
                        return False
                    
                    msg = await self.bot.wait_for("message", check=check)
                    rank_score = msg.content
                    lrank_score = rank_score.split("#") if '#' in rank_score else rank_score.split(" ")
                    rank = lrank_score[0]
                    score = lrank_score[1]

                self.logger.debug(f"rank :: {rank}, score :: {score}")
        elif not attch and score == None:
            return await ctx.send(embed=discord.Embed(title="", description=f"unable to update score, the value is not provided", color=discord.Color.from_rgb(255, 170, 204)))
        
        score = str(score).replace(',', '')
        userid = targeted_user.id

        rank = str(rank)
        score = str(score)
        
        affect = raw(f"INSERT OR REPLACE INTO BA_RAID_MEMBER (MEMBER_ID, RE_ID, RE_SCORE, RE_RANK, RE_DIFFICULTY)VALUES ('{userid}', '{scoreboard.current_event[0]}', '{score}', '{rank}', '5');")[1]
        
        embed = discord.Embed(title="", description=f"{targeted_user.mention}, your score for event `{scoreboard.current_event[1]}` had been set to `{score}` {' at `rank:' + rank + '`' if not rank == None else ''}", color=discord.Color.from_rgb(255, 170, 204))
        # embed.set_footer(text="use **/scoreboard show** to check the score!")
        await ctx.send(embed=embed)

    @scoreboard.command(name='activate-raid', description="Activate a raid event.")
    @app_commands.rename(event="raid")
    @app_commands.describe(event="The raid event name. If the event name not provided, default will set the latest event to active.")
    async def open(self, ctx: discord.Interaction|commands.Context, event: str = None):
        """Activate an event. If the event name not provided, default will set the latest event to active. """
        self.logger.debug("===== scoreboard :: activate-event =====")

        ctx = await context(ctx)

        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)

        scoreboard: ScoreboardRecord = self.get_scoreboard(ctx)
                
        if not event is None:
            exist, result = raw(f"SELECT BRR.ID, BR.R_NAME || ' S-' || BRR.R_SEASON AS R_NAME, BRR.R_TYPE FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID WHERE BR.R_NAME || ' S-' || BRR.R_SEASON = '{event}';")[1:]
            if exist == 0:
                return await ctx.send(embed=discord.Embed(title="", description=f"the event with name, `{event}` not found", color=discord.Color.from_rgb(255, 170, 204)))
        else:
            exist, result = self.__get_latest_raid()
            if exist == 0:
                return await ctx.send(embed=discord.Embed(title="", description=f"there has no available event to be activated", color=discord.Color.from_rgb(255, 170, 204)))

        scoreboard.current_event = (result[0].get('ID'),result[0].get('R_NAME'))
        scoreboard.is_active = True

        await ctx.send(embed=discord.Embed(title="", description=f"Event `{scoreboard.current_event[1]}` had been set to **active**", color=discord.Color.from_rgb(255, 170, 204)))

    @scoreboard.command(name='deactivate-raid', description="Close the current raid event and compute the score of the member if hit the minimum treshold. ")
    @app_commands.describe(compute="Default is True. If not willing to compute the score of the member if hit the minimum treshold, set it to False")
    async def close(self, ctx: discord.Interaction|commands.Context, compute: bool = True):
        """Close the current event and compute the score of the member if hit the minimum treshold. """
        self.logger.debug("===== scoreboard :: deactivate-event =====")
        
        ctx = await context(ctx)

        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)

        scoreboard: ScoreboardRecord = self.get_scoreboard(ctx)
        if scoreboard == None or not await self.__check_current_active_event(ctx):
            return
        if scoreboard.score_listening:
            return await ctx.send(embed=discord.Embed(title="", description=f"Failed to close event `{scoreboard.current_event[1]}` due to the running listener at channel `{scoreboard.listening_channel}`", color=discord.Color.from_rgb(255, 170, 204)))
        
        c_event = scoreboard.current_event
        scoreboard.current_event = None
        scoreboard.is_active = False

        message = ctx.message
        await ctx.send(embed=discord.Embed(title="", description=f"The event `{c_event[1]}` had been closed", color=discord.Color.from_rgb(255, 170, 204)))#, delete_after=3)

        if compute:
            ctx: commands.Context = await self.bot.get_context(message)
            guilds = raw(f"SELECT GUILD_ID, GUILD_NAME FROM BA_GUILD WHERE SERVER_ID = '{ctx.guild.id}';")[2]
            async with ctx.typing():
                msg_cal = await ctx.send(embed=discord.Embed(title="", description=f"Doing calculation on who is the top scorer in `{c_event}`...", color=discord.Color.from_rgb(255, 170, 204)))
                
                for guild in guilds:
                    record = raw(f"SELECT RM.MEMBER_ID, RE_ID, RE_SCORE, RE_RANK, RE_DIFFICULTY, RE_TIMING FROM BA_RAID_MEMBER RM LEFT JOIN BA_RAID_RECORD RR ON RM.RE_ID = RR.ID INNER JOIN BA_GUILD_MEMBER BGM ON RM.MEMBER_ID = BGM.MEMBER_ID WHERE BGM.GUILD_ID = '{guild['GUILD_ID']}' AND RR.ID = '{c_event[0]}' ORDER BY RE_SCORE DESC;")[2]

                    try:
                        d_role = scoreboard.default_award_rank.get(guild['GUILD_ID'], None)
                        if d_role is not None:
                            t_role = ctx.guild.get_role(int(d_role))
                            
                            if len(record) > 0:
                                top_scorer = record[0].get('MEMBER_ID')
                                raider = ctx.guild.get_member(int(top_scorer))
                            
                                for u in ctx.guild.members:
                                    if t_role in u.roles:
                                        self.logger.debug(f"{t_role} -> {u}")
                                        await u.remove_roles(*[t_role])

                                if raider is not None:
                                    await raider.add_roles(*[t_role], reason=f"highest rank in current raid for club {guild['GUILD_NAME']}")
                                    await ctx.send(content=f":tada: Congrats {raider.mention} became the new top scorer in raid `{c_event}` for **{guild['GUILD_NAME']}**!!")
                    finally:
                        pass
                    # calculate and compute the member which not passing the treshold marks
                    if scoreboard.threshold.get(guild['GUILD_ID'], None):
                        threshold = int(scoreboard.threshold.get(guild['GUILD_ID'], None))
                        if threshold > 0:
                            msg_thres = await ctx.send(content=f"Let's see who didn't score well, hmmmm..")
                            message = f"### Threshold mark is **{threshold}**\n\n"
                            index = 0

                            for member_score in record:
                                if int(member_score['RE_SCORE']) < threshold:
                                    targeted = ctx.guild.get_member(int(member_score['MEMBER_ID']))
                                    if targeted is not None:
                                        message += f"{targeted.mention}, your score `{str(member_score['RE_SCORE'])}` is below the threshold mark!!\n"
                                        index += 1
                                
                            await msg_thres.delete()
                            if index > 0:
                                await ctx.send(content=message)
                            else:
                                await ctx.send(content="Seem like everyone here hit the minimum requirement. Goodjob everyone!!")
                await msg_cal.delete()

    @scoreboard.command(name='show', description="Show the score of the targeted user or a full list of members' score of the event. ")
    @app_commands.describe(option="To show member or raid scoreboard")
    @app_commands.describe(sort="The criteria to sort the result")
    @app_commands.describe(event="The raid event name.")
    @app_commands.describe(show_summary="Whether to show the summary page")
    @app_commands.rename(event="raid")
    @app_commands.rename(show_summary="show-summary")
    @app_commands.autocomplete(option=show_option_options)
    @app_commands.autocomplete(sort=sorting_options)
    async def show(self, ctx: discord.Interaction|commands.Context, option:str, sort:str = "rank", event: str = None, member: discord.Member = None, show_summary: bool = True):
        """
        Show the score of the targeted user or a full list of members' score of the event. 
        To show the member score, use "show member <@mention>" or use "show myscore" to listdown all events you had participated. To show the event score, use "show [eventname]"
        """
        self.logger.debug("===== scoreboard :: show-scoreboard =====")

        ctx = await context(ctx)
        scoreboard: ScoreboardRecord = self.get_scoreboard(ctx)

        show_in_single_page = 10
        check_event = False
        member_ = ["member", "myscore"]
        if not option in member_:
            if option == 'raid' and event is None:
                if scoreboard.is_active:
                    await self.__check_current_active_event(ctx)
                    event = scoreboard.current_event
                else:
                    exist, result = self.__get_latest_raid()
                    if exist == 0:
                        return await ctx.send(embed=discord.Embed(title="", description=f"there has no available event", color=discord.Color.from_rgb(255, 170, 204)))

                    event = (result[0].get('ID'), result[0].get('R_NAME'))
            check_event = True
        
        has_mention = member is not None
        if option == "myscore" or (option == "member" and not has_mention):
            member = ctx.author
        elif option == "member" and has_mention:
            pass

        if True:
            embeds = []
            if check_event:
                exist, result = raw(f"SELECT BRR.ID, BRR.R_SEASON, BR.R_NAME AS BOSS, BR.R_NAME || ' S-' || BRR.R_SEASON AS R_NAME, (SELECT DESCRIPTION FROM MISC WHERE TYPE = 'R_TYPE' AND NAME = UPPER(BRR.R_TYPE)) AS I_TYPE, BRR.R_TYPE, BRR.R_START_DATE FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID WHERE BR.R_NAME || ' S-' || BRR.R_SEASON = '{event[1]}';")[1:]
                if exist == 0:
                    return await ctx.send(embed=discord.Embed(title="", description=f"the event with name, `{event[1]}` not found", color=discord.Color.from_rgb(255, 170, 204)))
                
                if show_in_single_page > 20:
                    return await ctx.send(embed=discord.Embed(title="", description=f"the maximum records can be shown in a single page is 20.", color=discord.Color.from_rgb(255, 170, 204)))
                elif show_in_single_page < 1:
                    return await ctx.send(embed=discord.Embed(title="", description=f"the request shows of records failed, 1 is the minimum value.", color=discord.Color.from_rgb(255, 170, 204))) 
                
                number_of_members_participated, scorelist = raw(f"SELECT RM.MEMBER_ID, GM.MEMBER_IGN, RE_SCORE, RE_RANK, RE_DIFFICULTY, RE_TIMING FROM BA_RAID_MEMBER RM INNER JOIN BA_GUILD_MEMBER GM ON RM.MEMBER_ID = GM.MEMBER_ID WHERE SERVER_ID = '{ctx.guild.id}' AND RE_ID = '{result[0].get('ID')}' ORDER BY {'GM.MEMBER_IGN' if sort == 'name' else 'RM.RE_SCORE DESC'};")[1:]
                if number_of_members_participated == 0:
                    return await ctx.send(embed=discord.Embed(title="", description=f"there has no member submitted score for this raid", color=discord.Color.from_rgb(255, 170, 204))) 

                userscore = {i.get('MEMBER_IGN'): f"{i.get('RE_RANK')}#{i.get('RE_SCORE')}" for i in scorelist}
                raid_name = result[0].get('R_NAME')
                raid_start_date = datetime.strptime(get_date(result[0].get('R_START_DATE')), '%Y-%m-%d').strftime('%d-%b-%Y')

                ### Summary Page
                summary_embed = discord.Embed(title=f":bookmark_tabs: Raid Scoreboard Summary", description=f"The summary of the scoreboard for event `{result[0].get('R_NAME')}`:",  color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())

                summary_embed.add_field(name=":tada: Name", value=f"{raid_name} {result[0].get('I_TYPE')}")
                summary_embed.add_field(name=":calendar_spiral: Date", value=f"{raid_start_date}")
                summary_embed.add_field(name=":busts_in_silhouette: Total Participants", value=f"{number_of_members_participated}")
                summary_embed.add_field(name="", value="\b", inline=False)

                ### get top three rank in the scoreboard
                filtered_user = {k: v for k, v in userscore.items() if v}
                filtered_user_score = {k: int(v.split("#")[1]) for k, v in filtered_user.items() if v}
                filtered_user_rank = {k: int(v.split("#")[0]) for k, v in filtered_user.items() if v}
                sorted_from_highest_score = sorted(filtered_user_score.items(), key=lambda x:x[1])
                sorted_from_highest_score.reverse()
                
                top_3 = sorted_from_highest_score[:3]
                
                # perform sort
                if sort == 'name':
                    myKeys = list(userscore.keys())
                    myKeys.sort()
                    userscore = {i: userscore[i] for i in reversed(myKeys)}
                elif sort == 'rank':
                    tuserscore = {}
                    for k,v in sorted_from_highest_score:
                        tuserscore[k] = userscore.get(k)
                    ftuserscore = {k:v for (k,v) in userscore.items() 
                        if tuple(sorted(v)) not in [tuple(sorted(x)) for x in tuserscore.values()]} 
                    userscore = {**tuserscore, **ftuserscore}
                    userscore = dict(reversed(list(userscore.items())))
                
                ### Summary Page - start
                if show_summary:
                    icon = [":first_place:",":second_place:",":third_place:"]
                    top_3_str = ""
                    for uname, rankscore in top_3:
                        top_3_str += f"{icon.pop(0)} **{uname}** @ **{filtered_user_rank.get(uname)}#{rankscore}**\n"

                    summary_embed.add_field(name="Top Champions", value=top_3_str, inline=False)
                    summary_embed.add_field(name="", value="\b", inline=False)

                    uname, rankscore = top_3[0]
                    summary_embed.add_field(name="Top Scorer", value=f":confetti_ball: Congrats `{uname}` dominates the scoreboard with score of `{rankscore}`!!", inline=False)
                    summary_embed.add_field(name="", value="\b", inline=False)

                    summary_embed.set_footer(text="The scoreboard is dated upto the execution of commands, the leaderboard may differ after the finalise of scoreboard.")

                    embeds.append(summary_embed)
                ### Summary Page - end

                page_limit = 12
                total_pages = math.ceil(number_of_members_participated/ page_limit)
                for i in range(total_pages):
                    # Header
                    embed = discord.Embed(title=f":bookmark: Raid Scoreboard", description=f"⤖ {raid_start_date} {result[0].get('I_TYPE')} {result[0].get('BOSS')} ({result[0].get('R_SEASON')})", color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
                    embed.add_field(name=f"Sort by: **{sort.title()}**", value="", inline=False)
                    # embed.add_field(name=":tada: Name", value=f"{raid_name}")
                    # embed.add_field(name=":calendar_spiral: Date", value=f"{raid_start_date}")
                    # embed.add_field(name=":busts_in_silhouette: Total Participants", value=f"{number_of_members_participated}")
                    # embed.add_field(name="", value="\b", inline=False)

                    s_list = ""

                    record= []

                    m_pad_member = -1
                    m_pad_score = -1
                    for y in range(page_limit):
                        u, s = userscore.popitem()
                        lsr = s.split("#")
                        m_pad_member = len(u) if len(u) > m_pad_member else m_pad_member
                        if len(lsr) == 2:
                            rank = int(lsr[0])
                            score = str('{:,}'.format(int(lsr[1])))
                            rank_icon = ""
                            if rank <= 15000: 
                                rank_icon = "<:ba_rank_plat:1136568139702882366>"
                            elif rank > 15000 and rank <= 80000:
                                rank_icon = "<:ba_rank_gold:1136568105452179456>"
                            elif rank > 80000 and rank <= 180000:
                                rank_icon = "<:ba_rank_silv:1136568062041137202>"
                            else:
                                rank_icon = "<:ba_rank_brz:1136568021113126922>"
                            record.append({
                                "member": u,
                                "rank_icon": rank_icon,
                                "rank": str(rank),
                                "score": score
                            })
                            m_pad_score = len(score) if len(score) > m_pad_score else m_pad_score

                        if y == page_limit - 1 or len(userscore) == 0:
                            s_list = '\n'.join(f"`{_['member'].ljust(m_pad_member, ' ')}` {_['rank_icon']} `{_['rank'].rjust(6, ' ')}` ▪ `{_['score'].rjust(m_pad_score, ' ')}`" for _ in record)
                            embed.add_field(name="", value=s_list)
                            break
                    
                    embed.add_field(name="", value="\b", inline=False)
                    embed.set_footer(text=f"Page {i + 1} of {total_pages} | Chronus@Chronius scoreboard")
                    embeds.append(embed)
            else:
                userid = member.id
                username = self.__get_ign_or_default(userid, member.name)

                targeted_user: discord.User = ctx.message.author
                display_name = self.__get_ign_or_default(targeted_user.id, targeted_user.name)

                if event is not None:
                    exist, tevent = raw(f"SELECT BR.R_NAME || ' S-' || BRR.R_SEASON AS R_NAME, (SELECT DESCRIPTION FROM MISC WHERE TYPE = 'R_TYPE' AND NAME = UPPER(BRR.R_TYPE)) AS I_TYPE, BRR.R_TYPE, BRR.R_START_DATE, BRM.RE_SCORE, BRM.RE_RANK FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID INNER JOIN BA_RAID_MEMBER BRM ON BRM.RE_ID = BRR.ID WHERE BRM.MEMBER_ID = '{userid}' AND BR.R_NAME || ' S-' || BRR.R_SEASON = '{event}';")[1:]
                    if exist == 0:
                        return await ctx.send(embed=discord.Embed(title="", description=f"the event with name, `{event}` not found", color=discord.Color.from_rgb(255, 170, 204)))
                    
                    self.logger.info(f"user {username} checking for event {event}")

                    score = tevent[0].get('RE_SCORE')
                    rank = tevent[0].get('RE_RANK')

                    ### directly return score for the user 
                    embed = discord.Embed(title="", 
                                          description=f"{'Your' if userid == targeted_user.id else member.mention} score in raid `{event}` is `{str(score)}` at rank `{str(rank)}`", 
                                          color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
                    embed.set_author(name=f"Hi {display_name} sensei", icon_url=ctx.author.avatar)
                    embed.set_footer(text=f"AiriBot @ {ctx.guild.name} | EN", icon_url=self.bot.user.avatar)
                    return await ctx.send(embed=embed)

                participated_raid, result = raw(f"SELECT BR.R_NAME || ' S-' || BRR.R_SEASON AS R_NAME, (SELECT DESCRIPTION FROM MISC WHERE TYPE = 'R_TYPE' AND NAME = UPPER(BRR.R_TYPE)) AS I_TYPE, BRR.R_TYPE, BRR.R_START_DATE, BRM.RE_SCORE, BRM.RE_RANK FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID INNER JOIN BA_RAID_MEMBER BRM ON BRM.RE_ID = BRR.ID WHERE BRM.MEMBER_ID = '{userid}';")[1:]

                if participated_raid == 0:
                    embed = discord.Embed(title=f"Hi {display_name} sensei", 
                                          description=f"He/she not participate in any raid or have not been submit any score yet", 
                                          color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now(), icon_url=targeted_user.avatar)
                    embed.set_footer(text=f"AiriBot @ {ctx.guild.name} | EN", icon_url=self.bot.user.avatar)
                    return await ctx.send(embed=embed)
                
                scores = [events.get('RE_RANK') for events in result]
                average = int(sum(scores) / len(scores) if len(scores) > 0 else 0)

                events_date = {i.get('R_NAME'): i.get('R_START_DATE') for i in result}
                events_scores = {i.get('R_NAME'): str(i.get('RE_RANK')) + '#' + str(i.get('RE_SCORE')) for i in result}

                ### 
                # Summary page including information such as 
                # - times being scoreboard leader
                # - numbers of event participated
                # - the best 3 position among the server
                ### Summary Page
                if show_summary:
                    summary_embed = discord.Embed(title=f":bookmark_tabs: {username}'s Scoreboard Summary", description=f"The summary of the scoreboard in the server for `{username}`:",  color=member.color, timestamp=datetime.now())

                    
                    summary_embed.add_field(name=":ticket: First Participated Raid", value=f"{result[0].get('R_NAME')} {result[0].get('I_TYPE')}", inline=False)
                    summary_embed.add_field(name=":clipboard: Total Participated Raid", value=f"{participated_raid}", inline=False)
                    summary_embed.add_field(name=":label: Average Rank", value=f"{average}", inline=False)
                    summary_embed.add_field(name="", value="\b", inline=False)

                    summary_embed.set_footer(text=f"AiriBot @ {ctx.guild.name} | EN", icon_url=self.bot.user.avatar)
                    
                    embeds.append(summary_embed)
                ### Summary Page

                ### list all the score of the event this user had participated
                page_limit = 12
                total_events = len(events_scores)
                total_pages = math.ceil(total_events / page_limit)
                n = 1
                for i in range(total_pages):
                    # Header
                    embed = discord.Embed(title="", 
                                          description=f"Raid score for `{display_name}`", 
                                          color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
                    embed.set_author(icon_url=targeted_user.avatar, name=f"Hi {display_name} sensei!!")

                    s_list = ""

                    record= []

                    m_pad_event = -1
                    m_pad_score = -1
                    for y in range(page_limit):
                        e, s = events_scores.popitem()
                        lsr = s.split("#")
                        date = datetime.strptime(get_date(events_date.get(e)), '%Y-%m-%d').strftime("%d-%b-%Y")
                        if len(lsr) == 2:
                            rank = int(lsr[0])
                            score = str('{:,}'.format(int(lsr[1])))
                            rank_icon = ""
                            if rank <= 15000: 
                                rank_icon = "<:ba_rank_plat:1136568139702882366>"
                            elif rank > 15000 and rank <= 80000:
                                rank_icon = "<:ba_rank_gold:1136568105452179456>"
                            elif rank > 80000 and rank <= 180000:
                                rank_icon = "<:ba_rank_silv:1136568062041137202>"
                            else:
                                rank_icon = "<:ba_rank_brz:1136568021113126922>"
                            record.append({
                                "index": n,
                                "date": date,
                                "type": "",
                                "event": e,
                                "rank_icon": rank_icon,
                                "rank": str(rank),
                                "score": score
                            })
                            m_pad_event = len(e) if len(e) > m_pad_event else m_pad_event
                            m_pad_score = len(score) if len(score) > m_pad_score else m_pad_score

                            n += 1
                        
                        s_list = '\n'.join(f"`{_['index']}|{_['date']}|{_['event'].ljust(m_pad_event, ' ')}` {_['rank_icon']} `{_['rank'].rjust(6, ' ')}` ▪ `{_['score'].rjust(m_pad_score, ' ')}`" for _ in record)

                        if y == page_limit - 1 or len(events_scores) == 0:
                            embed.add_field(name="", value=s_list)
                            break

                    # Footer
                    embed.add_field(name="", value="\b", inline=False)
                    embed.set_footer(text=f"Page {i + 1} of {total_pages} | Chronus@Chronius scoreboard", icon_url=self.bot.user.avatar)
                    embeds.append(embed)
            await page.EmbedPaginator(timeout=180).start(ctx, pages=embeds)

    @scoreboard.command(name='did-not-submit', description="List down all of the members not submit the score.")
    @app_commands.describe(raid="Default will be current active event")
    async def not_submit(self, ctx: discord.Interaction|commands.Context, raid: str = None):
        """List down all of the members not submit the score."""
        self.logger.debug("===== scoreboard :: list-not-submit-score =====")

        ctx = await context(ctx)
        scoreboard: ScoreboardRecord = self.get_scoreboard(ctx)

        embed = discord.Embed(color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
        embed.set_author(name=f"Hi {self.__get_ign_or_default(ctx.author.id, ctx.author.display_name)} sensei！", icon_url=ctx.author.avatar)
        embed.set_footer(icon_url=self.bot.user.avatar, text=f"AiriBot @ {ctx.guild.name} | EN")

        if raid is None:
            if scoreboard.current_event is None:
                embed.description = f"there has no available raid"
                return await ctx.send(embed=embed)
            raid = scoreboard.current_event[1]

        exist, result = raw(f"SELECT BRR.ID FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID WHERE BR.R_NAME || ' S-' || BRR.R_SEASON = '{raid}';")[1:]
        if exist == 0:
            embed.description = f"unable to find raid named **{raid}**"
            return await ctx.send(embed=embed)
                
        row, un_members = raw(f"SELECT GM.MEMBER_ID FROM BA_GUILD_MEMBER GM WHERE GM.MEMBER_ID NOT IN ( SELECT RM.MEMBER_ID FROM BA_RAID_MEMBER RM WHERE RE_ID = '{result[0].get('ID')}' ) AND GM.SERVER_ID = {ctx.guild.id}")[1:]
        if row == 0:
            embed.description = f"seem like everyone submitted their score accordingly"
            return await ctx.send(embed=embed)
        
        embeds = []
        embed.description = "These are the members which not submit the raid score"

        for s in un_members:
            std = ''
            page_limit = 30
            page_embed = copy.deepcopy(embed)
            page_embed.add_field(name="", value="\b", inline=False)
            single_page_records = page_limit if len(un_members) >= page_limit else len(un_members)
            n = math.ceil(single_page_records / 2)
            for i in range(single_page_records):
                member_data = un_members.pop()
                member = member_data.get('MEMBER_ID')
                std += f"<@{member}>\n"
                if i + 1 in (n, single_page_records):
                    page_embed.add_field(name="", value=std)
                    std = ''
            page_embed.add_field(name="", value="\b", inline=False)
            embeds.append(page_embed)

        await page.EmbedPaginator(ephemeral=True, timeout=180).start(ctx, pages=embeds)

    @scoreboard.command(name='list-raid', description="List down all of the raid events created.")
    async def list_events(self, ctx: discord.Interaction|commands.Context):
        """List down all of the events created. """
        self.logger.debug("===== scoreboard :: list-events =====")

        ctx = await context(ctx)
        result = await self.__list_event_method(ctx)
        if isinstance(result, discord.Embed):
            await ctx.send(embed=result)
        else:
            await page.EmbedPaginator(ephemeral=True, timeout=180).start(ctx, pages=result)

    @scoreboard.command(name='download', description="Download the scorelist")
    async def download_scorelist(self, ctx: discord.Interaction|commands.Context):
        """Download the scorelist"""
        self.logger.debug("===== scoreboard :: download-scorelist =====")

        ctx = await context(ctx)
        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)

        row, raid = raw("SELECT DISTINCT BR.R_NAME || ' S-' || BRR.R_SEASON AS RAID, BRR.R_START_DATE FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID_MEMBER RM ON RM.RE_ID = BRR.ID INNER JOIN BA_RAID BR ON BR.ID = BRR.R_ID ORDER BY BRR.R_SEASON")[1:]
        header = [['',''] + [r.get('RAID') for r in raid], ['Name','Club'] + [datetime.strptime(get_date(r.get('R_START_DATE')), '%Y-%m-%d').strftime('%d-%b-%Y') for r in raid]]
        raid_pos = {r.get('RAID'): index + 2 for index, r in enumerate(raid)}

        row, data = raw(f"SELECT GM.MEMBER_IGN AS NAME, G.GUILD_NAME AS CLUB, BR.R_NAME || ' S-' || BRR.R_SEASON AS RAID, RE_SCORE AS SCORE, RE_RANK AS RANK FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID_MEMBER RM ON RM.RE_ID = BRR.ID INNER JOIN BA_RAID BR ON BR.ID = BRR.R_ID INNER JOIN BA_GUILD_MEMBER GM ON GM.MEMBER_ID = RM.MEMBER_ID INNER JOIN BA_GUILD G ON G.GUILD_ID = GM.GUILD_ID WHERE G.SERVER_ID = {ctx.guild.id} ORDER BY BRR.R_END_DATE, GM.GUILD_ID, GM.MEMBER_IGN;")[1:]
        formated = {}
        for d in data:
            add_to_nested_dict(formated, [(d.get('NAME'), d.get('CLUB')), d.get('RAID')], f"{d.get('RANK')}#{d.get('SCORE')}")

        data = []
        for k, v in formated.items():
            row_data = [k[0], k[1]] + ([None] * (len(raid_pos)))
            for raid, score in v.items():
                row_data.insert(raid_pos.get(raid), score)
            data.append(row_data)

        data = header + data
        filename = f'temp/{ctx.guild.name.lower()}_scoreboard_{datetime.now().date()}.xlsx'
        generate_excel([f'Generated at {datetime.now()}'], data, filename)

        embed = discord.Embed(color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
        embed.set_author(name=f"Hi {self.__get_ign_or_default(ctx.author.id, ctx.author.display_name)} sensei！", icon_url=ctx.author.avatar)
        embed.set_footer(icon_url=self.bot.user.avatar, text=f"AiriBot @ {ctx.guild.name} | EN")

        embed.description = f"Here is the latest scorelist ~"
        return await response(ctx, embed=embed, file=discord.File(filename))
            
    # region scoreboard settings
    
    setting = app_commands.Group(name="setting", description="scoreboard setting for permitted roles and users", parent=scoreboard)

    @setting.command(name='threshold', description="set the minimum threshold for the scoreboard. ")
    @app_commands.autocomplete(club=clubs_options)
    @app_commands.describe(score="The minumum score for the threshold")
    @app_commands.describe(club="The club to update the threshold score, if not provided will applied for all")
    async def set_threshold_score(self, ctx: discord.Interaction|commands.Context, score: int, club: int = 0):
        """set the minimum threshold for the scoreboard. 
        If a member who participated has lower than threshold, the bot will mention the member during closing"""
        self.logger.debug("===== scoreboard :: scoreboard-threshold =====")
        
        ctx = await context(ctx)
        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
        
        scoreboard: ScoreboardRecord = self.get_scoreboard(ctx)

        raw(f"UPDATE BA_GUILD SET RAID_THRESHOLD = '{score}' WHERE SERVER_ID = '{ctx.guild.id}' {'AND GUILD_ID = ' + str(club) if not club == 0 else ''}")
        self.update_setting(ctx.guild.id, scoreboard)
        
        await ctx.send(embed=discord.Embed(title="", description=f"The threshold score had been updated to `{str(score)}`", color=discord.Color.from_rgb(255, 170, 204)))

    @setting.command(name='default-role', description="Set the default role for top scorer")
    @app_commands.autocomplete(club=clubs_options)
    @app_commands.describe(role="The default role to be assigned to the top scorer after the raid event declare close")
    @app_commands.describe(club="The club to update, if not provided will applied for all")
    async def set_default_leaderboard_role(self, ctx: discord.Interaction|commands.Context, role: discord.Role, club: int = 0):
        """set the default role for top scorer
        , the role will be assigned to the top scorer after the event declare close"""
        self.logger.debug("===== scoreboard :: scoreboard-default-role =====")
        
        ctx = await context(ctx)
        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
            
        scoreboard = self.get_scoreboard(ctx)
                
        d_role = scoreboard.default_award_rank.get(club)
        self.logger.debug(d_role)
        if d_role is not None:
            t_role = ctx.guild.get_role(int(d_role))
            
            # ask user whether want to overwrite it
            msg: discord.Message = await ctx.send(f"There is a default top scorer role in records ({t_role.name}).\n Do you want to overwrite it?") 
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            def is_owner(reaction, user):
                if reaction.message.id == msg.id and not user.id == ctx.author.id:
                    return False
                if reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '❌':
                    raise CancelledAction("canceled, user reacted with ❌")
                return reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '✅'
            try:
                respond = await self.bot.wait_for('reaction_add', check=is_owner)

                raw(f"UPDATE BA_GUILD SET RAID_TOP_ROLE = '{role.id}' WHERE SERVER_ID = '{ctx.guild.id}' {'AND GUILD_ID = ' + str(club) if not club == 0 else ''}")
                self.update_setting(ctx.guild.id, scoreboard)
                await msg.delete()
                return await ctx.send(embed=discord.Embed(title="", description=f"The default top scorer's role had been updated to `{role.name}`", color=discord.Color.from_rgb(255, 170, 204)))
            except CancelledAction:
                return await ctx.send(f"the request to had been cancelled") 
            except Exception as error:
                self.logger.debug(error)
                return await ctx.send(f"something gone wrong") 

        raw(f"UPDATE BA_GUILD SET RAID_TOP_ROLE = '{role.id}' WHERE SERVER_ID = '{ctx.guild.id}' {'AND GUILD_ID = ' + club if not club == 0 else ''}")
        self.update_setting(ctx.guild.id, scoreboard)
        await ctx.send(embed=discord.Embed(title="", description=f"The default top scorer's role had been updated to `{role.name}`", color=discord.Color.from_rgb(255, 170, 204)))
    
    @scoreboard.command(name='listening', description="Enable the score listening in current channel")
    @app_commands.describe(option="on or offf the listening")
    @app_commands.autocomplete(option=listening_options)
    async def enable_listening_score(self, ctx: discord.Interaction|commands.Context, option: str):
        """enable the score listening"""
        self.logger.debug("===== scoreboard :: scoreboard-listening =====")
        
        ctx = await context(ctx)
        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)

        scoreboard = self.get_scoreboard(ctx)
        try:
            options_positive = ['on', 'enable', 'en']
            options_negative = ['off', 'disable']
            options = ['off', 'disable', 'on', 'enable', 'en']
            if option not in options:
                raise ValueError("Invalid option. Expected one of: %s" % options)
            if option in options_positive:
                if scoreboard.score_listening:
                    return await ctx.send(f"The listener is running..")

                # TODO: Ask user to activate event if the status is not active
                if not await self.__check_current_active_event(ctx):
                    msg: discord.Message = await ctx.send(embed=discord.Embed(title="", description="Seem like there isn't any active raid at the moment, would you like to set the latest raid to active? " +
                                                           "\n\nReact on ✅ for activate latest raid, react on ❌ to cancel the action.", color=discord.Color.from_rgb(255, 170, 204)), 
                                                           ) 
                    await msg.add_reaction("✅")
                    await msg.add_reaction("❌")
                    def is_owner(reaction, user):
                        if reaction.message.id == msg.id and not user.id == ctx.author.id:
                            return False
                        if reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '❌':
                            raise CancelledAction("canceled, user reacted with ❌")
                        return reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '✅'
                    def check(m):
                        if m.author == ctx.author and m.reference is not None:
                            if m.reference.message_id == msg.id:
                                return True
                        return False
                    try:
                        done, pending = await asyncio.wait([
                            self.bot.loop.create_task(self.bot.wait_for('message', check=check)),
                            self.bot.loop.create_task(self.bot.wait_for('reaction_add', check=is_owner))
                        ], return_when=asyncio.FIRST_COMPLETED)

                        await msg.delete()
                        exist, result = self.__get_latest_raid()
                        if exist == 0:
                            return await ctx.send(embed=discord.Embed(title="", description=f"there has no available event to be activated", color=discord.Color.from_rgb(255, 170, 204)))

                        scoreboard.current_event = (result[0].get('ID'),result[0].get('R_NAME'))
                        scoreboard.is_active = True
                    except CancelledAction:
                        return await ctx.send(embed=discord.Embed(title="", description=f"The listener had not been started", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True) 
                    except Exception as error:
                        self.logger.debug(error)
                        return await ctx.send(embed=discord.Embed(title="", description=f"Something went wrong", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True) 

                scoreboard.score_listening = True
                scoreboard.listening_channel = ctx.channel
                await ctx.send(embed=discord.Embed(title="", description=f"Start listening to incoming message at `{scoreboard.listening_channel.name}` to handle score update", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
            else:
                if not scoreboard.score_listening:
                    return await ctx.send(embed=discord.Embed(title="", description=f"The listener is not running..", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
                scoreboard.score_listening = False
                scoreboard.listening_channel = None
                await ctx.send(embed=discord.Embed(title="", description=f"The listener had been stopped", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send(embed=discord.Embed(title="", description=f"Failed to start listener", color=discord.Color.from_rgb(255, 170, 204)))
            scoreboard.score_listening = False
            scoreboard.listening_channel = None
    
    @commands.Cog.listener()
    async def on_message(self, message :discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)
        
        if not message.author.bot and ctx.guild.id in self.scoreboard:
            scoreboard = self.get_scoreboard(ctx)
            if not message.content.startswith("scoreboard!") and scoreboard.score_listening and message.channel == scoreboard.listening_channel:
                attch = None
                if validators.url(message.content) and message.content.split("?")[0].endswith(('.jpg', '.png', '.gif', '.jpeg')):
                    attch = message.content
                elif message.attachments:
                    attch = message.attachments
                    
                if attch is not None:
                    await self.score_method(ctx, image=attch)

    @scoreboard.command(name='scan', description="Automatically scanning the channel and update the score from the channel")
    @app_commands.describe(message_limit="the message limit to scan for update the score")
    @app_commands.rename(message_limit="message-limit")
    async def set_score_in_channel(self, ctx: discord.Interaction|commands.Context, message_limit: int = 200):
        """Automatically scanning the channel and update the score
         by using command \"scoreboard!auto_score [optonal:message_limit(number)]\""""
        self.logger.debug("===== scoreboard :: auto-score =====")
        
        ctx = await context(ctx)
        if not await self.permitted_to_execute(ctx):
            return await response(ctx,embed=discord.Embed(title="", description=f"you do not have permission to execute this command", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)

        ### check if there is active current event
        scoreboard = self.get_scoreboard(ctx)
        if scoreboard == None or not await self.__check_current_active_event(ctx):
            return

        involve = 0
        success = 0
        channel = ctx.message.channel
        msg_str = "Start lookup for messages contains image and attempting to update score"
        msg_body_attp = ""
        msg = await ctx.send("Start lookup for messages contains image and attempting to update score")
        async for message in channel.history(limit=message_limit):
            # do something with all messages
            targeted_user = message.author
            if message.attachments:
                involve += 1

                try:
                    score, rank = self.__extract_score_from_image(message.attachments)
                    score = str(score).replace(',', '')
                    #check if the user exist in the sheet
                    userid = targeted_user.id
                    username = targeted_user.name
                    self.logger.debug(f"update score :: {userid} {username} {score}")

                    rank = str(rank)
                    score = str(score)

                    affect = raw(f"INSERT OR REPLACE INTO BA_RAID_MEMBER (MEMBER_ID, RE_ID, RE_SCORE, RE_RANK, RE_DIFFICULTY)VALUES ('{userid}', '{scoreboard.current_event[0]}', '{score}', '{rank}', '5');")[1]

                    msg_str += f"\n- Succesfully update {targeted_user.mention}'s score to `{score}` {' at `rank:' + rank + '`' if not rank == None else ''}"
                    await msg.edit(content=f"{msg_str}\n{msg_body_attp}")
                    success += 1
                except:
                    ## send alert
                    await message.reply(content=f"{targeted_user.mention}, unable to update your score, maybe it is due to I cannot understand the image")
 
        msg_str = f"{msg_str}\n{msg_body_attp}\n{success} success out of {involve} attempts"
        await msg.edit(content=msg_str)
    # endregion

    # region local functions
    async def __list_event_method(self, ctx) -> discord.Embed | list[discord.Embed]:
        ctx = await context(ctx)
        scoreboard = self.get_scoreboard(ctx)
        total_events, raids = raw("SELECT BRR.ID, BR.R_NAME || ' S-' || BRR.R_SEASON AS R_NAME, BRR.R_TYPE, (SELECT DESCRIPTION FROM MISC WHERE TYPE = 'R_TYPE' AND NAME = UPPER(BRR.R_TYPE)) AS TYPE, R_START_DATE FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID ORDER BY R_START_DATE;")[1:]

        tembed = discord.Embed(color=discord.Color.from_str('#02D3FB'), title="Raid List")
        tembed.set_author(name=f"Hi {self.__get_ign_or_default(ctx.author.id, ctx.author.display_name)} sensei！", icon_url=ctx.author.avatar)
        tembed.set_footer(icon_url=self.bot.user.avatar, text=f"AiriBot @ {ctx.guild.name} | EN")

        if total_events > 0:
            page_limit = 12
            total_pages = math.ceil(total_events / page_limit)
            
            embeds = []
            index = 1
            for i in range(total_pages):
                embed = copy.deepcopy(tembed)
                embed.description=f"{'The current active raid is `' + scoreboard.current_event + '`' if scoreboard.current_event is not None else 'There has no current **active raid** at the moment.'}"
                embed.add_field(name="", value="\b", inline=False)
                m_pad_raid = -1
                result = []
                for y in range(page_limit):
                    raid = raids.pop(-1)
                    raid_name = raid.get('R_NAME')
                    raid_start_date = datetime.strptime(get_date(raid.get('R_START_DATE')), '%Y-%m-%d').strftime('%d-%b-%Y')

                    m_pad_raid = len(raid_name) if len(raid_name) > m_pad_raid else m_pad_raid

                    result.append({
                        "index": index,
                        "name": raid_name,
                        "type": raid.get('TYPE'),
                        "start": raid_start_date
                    })
                    index += 1

                    if y == page_limit - 1 or len(raids) == 0:
                        embed.add_field(name="", value='\n'.join(f"`{str(_['index']).rjust(3, '0')}|{_['name'].ljust(m_pad_raid, ' ')}`|{_['type']}|`{_['start']}`" for _ in result))
                        break
                    
                embed.add_field(name="", value="\b", inline=False)
                embed.set_footer(text=f"Page {i + 1} of {total_pages} | Chronus@Chronius scoreboard")
                embeds.append(embed)
            return embeds
        else:
            embed = copy.deepcopy(tembed)
            embed.add_field(name="", value="\b", inline=False)
            embed.add_field(name="", value="*There has no raid created*", inline=False)
            return embed

    async def __check_current_active_event(self, ctx) -> bool:
        scoreboard = self.get_scoreboard(ctx)
        if not scoreboard.is_active:
            await ctx.send(embed=discord.Embed(title="", description=f"there has no active event at the moment", color=discord.Color.from_rgb(255, 170, 204)))
            return False
        return True

    def __extract_score_from_image(self, args):
        score = 0
        rank = 0
        found_rank = False
        found_score = False

        image_url = None
        if isinstance(args, list):
            for att in args:
                if att.content_type.startswith("image"):
                    image_url = att.url
                    break
        elif isinstance(args, str):
            image_url = args
        else:
            image_url = args.url

        result = ocr.extract_from_image(image_url, 0, 0, 100, 650, True, output=ocr.Output.LIST)
        self.logger.debug(f"result :: {result}")
        for d in result:
            red = re.findall(r"^(rank)[\s+](\d*)", d, flags=re.IGNORECASE)
            if red:
                rank = red[0][1]
                found_rank = True
                break
            
        for d in result: 
            red = re.findall(r"^(\d+|\d{1,3}(,\d{3})*)(\.\d+)?$", d, flags=re.IGNORECASE)
            if red:
                score = red[0][0]
                found_score = True
                break
            
        self.logger.debug(f"rank :: {rank}, score :: {score}")
            
        tscore = str(score).replace(',', '')
        try:
            if int(tscore) < 1000000:
                raise ScoreOrRankExtractionError("score retrieval on invalid value")
        except Exception as error:
            raise ScoreOrRankExtractionError("score retrieval on invalid value")
        if not found_rank:
            raise ScoreOrRankExtractionError("failed to extract rank from provided image!!")
        if not found_score:
            raise ScoreOrRankExtractionError("failed to extract score from provided image!!")
        return (score, rank)
    
    def __get_list_item(self, list: list, index, default=None):
        try:
            return list[index]
        except IndexError:
            return default
        
    def __get_ign_or_default(self, userid, default):
        r, result = raw(f'SELECT MEMBER_IGN FROM BA_GUILD_MEMBER WHERE MEMBER_ID = {userid}')[1:]
        if not r == 0:
            return result[0].get('MEMBER_IGN', default)
        return default
    
    def check_similar(self, input, list, similarity_percentage) -> str:
        best_match, similarity = process.extractOne(input, list)
        self.logger.debug(f"input :: {input}, best match :: {best_match}, similarity :: {similarity}")
        return best_match if similarity >= similarity_percentage else None
    
    def __get_latest_raid(self):
        return raw(f"SELECT BRR.ID, BR.R_NAME || ' S-' || BRR.R_SEASON AS R_NAME, BRR.R_TYPE FROM BA_RAID_RECORD BRR INNER JOIN BA_RAID BR ON BRR.R_ID = BR.ID WHERE R_START_DATE < DATE('now') ORDER BY R_START_DATE DESC LIMIT 1;")[1:]        
    
    # endregion

class ScoreOrRankExtractionError(Exception):
    pass

class CancelledAction(Exception):
    # handle exception for cancelled action from user
    pass

async def setup(bot):
    await bot.add_cog(Scoreboard(bot))