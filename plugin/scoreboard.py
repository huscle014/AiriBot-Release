import discord
from discord.ext import commands
from discord.utils import get

import traceback
import sys
from datetime import date, datetime
import math
import asyncio

import utils.google.gsheet as gs
from utils import logger
import utils.constant as const
import utils.ocr as ocr
from utils.cutils import is_date, get_date

from gspread_formatting import *
import Paginator
import validators

class ScoreboardRecord:

    __slots__ = ('bot', 'gsheet', 'current_event', 'is_active', 'worksheet', 'threshold', 'default_award_rank', 'score_listening', 'listening_channel')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self.gsheet = None
        self.current_event = None
        self.worksheet = None
        self.is_active = False
        self.threshold = 0
        self.default_award_rank = None
        self.score_listening = False
        self.listening_channel = None

class Scoreboard(commands.Cog):
    """Scoreboard related command."""

    __slots__ = ('bot', 'prefix')

    def __init__(self, bot):
        self.bot = bot
        self.scoreboard = {}
        self.prefix = 'scoreboard!'
        
    async def cog_check(self, ctx):
        return ctx.prefix == self.prefix

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

    def get_scoreboard(self, ctx):
        try:
            scoreboard = self.scoreboard[ctx.guild.id]
        except KeyError:
            scoreboard = ScoreboardRecord(ctx)
            self.scoreboard[ctx.guild.id] = scoreboard
            
        return scoreboard
    
    @commands.command(name='bind', aliases=['捆綁', 'link'], pass_context=True)
    async def bind(self, ctx, sheet: str = None):
        """
        Activate the API handle for scoreboard
        """

        try:
            async with ctx.typing():
                if sheet is None:
                    sheet = const.DEFAULT_SCOREBOARD_SHEET
                scoreboard = self.get_scoreboard(ctx)
                scoreboard.gsheet = gs.GSheet(sheet)
                scoreboard.worksheet = scoreboard.gsheet.check_if_exist(ctx.guild.name ,ctx.guild.id)

                tthreshold = scoreboard.worksheet.cell(1, 3).value
                scoreboard.threshold = 0 if tthreshold == None else tthreshold
                scoreboard.default_award_rank = scoreboard.worksheet.cell(1, 4).value
                scoreboard.worksheet.hide_columns(1, 2)
                
                await ctx.message.edit(suppress=True)

                # await ctx.send(embed=discord.Embed(title="", description=f"Successfully binded", color=discord.Color.from_rgb(255, 170, 204)))
        except Exception as e:
            logger.error(e)
            await ctx.send(embed=discord.Embed(title="", description=f"fail to bind, probably something wrong during API request", color=discord.Color.from_rgb(255, 170, 204)))

    @commands.command(name='create', aliases=['活動', 'event'], pass_context=True)
    async def create(self, ctx, name, date = str(date.today())):
        """
        Create an event. Use the command as "create [mandatory:name] [optional:date]". If the date is not provided as the parameter, the local current date will be use as default
        """

        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return

        try:
            scoreboard = self.get_scoreboard(ctx)
            eventlist = scoreboard.gsheet.get_row_values(scoreboard.worksheet, 2)
            if name in eventlist:
                await ctx.send(embed=discord.Embed(title="", description=f"the event with name `{name}` already existed", color=discord.Color.from_rgb(255, 170, 204)))
                ## ask if the user want to create with alt name
            else:
                if not is_date(date):
                    return await ctx.send(embed=discord.Embed(title="", description=f"the date provided is not a valid format", color=discord.Color.from_rgb(255, 170, 204)))
                date = get_date(date)
                index = 3 if len(eventlist) == 0 else len(eventlist) + 1
                scoreboard.worksheet.update_cell(2, index, name)
                namecell = gs.GSheet.get_cell_by_rowcol(2, index)
                scoreboard.worksheet.format(namecell, {'textFormat': {'bold': True}})

                scoreboard.worksheet.update_cell(3, index, date)
                scoreboard.current_event = name
                scoreboard.is_active = True
                await ctx.send(embed=discord.Embed(title="", description=f"the event, `{name}` had been created", color=discord.Color.from_rgb(255, 170, 204)))
        except Exception as e:
            raise 
    
    @commands.command(name='set', aliases=['新增分數', 'add_score'], pass_context=True)
    async def score(self, ctx, score = None, rank = None, member = None):
        """Set the score to the scoreboard. """

        ### check if there is active current event
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None or not await self.__check_current_active_event(ctx):
            return
        
        attch = None
        targeted_user = ctx.message.author
        mention_member = len(ctx.message.mentions) > 0
        member_mentioned = (user_mentioned.id for user_mentioned in ctx.message.mentions)
        if mention_member:
            targeted_user = await self.bot.fetch_user(ctx.message.mentions[0].id)
        if mention_member and ctx.message.reference is not None:
            # fetch reference message
            reply_to: discord.Message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            attch = reply_to.attachments

            if attch is None:
                return await ctx.reply(embed=discord.Embed(title="", description=f"the reference message didn't include an attachment", color=discord.Color.from_rgb(255, 170, 204)))

        elif mention_member and ctx.message.reference is None:
            if not score is None and not rank is None:
                pass
            else:
                return await ctx.reply(embed=discord.Embed(title="", description=f"hmmm seem like the way execute for this command is not correct", color=discord.Color.from_rgb(255, 170, 204)))
        elif validators.url(ctx.message.content) and ctx.message.content.endswith(('.jpg', '.png', '.gif', '.jpeg')):
            attch = ctx.message.content
        else:
            attch = ctx.message.attachments
        
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
                    msgscore: discord.Message = await ctx.reply(embed=embed)
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

                logger.debug(f"rank :: {rank}, score :: {score}")
        elif not attch and score == None:
            return await ctx.send(embed=discord.Embed(title="", description=f"unable to update score, the value is not provided", color=discord.Color.from_rgb(255, 170, 204)))
        
        score = str(score).replace(',', '')
        #check if the user exist in the sheet
        userid = targeted_user.id
        username = targeted_user.name
        user = scoreboard.gsheet.find_cell(scoreboard.worksheet, userid, in_column=2)
        logger.debug(f"update score :: {userid} {username} {score} {user}")
        
        row = 0
        if user is None:
            users = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 2)
            row = 4 if len(users) == 0 else len(users) + 1
            scoreboard.worksheet.update_cell(row, 1, username)
            scoreboard.worksheet.update_cell(row, 2, f"'{userid}")
        else:
            row = user.row

        # TODO: check if user permitted to update score (check by the color code?)
        usernamedcell = gs.GSheet.get_cell_by_rowcol(row, 2)
        usernote = scoreboard.worksheet.get_note(usernamedcell)
        logger.debug(f"{usernote} {usernamedcell}")

        # 11/7/2023 - fixed unsupported operand type(s) for +: 'int' and 'str'
        rank = str(rank)
        score = str(score)
        
        event = scoreboard.gsheet.find_cell(scoreboard.worksheet, scoreboard.current_event, in_row=2)
        scoreboard.worksheet.update_cell(row, event.col, f"'{rank + '#' if not rank == None else ''}{score}")
        
        embed = discord.Embed(title="", description=f"{targeted_user.mention}, your score for event `{scoreboard.current_event}` had been set to `{score}` {' at `rank:' + rank + '`' if not rank == None else ''}", color=discord.Color.from_rgb(255, 170, 204))
        # embed.set_footer(text="use **scoreboard!check** or **scoreboard!list** to check the score!")
        await ctx.reply(embed=embed)

    @commands.command(name='activate', aliases=['開放排行', 'unfreeze', 'open'], pass_context=True)
    async def open(self, ctx, eventname = None):
        """Activate an event. If the event name not provided, default will set the latest event to active. """

        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        
        if not eventname is None:
            tevent = scoreboard.gsheet.find_cell(scoreboard.worksheet, str(eventname), in_row=2)
            if tevent is None:
                return await ctx.send(embed=discord.Embed(title="", description=f"the event with name, `{eventname}` not found", color=discord.Color.from_rgb(255, 170, 204)))
            scoreboard.current_event = tevent.value
        else:
            eventlist = scoreboard.gsheet.get_row_values(scoreboard.worksheet, 2)
            if len(eventlist) == 0:
                return await ctx.send(embed=discord.Embed(title="", description=f"there has no available event to be activated", color=discord.Color.from_rgb(255, 170, 204)))

            scoreboard.current_event = eventlist.pop()
            
        scoreboard.is_active = True

        await ctx.send(embed=discord.Embed(title="", description=f"Event `{scoreboard.current_event}` had been set to **active**", color=discord.Color.from_rgb(255, 170, 204)))

    @commands.command(name='deactivate', aliases=['關閉排行', 'freeze', 'inactivate', 'close'], pass_context=True)
    async def close(self, ctx: commands.Context):
        """Close the current event and compute the score of the member if hit the minimum treshold. """

        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None or not await self.__check_current_active_event(ctx):
            return
        if scoreboard.score_listening:
            return await ctx.send(embed=discord.Embed(title="", description=f"Failed to close event `{scoreboard.current_event}` due to the running listener at channel `{scoreboard.listening_channel}`", color=discord.Color.from_rgb(255, 170, 204)))
        
        c_event = scoreboard.current_event
        scoreboard.current_event = None
        scoreboard.is_active = False

        await ctx.send(embed=discord.Embed(title="", description=f"The event `{c_event}` had been closed", color=discord.Color.from_rgb(255, 170, 204)))

        ## 13/07/2023 - add new variable and store the treshold into googlesheet

        async with ctx.typing():
            msg_cal = await ctx.send(embed=discord.Embed(title="", description=f"Doing calculation on who is the top scorer in `{c_event}`...", color=discord.Color.from_rgb(255, 170, 204)))
            event = scoreboard.gsheet.find_cell(scoreboard.worksheet, str(c_event), in_row=2)

            col = event.col
            scorelist: list = scoreboard.gsheet.get_col_values(scoreboard.worksheet, col)
            userlist: list = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 1)
            useridlist: list = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 2)

            t_userlist = userlist[3:]
            t_useridlist = useridlist[3:]
            user_userid = {t_userlist[i]: t_useridlist[i] for i in range(len(t_userlist))}

            userlist[1] = 'eventname'
            userlist[2] = 'date'
            append_scorelist = [''] * (len(userlist) - len(scorelist))
            scorelist.extend(append_scorelist)

            scoreboard_event = {userlist[i]: scorelist[i] for i in range(len(userlist))}

            userscore = dict(list(scoreboard_event.items())[3:])
            filtered_user = {k: v for k, v in userscore.items() if v}
            filtered_user_score = {k: int(v.split("#")[1]) for k, v in filtered_user.items() if v}
            sorted_from_highest_score = sorted(filtered_user_score.items(), key=lambda x:x[1])
            sorted_from_highest_score.reverse()

            d_role = scoreboard.default_award_rank
            if d_role is not None:
                t_role = ctx.guild.get_role(int(d_role))
                
                if len(userscore) > 0:
                    top_scorer, _ = sorted_from_highest_score[0]

                    user = scoreboard.gsheet.find_cell(scoreboard.worksheet, str(top_scorer), in_column=1)
                    userid = scoreboard.worksheet.cell(user.row, 2).value
                    raider = ctx.guild.get_member(int(userid))
                
                    for u in ctx.guild.members:
                        if t_role in u.roles:
                            logger.debug(f"{t_role} -> {u}")
                            await u.remove_roles(*[t_role])

                    await msg_cal.delete()
                    if raider is not None:
                        await raider.add_roles(*[t_role], reason="highest rank in current event")
                        await ctx.send(content=f":tada: Congrats {raider.mention} became the new top scorer in event `{c_event}`!!")

        async with ctx.typing():
            ## calculate and compute the member which not passing the treshold marks
            threshold = int(scoreboard.threshold)
            if threshold > 0:
                msg_thres = await ctx.send(content=f"Let's see who didn't score well, hmmmm..")
                message = f"### Threshold mark is **{threshold}**\n\n"
                index = 0

                for k,v in filtered_user_score.items():
                    if int(v) < threshold:
                        targeted = ctx.guild.get_member(int(user_userid.get(k)))
                        if targeted is not None:
                            message += f"{targeted.mention}, your score `{str(v)}` is below the threshold mark!!\n"
                            index += 1
                
                await msg_thres.delete()
                if index > 0:
                    await ctx.send(content=message)
                else:
                    await ctx.send(content="Seem like everyone here hit the minimum requirement. Congrats!!")

    ### TODO: show ranking list (keyword event name or by userid)
    @commands.command(name='show', aliases=['查看', 'check', 'find'], pass_context=True)
    async def show(self, ctx, args1 = None, args2 = None):
        """
        Show the score of the targeted user or a full list of members' score of the event. To show the member score, use "show member <@mention>" or use "show myscore" to listdown all events you had participated. To show the event score, use "show [eventname]"
        """

        show_in_single_page = 10
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        check_event = False
        member_ = ["member", "myscore"]
        if not args1 in member_:
            if args1 is None:
                if await self.__check_current_active_event(ctx):
                    args1 = scoreboard.current_event
                else:
                    return
            try:
                show_in_single_page = int(args2)
            except:
                pass
            check_event = True
        
        has_mention = len(ctx.message.mentions) > 0
        member = None
        if args1 == "myscore" or (args1 == "member" and not has_mention):
            # await ctx.reply(embed=discord.Embed(title="", description=f"do you want to check your own score?", color=discord.Color.from_rgb(255, 170, 204)))
            member = ctx.author
        elif args1 == "member" and has_mention:
            member = await self.bot.fetch_user(ctx.message.mentions[0].id)

        async with ctx.typing():
            if check_event:
                event = scoreboard.gsheet.find_cell(scoreboard.worksheet, str(args1), in_row=2)
                if event is None:
                    return await ctx.send(embed=discord.Embed(title="", description=f"the event with name, `{args1}` not found", color=discord.Color.from_rgb(255, 170, 204)))
                
                if show_in_single_page > 20:
                    return await ctx.send(embed=discord.Embed(title="", description=f"the maximum records can be shown in a single page is 20.", color=discord.Color.from_rgb(255, 170, 204)))
                elif show_in_single_page < 1:
                    return await ctx.send(embed=discord.Embed(title="", description=f"the request shows of records failed, 1 is the minimum value.", color=discord.Color.from_rgb(255, 170, 204)))

                col = event.col
                scorelist: list = scoreboard.gsheet.get_col_values(scoreboard.worksheet, col)
                userlist: list = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 1)

                userlist[1] = 'eventname'
                userlist[2] = 'date'

                append_scorelist = [''] * (len(userlist) - len(scorelist))
                scorelist.extend(append_scorelist)

                scoreboard_event = {userlist[i]: scorelist[i] for i in range(len(userlist))}

                event = dict(list(scoreboard_event.items())[1:3])
                userscore = dict(list(scoreboard_event.items())[3:])
                # userscore = dict(reversed(list(userscore.items())))

                number_of_members_participated = len(list(filter(None, list(userscore.values()))))

                ### Summary Page
                summary_embed = discord.Embed(title=f":bookmark_tabs: Event Scoreboard Summary", description=f"The summary of the scoreboard for event `{event.get('eventname')}`:",  color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())

                summary_embed.add_field(name=":tada: Name", value=f"{event.get('eventname')}")
                summary_embed.add_field(name=":calendar_spiral: Date", value=f"{event.get('date')}")
                summary_embed.add_field(name=":busts_in_silhouette: Total Participants", value=f"{number_of_members_participated}")
                summary_embed.add_field(name="", value="\b", inline=False)

                ### get top three rank in the scoreboard
                filtered_user = {k: v for k, v in userscore.items() if v}
                filtered_user_score = {k: int(v.split("#")[1]) for k, v in filtered_user.items() if v}
                filtered_user_rank = {k: int(v.split("#")[0]) for k, v in filtered_user.items() if v}
                sorted_from_highest_score = sorted(filtered_user_score.items(), key=lambda x:x[1])
                sorted_from_highest_score.reverse()
                top_scorer, _ = sorted_from_highest_score[0]
                
                top_3 = sorted_from_highest_score[:3]

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
                ### Summary Page

                page_limit = show_in_single_page
                total_members = len(userscore)
                total_pages = math.ceil(total_members / page_limit)
                embeds = [summary_embed]
                for i in range(total_pages):
                    embed = discord.Embed(title=f":bookmark: Event Scoreboard", description=f"Each page showing maximum of {page_limit} records.", color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
                    embed.add_field(name=":tada: Name", value=f"{event.get('eventname')}")
                    embed.add_field(name=":calendar_spiral: Date", value=f"{event.get('date')}")
                    embed.add_field(name=":busts_in_silhouette: Total Participants", value=f"{number_of_members_participated}")
                    embed.add_field(name="", value="\b", inline=False)
                    embed.add_field(name="", value="\b")
                    embed.add_field(name="__:busts_in_silhouette: Member__", value="")
                    embed.add_field(name="__:clipboard: Rank#Score__", value="")
                    number = ""
                    username = ""
                    score = ""
                    for y in range(page_limit):
                        if len(userscore) == 0:
                            append_space = page_limit - (total_members % page_limit)
                            for z in range(append_space):
                                number += f"**{y + 1}.**\n"
                                username += f"\b\n"
                                score += f"\b\n"
                                y = y + 1
                            break
                        u, s = userscore.popitem()
                        number += f"**{y + 1}.**\n"
                        username += '{:<{}s}\n'.format(u, 50)
                        if s == '':
                            score += f"-\n".center(20, " ")
                        else:
                            score += f"{s}\n".center(20, " ")
                    embed.add_field(name="", value=number)
                    embed.add_field(name="", value=username)
                    embed.add_field(name="", value=score)

                    embed.add_field(name="", value="\b", inline=False)
                    embed.set_footer(text=f"Page {i + 1} of {total_pages}. \nEach page showing maximum of {page_limit} records. To show more records in a single page, use command \"scoreboard!show [eventname] [rows to shows]\" ")
                    embeds.append(embed)
                await Paginator.Simple(ephemeral=True, timeout=180).start(ctx, pages=embeds)
            else:
                userid = member.id
                username = member.name
                user = scoreboard.gsheet.find_cell(scoreboard.worksheet, userid, in_column=2)
                
                row = 0
                if user is None:
                    users = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 2)
                    row = 4 if len(users) == 0 else len(users) + 1
                    scoreboard.worksheet.update_cell(row, 1, username)
                    scoreboard.worksheet.update_cell(row, 2, f"'{userid}")
                else:
                    row = user.row

                events = scoreboard.gsheet.get_row_values(scoreboard.worksheet, 2)[2:]
                date = scoreboard.gsheet.get_row_values(scoreboard.worksheet, 3)[2:]
                events_date = {events[i]: date[i] for i in range(len(events))}

                scores = scoreboard.gsheet.get_row_values(scoreboard.worksheet, row)[2:]

                append_scorelist = [''] * (len(events) - len(scores))
                scores.extend(append_scorelist)

                events_scores = {events[i]: scores[i] for i in range(len(events))}

                filtered_user_events = {k: v for k, v in events_scores.items() if not v == ''}

                logger.debug(events_scores)
                logger.debug(filtered_user_events)

                ### 
                # Summary page including information such as 
                # - times being scoreboard leader
                # - numbers of event participated
                # - the best 3 position among the server
                ### Summary Page
                summary_embed = discord.Embed(title=f":bookmark_tabs: {username}'s Scoreboard Summary", description=f"The summary of the scoreboard in the server for `{username}`:",  color=member.color, timestamp=datetime.now())

                targeted_user = ctx.message.author
                nick = scoreboard.worksheet.cell(user.row, 1).value
                nick = nick if nick is not None and not nick == targeted_user.name else '-'
                display_name = nick if not nick == '-' else targeted_user.name

                summary_embed.add_field(name=":label: Nickname", value=f"{nick}")
                summary_embed.add_field(name=":ticket: First Participated Event", value=f"{list(filtered_user_events.keys())[0]}")
                summary_embed.add_field(name=":clipboard: Total Participated Events", value=f"{len(filtered_user_events)}")
                summary_embed.add_field(name="", value="\b", inline=False)

                summary_embed.set_footer(text="use command \"scoreboard!show member <@mention>\" to check score of a user. To check your own score, user command \"scoreboard!show myscore\"")
                ### Summary Page

                ### list all the score of the event this user had participated
                page_limit = 10
                total_events = len(events_scores)
                total_pages = math.ceil(total_events / page_limit)
                embeds = [summary_embed]
                for i in range(total_pages):
                    # Header
                    embed = discord.Embed(title=f":bookmark: {display_name}'s Scoreboard", 
                                          description=f"Each page showing maximum of {page_limit} records.", 
                                          color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
                    embed.add_field(name=":label: Nickname", value=f"{nick}")
                    embed.add_field(name=":ticket: First Participated Event", value=f"{list(filtered_user_events.keys())[0]}")
                    embed.add_field(name=":clipboard: Total Participated Events", value=f"{len(filtered_user_events)}")
                    embed.add_field(name="", value="\b", inline=False)

                    # Body
                    embed.add_field(name="", value="\b")
                    embed.add_field(name="", value=":ticket: __Event (Date)__")
                    embed.add_field(name="", value=":medal: __Rank#Score (Rank in leaderboard)__")

                    number = ""
                    event_date = ""
                    score_position = ""
                    for y in range(page_limit):
                        if len(events_scores) == 0:
                            append_space = page_limit - (total_events % page_limit)
                            for z in range(append_space):
                                number += f"**{y + 1}.**\n"
                                event_date += f"\b\n"
                                score_position += f"\b\n"
                                y = y + 1
                            break
                        e, s = events_scores.popitem()
                        number += f"**{y + 1}.**\n"
                        event_date += f"{e} ({events_date.get(e)})\n"
                        if s == '':
                            score_position += f"-\n"
                        else:
                            score_position += f"{s}\n"
                    embed.add_field(name="", value=number)
                    embed.add_field(name="", value=event_date)
                    embed.add_field(name="", value=score_position)

                    # Footer
                    embed.add_field(name="", value="\b", inline=False)
                    embed.set_footer(text=f"Page {i + 1} of {total_pages}. \nUsed command \"scoreboard!show {args1}\" ")
                    embeds.append(embed)

                await Paginator.Simple(ephemeral=True, timeout=180).start(ctx, pages=embeds)

    ### 13/07/2023 - show qualified/unqualified member /set qualified score / automatically qualify score
    @commands.command(name='threshold', aliases=['set_threshold'], pass_context=True)
    async def set_threshold_score(self, ctx: commands.Context, score: int):
        """set the minimum threshold for the scoreboard. If a member who participated has lower than threshold, the bot will mention the member during closing"""
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        
        scoreboard.worksheet.update_cell(1, 3, f"'{score}")
        scoreboard.threshold = score
        await ctx.send(embed=discord.Embed(title="", description=f"The threshold score had been updated to `{str(score)}`", color=discord.Color.from_rgb(255, 170, 204)))

    ### TODO: freeze/unfreeze user from update score

    ### 13/07/2023 - bot assign raid demon once the score computed (when close the scoreboard/calling command to award raid demon) 
    # but the preacquisition is set the default role to be assigned
    @commands.command(name='dr', aliases=['set_scorer_role'], pass_context=True)
    async def set_default_leaderboard_role(self, ctx: commands.Context, role: discord.Role):
        """set the default role for top scorer, the role will be assigned to the top scorer after the event declare close"""
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        
        d_role = scoreboard.worksheet.cell(1, 4).value
        if d_role is not None:
            t_role = ctx.guild.get_role(int(d_role))
            
            # ask user whether want to overwrite it
            msg: discord.Message = await ctx.reply(f"There is a default top scorer role in records ({t_role.name}).\n Do you want to overwrite it?") 
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

                scoreboard.worksheet.update_cell(1, 4, f"'{role.id}")
                scoreboard.default_award_rank = role.id
                await msg.delete()
                return await ctx.reply(embed=discord.Embed(title="", description=f"The default top scorer's role had been updated to `{role.name}`", color=discord.Color.from_rgb(255, 170, 204)))
            except CancelledAction:
                return await ctx.reply(f"the request to had been cancelled") 
            except Exception as error:
                logger.debug(error)
                return await ctx.reply(f"something gone wrong") 

        scoreboard.worksheet.update_cell(1, 4, f"'{role.id}")
        scoreboard.default_award_rank = role.id
        await ctx.send(embed=discord.Embed(title="", description=f"The default top scorer's role had been updated to `{role.name}`", color=discord.Color.from_rgb(255, 170, 204)))

    ### 13/07/2023 - start/stop listener which can be binded to a channel 
    # (additionally add a function which can scan through the channel and update the score based on the posted image, tag the user if the score failed to update)
    @commands.command(name='ls', aliases=['listening', 'es'], pass_context=True)
    async def enable_listening_score(self, ctx: commands.Context, option: str):
        """enable the score listening by using command \"scoreboard!ls [option:on|off]\""""

        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        try:
            options_positive = ['on', 'enable', 'en']
            options_negative = ['off', 'disable']
            options = ['off', 'disable', 'on', 'enable', 'en']
            if option not in options:
                raise ValueError("Invalid option. Expected one of: %s" % options)
            if option in options_positive:
                if scoreboard.score_listening:
                    return await ctx.reply(f"The listener is running..")

                # TODO: Ask user to activate event if the status is not active
                if not await self.__check_current_active_event(ctx):
                    msg: discord.Message = await ctx.reply(embed=discord.Embed(title="", description="Seem like there isn't any active event at the moment, would you like to set the latest event to active? " +
                                                           "\n\nReact on ✅ for activate latest event, react on ❌ to cancel the action." + 
                                                           "\n\nAlternatively, reply to this message to set the targeted event or reply startwith **\"create [eventname] [date]\"** to create new event.", color=discord.Color.from_rgb(255, 170, 204)), 
                                                           ephemeral=True) 
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

                        reaction_done = done.pop().result()
                        if isinstance(reaction_done, discord.Message):
                            reply = reaction_done.content
                            if reply.startswith('create'):
                                args = reply.split(' ')
                                await self.create(ctx, name=args[1], date=self.__get_list_item(args, 2, str(date.today())))
                            else:
                                await self.open(ctx)
                        else:
                            await self.open(ctx)
                    except CancelledAction:
                        return await ctx.reply(embed=discord.Embed(title="", description=f"The listener had not been started", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True) 
                    except Exception as error:
                        logger.debug(error)
                        return await ctx.reply(embed=discord.Embed(title="", description=f"Something went wrong", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True) 

                #bind the API here
                if not self.check_exist(ctx):
                    await self.bind(ctx)
                scoreboard.score_listening = True
                scoreboard.listening_channel = ctx.channel
                await ctx.reply(embed=discord.Embed(title="", description=f"Start listening to incoming message at `{scoreboard.listening_channel.name}` to handle score update", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
            else:
                if not scoreboard.score_listening:
                    return await ctx.reply(embed=discord.Embed(title="", description=f"The listener is not running..", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
                scoreboard.score_listening = False
                scoreboard.listening_channel = None
                await ctx.reply(embed=discord.Embed(title="", description=f"The listener had been stopped", color=discord.Color.from_rgb(255, 170, 204)), ephemeral=True)
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.reply(embed=discord.Embed(title="", description=f"Failed to start listener", color=discord.Color.from_rgb(255, 170, 204)))
            scoreboard.score_listening = False
            scoreboard.listening_channel = None
    
    @commands.Cog.listener()
    async def on_message(self, message :discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)
        
        if ctx.guild.id in self.scoreboard:
            scoreboard = await self.__get_scoreboard(ctx)
            if not message.content.startswith("scoreboard!") and not message.author.bot and scoreboard.score_listening and message.channel == scoreboard.listening_channel:
                valid = False
                if validators.url(message.content) and message.content.endswith(('.jpg', '.png', '.gif', '.jpeg')):
                    valid = True
                elif message.attachments:
                    valid = True
                    
                if valid:
                    await self.score(ctx)

    @commands.command(name='auto_score', aliases=['scan_score'], pass_context=True)
    async def set_score_in_channel(self, ctx: commands.Context, message_limit: int = 200):
        """Automatically scanning the channel and update the score by using command \"scoreboard!auto_score [optonal:message_limit(number)]\""""

        ### check if there is active current event
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None or not await self.__check_current_active_event(ctx):
            return

        involve = 0
        success = 0
        channel = ctx.message.channel
        msg_str = "Start lookup for messages contains image and attempting to update score"
        msg_body_attp = ""
        msg = await ctx.send("Start lookup for messages contains image and attempting to update score")
        async for message in channel.history(limit=200, oldest_first=True):
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
                    user = scoreboard.gsheet.find_cell(scoreboard.worksheet, userid, in_column=2)
                    logger.debug(f"update score :: {userid} {username} {score} {user}")
                    
                    row = 0
                    if user is None:
                        users = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 2)
                        row = 4 if len(users) == 0 else len(users) + 1
                        scoreboard.worksheet.update_cell(row, 1, username)
                        scoreboard.worksheet.update_cell(row, 2, f"'{userid}")
                    else:
                        row = user.row

                    rank = str(rank)
                    score = str(score)
                    
                    event = scoreboard.gsheet.find_cell(scoreboard.worksheet, scoreboard.current_event, in_row=2)
                    scoreboard.worksheet.update_cell(row, event.col, f"'{rank + '#' if not rank == None else ''}{score}")

                    msg_str += f"\n- Succesfully update {targeted_user.mention}'s score to `{score}` {' at `rank:' + rank + '`' if not rank == None else ''}"
                    await msg.edit(content=f"{msg_str}\n{msg_body_attp}")
                    success += 1
                except:
                    ## send alert
                    await message.reply(content=f"{targeted_user.mention}, unable to update your score, maybe it is due to I cannot understand the image")
 
        msg_str = f"{msg_str}\n{msg_body_attp}\n{success} success out of {involve} attempts"
        await msg.edit(content=msg_str)

    ### 12/7/2023 - set nickname for the user
    @commands.command(name='nick', aliases=['set_nick'], pass_context=True)
    async def nickname(self, ctx, nickname: str):
        """set nickname for the user"""
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        
        targeted_user = ctx.message.author
        userid = targeted_user.id
        user = scoreboard.gsheet.find_cell(scoreboard.worksheet, userid, in_column=2)

        search_existed_nickname = scoreboard.gsheet.find_cell(scoreboard.worksheet, nickname, in_column=1)
        if not len(search_existed_nickname) == 0:
            ownerid = scoreboard.worksheet.cell(search_existed_nickname.row, 2).value
            owner: discord.Member = ctx.guild.get_member(int(ownerid))
            return await ctx.reply(embed=discord.Embed(title="", description=f"This nickname `{nickname}` had been taken by `{owner.mention}`", color=discord.Color.from_rgb(255, 170, 204)))
        
        row = 0 if user is None else user.row
        if user is None:
            users = scoreboard.gsheet.get_col_values(scoreboard.worksheet, 2)
            row = 4 if len(users) == 0 else len(users) + 1
            scoreboard.worksheet.update_cell(row, 1, nickname)
            scoreboard.worksheet.update_cell(row, 2, f"'{userid}")
            return await ctx.reply(embed=discord.Embed(title="", description=f"{targeted_user.mention}, you rocked in with `{nickname}`!!", color=discord.Color.from_rgb(255, 170, 204)))
        else:
            ori_username = scoreboard.worksheet.cell(row, 1).value
            scoreboard.worksheet.update_cell(row, 1, nickname)
            return await ctx.reply(embed=discord.Embed(title="", description=f"{targeted_user.mention}, you have set your nickname to `{nickname}`", color=discord.Color.from_rgb(255, 170, 204)))

    @commands.command(name='reset_nick', aliases=['rn'], pass_context=True)
    async def reset_nickname(self, ctx):
        """reset the user's nickname to their username"""
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        
        targeted_user = ctx.message.author
        userid = targeted_user.id
        username = targeted_user.name
        user = scoreboard.gsheet.find_cell(scoreboard.worksheet, userid, in_column=2)
        
        row = 0 if user is None else user.row
        if user is None:
            return await ctx.reply(embed=discord.Embed(title="", description=f"Hmmm, you didn't registered in the scoreboard yet", color=discord.Color.from_rgb(255, 170, 204)))

        msg: discord.Message = await ctx.reply("Are you sure to reset the nickname to your username?") 
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        def is_owner(reaction, user):
            if reaction.message.id == msg.id and not user.id == ctx.author.id:
                return False
            if reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '❌':
                raise CancelledAction("canceled, user reacted with ❌")
            return reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '✅'
        try:
            done, pending = await asyncio.wait([
                # self.bot.loop.create_task(self.bot.wait_for('message')),
                self.bot.loop.create_task(self.bot.wait_for('reaction_add', check=is_owner))
            ], return_when=asyncio.FIRST_COMPLETED)

            reaction_done = done.pop().result()
            logger.debug(f"result :: {reaction_done}")

            scoreboard.worksheet.update_cell(row, 1, username)
            return await ctx.reply(embed=discord.Embed(title="", description=f"{targeted_user.mention}, your name had been reset to `{username}`", color=discord.Color.from_rgb(255, 170, 204)))
        except CancelledAction:
            return await ctx.reply(f"the request to reset nickname had been cancelled") 
        except Exception as error:
            logger.debug(error)
            return await ctx.reply(f"something gone wrong") 
        
    ### list all the event with date and member participated
    @commands.command(name='list', aliases=['list_events', 'events'], pass_context=True)
    async def list_events(self, ctx):
        """List down all of the events created. """

        async with ctx.typing():
            result = await self.__list_event_method(ctx)
            if isinstance(result, discord.Embed):
                await ctx.send(embed=result)
            else:
                await Paginator.Simple(ephemeral=True, timeout=180).start(ctx, pages=result)

    async def __list_event_method(self, ctx) -> discord.Embed | list[discord.Embed]:
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard == None:
            return
        events = list(filter(None, scoreboard.gsheet.get_row_values(scoreboard.worksheet, 2)))
        dates = list(filter(None, scoreboard.gsheet.get_row_values(scoreboard.worksheet, 3)))
        events_dates = {events[i]: dates[i] for i in range(len(events))}
        if events_dates:
            page_limit = 5
            total_events = len(events_dates)
            total_pages = math.ceil(total_events / page_limit)
            
            embeds = []
            for i in range(total_pages):
                index = 1
                embed = discord.Embed(title="__Event list__", description=f"{'The current active event is `' + scoreboard.current_event + '`' if scoreboard.current_event is not None else 'There has no current **active event** at the moment.'}", color=discord.Color.from_rgb(255, 170, 204))
                embed.add_field(name="", value="\b", inline=False)
                embed.add_field(name="", value="\b")
                embed.add_field(name="__:tada: Event__", value="")
                embed.add_field(name="__:calendar_spiral: Date__", value="")
                for y in range(page_limit):
                    if len(events) == 0:
                        append_space = page_limit - (total_events % page_limit)
                        for z in range(append_space):
                            embed.add_field(name="", value=f"**{index}.**")
                            embed.add_field(name="", value="\b")
                            embed.add_field(name="", value="\b")
                            index = index + 1
                        break
                    embed.add_field(name="", value=f"**{index}.**")
                    embed.add_field(name="", value='{:<{}s}'.format(events.pop(0), 30))
                    embed.add_field(name="", value=f"`{dates.pop(0)}`")
                    index = index + 1
                embed.set_footer(text=f"Page {i + 1} of {total_pages}, total {total_events} event(s)")
                embeds.append(embed)
            return embeds
        else:
            embed = discord.Embed(title="__Event list__", color=discord.Color.from_rgb(255, 170, 204))
            embed.add_field(name="", value="\b", inline=False)
            embed.add_field(name="", value="*There has no event created*", inline=False)
            return embed

    async def __check_current_active_event(self, ctx) -> bool:
        scoreboard = await self.__get_scoreboard(ctx)
        if scoreboard is None:
            return False
        if not scoreboard.is_active:
            await ctx.send(embed=discord.Embed(title="", description=f"there has no active event at the moment", color=discord.Color.from_rgb(255, 170, 204)))
            return False
        return True

    async def __get_scoreboard(self, ctx) -> (None | ScoreboardRecord):
        scoreboard = self.get_scoreboard(ctx)
        if self.check_exist(ctx):
            return scoreboard
        else:
            await self.bind(ctx)
            return self.get_scoreboard(ctx)
            # await ctx.send(embed=discord.Embed(title="", description=f"the scoreboard had not been bind yet. Use **bind** command to bind scoreboard", color=discord.Color.from_rgb(255, 170, 204)))
        return None

    def check_exist(self, ctx) -> bool:
        try:
            if not isinstance(self.scoreboard[ctx.guild.id], ScoreboardRecord) or self.scoreboard[ctx.guild.id].gsheet is None:
                return False
            return True
        except:
            return False

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
        else:
            image_url = args

        result = ocr.extract_from_image(image_url, 0, 0, 100, 650, True, output=ocr.Output.LIST)
        logger.debug(f"result :: {result}")
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
            
        logger.debug(f"rank :: {rank}, score :: {score}")
            
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

class ScoreOrRankExtractionError(Exception):
    pass

class CancelledAction(Exception):
    # handle exception for cancelled action from user
    pass
        
async def setup(bot):
    await bot.add_cog(Scoreboard(bot))