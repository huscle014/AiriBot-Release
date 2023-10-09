import discord
from discord.ext import commands
from discord import PartialEmoji as pe
from discord import app_commands

import traceback
import sys
import re
import os
import validators
from typing import List
from datetime import datetime
import textwrap
import math
import time
import datetime as dt
import requests

import utils.logger as logger
from utils.cutils import apngtogif, rename_file, get_date, _gettext, get_server_locale
import utils.paginator as page
from utils.discord.utils import context, response

class Utilities(commands.Cog):
    """Utilities related commands."""

    __slots__ = ('bot', 'prefix')

    def __init__(self, bot):
        self.bot = bot
        self.logger = logger.Logger("Utilities")

    async def emote_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = ['reaction', 'message', 'reference', 'url', 'emoji']
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    @commands.hybrid_command(name="steal-emote", aliases=['steal', '偷表符', '偷表情', '偷'], pass_context=True, with_app_command=True)
    @app_commands.autocomplete(option=emote_options)
    @app_commands.describe(option="The option to extract the emoji, some parameter might required if certain option chosen")
    @app_commands.describe(emoji="[conditionally required] emoji to be extracted")
    @app_commands.describe(min_range="the lower bound position. if 'reaction' chosen as option, this parameter can be provided")
    @app_commands.describe(max_range="the higher bound position. if 'reaction' chosen as option, this parameter can be provided")
    @app_commands.describe(reference="[conditionally required] the message url of the reply message to be extracted from")
    @app_commands.describe(url="[conditionally required] the message url to be extracted from")
    async def steal_emote(self, ctx: commands.Context, emoji:str = None, min_range:int = 0, max_range: int = 0, option: str = None, reference: discord.Message = None, url:str = None):
        """Extract the image source of the emoji. """

        self.logger.debug("===== steal_emote =====")

        locale = get_server_locale(ctx.guild.id)

        ctx = await context(ctx)

        if not option in ['reaction', 'message', 'reference', 'url', 'emoji'] and reference is None and url is None:
            self.logger.debug("==legacy checking==")
            self.logger.debug(f"incoming :: {emoji} {option}")
            if ctx.message.reference is not None:
                reference = await ctx.fetch_message(ctx.message.reference.message_id)
                option = 'reaction' if emoji in ('reaction','反應') else 'reference'
            elif ctx.message.reference is None and emoji is not None:
                if validators.url(emoji):
                    option = 'url'
                else:
                    option = 'message'
                url = emoji
            else:
                return await response(ctx, _gettext('msg_missing_emoji', locale))
            self.logger.debug(f"complete :: {emoji} {option}")
            self.logger.debug("==done legacy check==")

        if option == 'reference' and reference is None:
            return await response(ctx, _gettext('msg_wrong_missing_reference', locale))
        elif option == 'reaction' and reference is None:
            return await response(ctx, _gettext('msg_missing_emoji', locale))
        elif option in ['message', 'emoji'] and emoji is None:
            return await response(ctx, _gettext('msg_missing_emoji', locale))
        elif option == 'url' and url is None:
            return await response(ctx, _gettext('msg_wrong_missing_url', locale))
        elif option == 'url' and not validators.url(url):
            return await response(ctx, _gettext('msg_url_unidentify', locale))
        elif option is None:
            return await response(ctx, _gettext('msg_content_unidentify', locale))
        else:
            self.logger.debug("done validation..")

        fetch_by_id = False
        if emoji.isdigit():
            emoji = f'<a:{emoji}:{emoji}><:{emoji}:{emoji}>'
            fetch_by_id = True
        
        if option == 'url':
            #attempt to retrieve the message content of the provided url, if failed then raise error
            try:
                link = url.split('/')
                server_id = int(link[4])
                channel_id = int(link[5])
                msg_id = int(link[6])
                self.logger.debug(f"{server_id} {channel_id} {msg_id}")

                server: discord.Guild = await self.bot.fetch_guild(server_id)
                channel: discord.channel = await server.fetch_channel(channel_id)
                msg: discord.Message = await channel.fetch_message(msg_id)
                emoji = msg.content
            except discord.errors.NotFound as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                return await response(ctx, _gettext('msg_not_in_server', locale))
            except Exception as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                return await response(ctx, _gettext('msg_url_unidentify', locale))
        elif option in ['reference', 'reaction']:
            penemoji: discord.Message = reference
            if option == 'reaction':
                rslt = []
                reactions = penemoji.reactions
                rangemin = 0
                rangemax = len(reactions)
                try:
                    if not min_range <= 0:
                        rangemin = int(min_range) - 1
                        if not max_range <= 0:
                            rangemax = int(max_range)
                        if rangemax > len(reactions):
                            return await response(ctx, _gettext('msg_exceed_range', locale))
                        elif rangemin > rangemax:
                            return await response(ctx, _gettext('msg_invalid_param_less_than', locale))
                        elif rangemin < 0:
                            return await response(ctx, _gettext('msg_invalid_small_less_zero', locale).format(rangemin=min_range))
                except:
                    pass
                for i in range(rangemin, rangemax):
                    curr_emoji = str(reactions[i].emoji)
                    try:
                        femoji: pe = pe.from_str(curr_emoji)
                        tmpembed = discord.Embed(url=femoji.url)
                        tmpembed.title = femoji.name
                        tmpembed.set_image(url=femoji.url)
                        rslt.append(tmpembed)
                    except Exception:
                        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                        await response(ctx, _gettext('msg_content_unidentify', locale))
                #客制回覆訊息，假設是
                msg = ""
                if rangemin == 0 and rangemax == len(reactions):
                    msg = _gettext('msg_emoji_all', locale) + "\n"
                else:
                    msg = _gettext('msg_emoji_in_range', locale).format(rangemin=(rangemin+1), rangemax=(rangemax)) + "\n"
                
                return await page.EmbedPaginator(timeout=180).start(ctx, pages=rslt, content=msg)
            emoji = penemoji.content

        # 12/07/2023 - remove redundant elements 
        custom_emojis = list(set(re.findall(r'<[a]?:\w*:\d*>', emoji)))
        
        self.logger.info(f"the emoji in the message includes {custom_emojis}")
        rslt: list[discord.Embed] = []
        if len(custom_emojis) > 1:
            for e in custom_emojis:
                try:
                    femoji: pe = pe.from_str(e)
                    if fetch_by_id:
                        if not validators.url(femoji.url):
                            continue
                        res = requests.get(femoji.url)
                        if not res.ok:
                            continue
                    tmpembed = discord.Embed(url=femoji.url)
                    tmpembed.title = femoji.name
                    tmpembed.set_image(url=femoji.url)
                    rslt.append(tmpembed)
                    if fetch_by_id and femoji.animated:
                        break
                except Exception as error:
                    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                    continue
            if len(rslt) > 1:
                await page.EmbedPaginator(timeout=180).start(ctx, pages=rslt, content=f"{_gettext('msg_emoji_all_message', locale)}\n")
            elif len(rslt) == 1:
                await response(ctx, rslt[0].image.url)
            else:
                await response(ctx, _gettext('msg_content_unidentify', locale))
        elif len(custom_emojis) == 1:
            try:
                # 10/7/2023 - fixed issue when only 1 emoji presented in reference message
                femoji: pe = pe.from_str(custom_emojis.pop())
                await response(ctx, femoji.url)
            except Exception as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                await response(ctx, _gettext('msg_content_unidentify', locale))
        else:
            return await response(ctx, _gettext('msg_emoji_failed_extract', locale))

    """
    這個功能只能以回覆的方式使用
    """
    @commands.hybrid_command(name="steal-sticker", aliases=['steal_sticker', '偷貼圖'], pass_context=True)
    @app_commands.describe(convert="specify if a sticker is animated should converted to gif format, default is False")
    @app_commands.describe(reference="[required] the message url of the reply message to be extracted from")
    async def steal_sticker(self, ctx: commands.Context, convert: bool = False, reference: discord.Message = None):
        """Extract the image source from a sticker in the server."""

        self.logger.debug("===== steal_sticker =====")

        locale = get_server_locale(ctx.guild.id)

        ctx = await context(ctx)

        if reference is None:
            if ctx.message.reference is not None:
                reference = await ctx.fetch_message(ctx.message.reference.message_id)
            else:
                return await response(ctx, _gettext('msg_missing_sticker', locale))

        #check if the replied message contain a sticker
        if len(reference.stickers) > 0:
            try:
                sticker = reference.stickers[0]
                tembed = discord.Embed()
                tembed.set_footer(text=_gettext('msg_sticker_footer_1', locale) + "\n" + _gettext('msg_sticker_footer_2', locale))
                
                if sticker.format is discord.StickerFormatType.apng:
                    path = None
                    filename = None
                    
                    if convert:
                        path, filename = apngtogif(sticker.url)
                        file = discord.File(path, filename=filename)
                        tembed.set_image(url=f"attachment://{filename}")
                        await response(ctx, file=file, embed=tembed)

                        file.close()
                        return 
                    else:
                        tembed.set_image(url=sticker.url)

                    if path is not None and os.path.exists(path):
                        os.remove(path)

                else:
                    tembed.url = sticker.url
                    tembed.title = sticker.name
                    tembed.set_image(url=sticker.url)
                
                return await response(ctx, embed=tembed)
            except Exception as e:
                raise e
        else:
            await response(ctx, _gettext('msg_sticker_failed', locale))

    @commands.hybrid_command(name="avatar", pass_context=True)
    @app_commands.describe(member="the member to be extract the avatar")
    @app_commands.describe(reference="the message url of the reply message to be extracted from")
    async def get_avatar(self, ctx: commands.Context, member: discord.Member = None, reference: discord.Message = None):
        """Extract avatar from user"""
        
        self.logger.debug("===== get_avatar =====")
        ctx = await context(ctx)
            
        if member is None and reference is not None:
            member = reference.author
            
        if reference is None and member is None:
            member = ctx.author

        embeds = []
        if member.guild_avatar is not None:
            embed = discord.Embed(title=f"{member.display_name}'s server avatar", 
                        description=f"**[{member.display_name}]({member.guild_avatar.url})**",
                        color=member.color, timestamp=datetime.now())
            embed.set_image(url=member.guild_avatar.url)
            embed.set_footer(icon_url=self.bot.user.avatar, text="")
            embeds.append(embed)

        embed = discord.Embed(title=f"{member.global_name}'s avatar", 
                        description=f"**[{member.global_name}]({member.avatar.url})**",
                        color=member.color, timestamp=datetime.now())
        embed.set_image(url=member.avatar.url)
        embed.set_footer(icon_url=self.bot.user.avatar, text="")

        if len(embeds) > 0:
            embeds.append(embed)
            return await page.EmbedPaginator(timeout=180).start(ctx, pages=embeds)
        await response(ctx, embed=embed)

    @commands.hybrid_command(name="banner", pass_context=True)
    @app_commands.describe(member="the member to be extract the avatar")
    async def get_banner(self, ctx: commands.Context, member: discord.Member = None, reference: discord.Message = None, convert: bool = True):
        """Extract avatar from user"""
        
        self.logger.debug("===== get_banner =====")

        locale = get_server_locale(ctx.guild.id)
        ctx = await context(ctx)

        if ctx.message.reference is not None:
            reference: discord.Message = await ctx.fetch_message(ctx.message.reference.message_id)
            member = reference.author

        if member is None and reference is not None:
            member = reference.author
            
        if reference is None and member is None:
            member = ctx.author

        embed = discord.Embed(title=f"{member.global_name}'s banner", 
                            color=member.color, timestamp=datetime.now())
        if member.banner:
            embed.set_image(url=member.banner.url)
            embed.set_footer(icon_url=self.bot.user.avatar, text="")

            await response(ctx, embed=embed, ephemeral=True)
        elif member.accent_colour:
            uc = str(member.accent_color).format(hex).strip('#')
            
            embed=discord.Embed(
                title='',
                description=f"**[banner]({f'https://singlecolorimage.com/get/{uc}/400x100'})**",
                color=0x000001
            )
            
            embed.set_author(name=f'{member.name}#{member.discriminator}', icon_url=member.display_avatar.url)
            embed.set_image(url=f'https://singlecolorimage.com/get/{uc}/400x100')
        else:
            req = await self.bot.http.request(discord.http.Route("GET","/users/{uid}",uid=member.id))
            banner_id = req["banner"]
            if banner_id:
                banner_url = f"https://cdn.discordapp.com/banners/{member.id}/{banner_id}?size=1024"
                if convert and banner_id.startswith('a_'): ## is animated banner, will convert to gif
                    try:
                        path, filename = await rename_file(banner_url, "gif")
                        file = discord.File(path, filename=filename)
                        embed.set_image(url=f"attachment://{filename}")
                        self.logger.info(f"{file.filename} {embed.image}")
                        await response(ctx, file=file, embed=embed)
                        file.close()
                        if path is not None and os.path.exists(path):
                            os.remove(path)
                        return
                    except Exception as e:
                        self.logger.error(e)
                        return
                embed.set_image(url=banner_url)
            else:
                return await response(ctx, _gettext('msg_banner_user_not_set', locale), ephemeral=True)  
            
        await response(ctx, embed=embed, ephemeral=True)

    async def search_options(self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = ['attachment', 'link', 'embed']
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]
    
    @commands.hybrid_command(name="search-message", pass_context=True)
    @app_commands.autocomplete(has=search_options)
    @app_commands.describe(keyword="the keyword to search")
    @app_commands.describe(channel="which channel to search")
    @app_commands.rename(f_user="from")
    @app_commands.describe(f_user="the message send by which user")
    @app_commands.describe(mentions="the message contains mentions to a user")
    @app_commands.describe(has="the message has either attachment, link or embed")
    @app_commands.describe(before="the message sent before date of")
    @app_commands.describe(after="the message sent after date of")
    async def keyword(self, ctx: commands.Context, keyword: str = '', f_user: discord.User = None, mentions: discord.User = None, has: str = 'message', 
                      before: str = str(datetime.today()), after: str = str(datetime.min), channel: discord.TextChannel = None):
        """Search message with keyword in the channel"""
        self.logger.debug("===== search-message =====")

        ctx = await context(ctx)
        if channel is None:
            channel = ctx.channel
        
        if after == str(datetime.min):
            after = str(channel.created_at)

        self.logger.info(f"before : {before}; after : {after}")
        
        finding_criteria = list(filter(lambda item: item is not None, [
                "from user" if not f_user is None else None,
                "has mention user" if not mentions is None else None,
                "has attachment" if has == 'attachment' else None,
                "has link" if has == 'link' else None,
                "has embed" if has == 'embed' else None,
                "contains text" if has == 'message' and not keyword == '' else None
            ]))
        
        self.logger.info(f"{finding_criteria}")
        total_search = 0
        result = []

        start = time.time()
        async for msg in channel.history(limit=9999999, oldest_first=True, 
                                         before=datetime.strptime(get_date(before), '%Y-%m-%d'), after=datetime.strptime(get_date(after), '%Y-%m-%d')):
            if keyword in msg.content :
                found = 0
                if not f_user is None and f_user == msg.author:
                    found += 1
                if not mentions is None and mentions in msg.mentions:
                    found += 1
                if has == 'attachment' and msg.attachments:
                    found += 1
                elif has == 'link' and re.search("(https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?[a-zA-Z0-9]{2,}(\.[a-zA-Z0-9]{2,})(\.[a-zA-Z0-9]{2,})?", msg.content):
                    found += 1
                elif has == 'embed' and msg.embeds:
                    found += 1
                elif has == 'message' and not keyword == '':
                    found += 1

                if found == len(finding_criteria):
                    result.append(
                        {
                            "author": msg.author,
                            "content":  textwrap.shorten(text=msg.content, width=50, placeholder="..."),
                            "mentions": msg.mentions,
                            "attachments": msg.attachments,
                            "embeds": msg.embeds,
                            "jump_url": msg.jump_url
                        }
                    )
                    total_search += 1
        
        self.logger.debug("Using paginations..")
        self.logger.debug(f"Search total : {total_search}; result count : {len(result)}")

        embeds = []
        page_limit = 12
        total_pages = math.ceil(total_search / page_limit)
        for i in range(total_pages):
            # Header
            embed = discord.Embed(title=f"", description=f"Filter with {', '.join(finding_criteria)}", color=discord.Color.from_rgb(255, 170, 204), timestamp=datetime.now())
            embed.add_field(name="Total search result", value=f"{total_search}", inline=False)
            for y in range(len(result) % page_limit if len(result) < page_limit else page_limit):
                d = result.pop()
                embed.add_field(name=f"{d['author']}", value=f">>> {d['content']}\n[➥ jump]({d['jump_url']})")
                        
            embed.set_footer(text=f"Page {i + 1} of {total_pages} | Utility @ Search")
            embeds.append(embed)

        
        end = str(dt.timedelta(seconds=int(round(time.time()-start))))
        await page.EmbedPaginator(ephemeral=True, timeout=180).start(ctx, pages=embeds, content=f"Total search result: {total_search}\nTotal time taken for query: {end}")

async def setup(bot):
    await bot.add_cog(Utilities(bot))

