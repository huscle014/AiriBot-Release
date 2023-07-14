import discord
from discord.ext import commands
from discord import PartialEmoji as pe

import traceback
import sys
import traceback
import re
import os
import validators

from utils.cutils import apngtogif
from utils import logger

class Utilities(commands.Cog):
    """Utilities related commands."""

    __slots__ = ('bot', 'prefix')

    def __init__(self, bot):
        self.bot = bot

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

    @commands.command(aliases=['延遲'])
    async def ping(self, ctx):
        """Returns the latency of the bot."""
        await ctx.send(f"目前延遲為 {round(self.bot.latency * 1000)}毫秒(ms)")

    @commands.hybrid_command(name="steal", aliases=['偷表符', '偷表情', '偷'], pass_context=True, with_app_command=True)
    async def steal_emote(self, ctx, emoji = None, arg1 = None, arg2 = None):
        """Extract the image source of the emoji. """

        if emoji is None and ctx.message.reference is None:# or not isinstance(emoji, discord.PartialEmoji):
            return await ctx.reply("沒附上表符哦!")
        elif emoji is not None and validators.url(emoji):
            #attempt to retrieve the message content of the provided url, if failed then raise error
            try:
                link = emoji.split('/')
                server_id = int(link[4])
                channel_id = int(link[5])
                msg_id = int(link[6])
                logger.debug(f"{server_id} {channel_id} {msg_id}")

                server: discord.Guild = await self.bot.fetch_guild(server_id)
                channel: discord.channel = await server.fetch_channel(channel_id)
                msg: discord.Message = await channel.fetch_message(msg_id)
                emoji = msg.content
            except discord.errors.NotFound as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                return await ctx.reply("不在伺服器内呢")
            except Exception as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                return await ctx.reply("所附上的網址無法解讀")
        elif ctx.message.reference is not None:
            penemoji: discord.Message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if emoji == "反應":
                rslt = []
                reactions = penemoji.reactions
                rangemin = 0
                rangemax = len(reactions)
                try:
                    if arg1 is not None:
                        rangemin = int(arg1) - 1
                        if arg2 is not None:
                            rangemax = int(arg2)
                        if rangemax > len(reactions):
                            return await ctx.reply("所提供的參數似乎不對捏~ 已超出範圍捏")
                        elif rangemin > rangemax:
                            return await ctx.reply("所提供的參數似乎不對捏~ 應該提供小數再提供大數喲")
                        elif rangemin < 0:
                            return await ctx.reply(f"所提供的參數似乎不對捏~ 小數 **{rangemin+1}** 不在範圍内")
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
                        await ctx.reply("沒辦法辨識内容呢")
                #客制回覆訊息，假設是
                if rangemin == 0 and rangemax == len(reactions):
                    await ctx.reply(f"這裏是反應裏全部的表符~ <:airi_excited:1123477536035319868>\n", embeds=rslt)
                else:
                    await ctx.reply(f"這裏是反應裏第{rangemin+1}至{rangemax}的表符~ <:airi_excited:1123477536035319868>\n", embeds=rslt)
                return
            emoji = penemoji.content

        # 12/07/2023 - remove redundant elements 
        custom_emojis = list(set(re.findall(r'<[a]?:\w*:\d*>', emoji)))
        
        logger.info(f"the emoji in the message includes {custom_emojis}")
        rslt = []
        if len(custom_emojis) > 1:
            for e in custom_emojis:
                try:
                    femoji: pe = pe.from_str(e)
                    tmpembed = discord.Embed(url=femoji.url)
                    tmpembed.title = femoji.name
                    tmpembed.set_image(url=femoji.url)
                    rslt.append(tmpembed)
                except Exception:
                    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                    await ctx.reply("沒辦法辨識内容呢")
            await ctx.reply(f"這裏是訊息裏全部的表符~ <:airi_excited:1123477536035319868>\n", embeds=rslt)
        else:
            try:
                # 10/7/2023 - fixed issue when only 1 emoji presented in reference message
                femoji: pe = pe.from_str(custom_emojis.pop())
                await ctx.reply(femoji.url)
            except Exception as error:
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                await ctx.reply("沒辦法辨識内容呢")

    """
    這個功能只能以回覆的方式使用
    """
    @commands.command(aliases=['偷貼圖'], pass_context=True)
    async def steal_sticker(self, ctx):
        """Extract the image source from a sticker in the server."""

        if ctx.message.reference is None:
            await ctx.reply("沒附上貼圖哦!")
            return
        reply_to: discord.Message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        #check if the replied message contain a sticker
        if len(reply_to.stickers) > 0:
            try:
                sticker = reply_to.stickers.pop()
                if sticker.format is discord.StickerFormatType.apng:
                    tembed = discord.Embed()
                    path, filename = apngtogif(sticker.url)
                    file = discord.File(path, filename=filename)
                    tembed.set_image(url=f"attachment://{filename}")
                    tembed.set_footer(text=f"已使用偷貼圖\n**需點開下載動圖")
                    await ctx.reply(file=file, embed=tembed)
                        
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    tembed = discord.Embed(title=sticker.name, url=sticker.url)
                    tembed.set_image(url=sticker.url)
                    tembed.set_footer(text=f"已使用偷貼圖\n**需點開下載動圖")
                    
                    await ctx.reply(embed=tembed)
                return
            except Exception as e:
                raise e
        else:
            await ctx.reply(f"沒辦法截取貼圖捏..可能是回覆的訊息不是貼圖哦")

    # @commands.command(aliases=['代寫'], pass_context=True)
    # async def act(self, ctx, member: discord.Member, *, message=None):
    #     if message == None:
    #         return await ctx.send(f'Please provide a message with that!')   

    #     webhook = await ctx.channel.create_webhook(name=member.name)
    #     await webhook.send(str(message), username=member.name, avatar_url=member.avatar)

    #     webhooks = await ctx.channel.webhooks()
    #     for webhook in webhooks:
    #         await webhook.delete()

async def setup(bot):
    await bot.add_cog(Utilities(bot))

