import discord
from discord.ext import commands

import traceback
import sys
import random

from utils import logger

class MiniGame(commands.Cog):
    """Some minigame."""

    __slots__ = ('bot')

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

    @commands.command(aliases=['井字遊戲'], pass_context=True)
    async def tictactoe(self, ctx):
        await ctx.send(f"目前還沒支援哦")
        pass

    @commands.command(aliases=['猜數'], pass_context=True)
    async def guessnumber(self, ctx):
        ranges = {
            0:{1000: 10},
            1:{100: 5}
        }
        rand = random.randint(0, 1)
        lowbound = 0
        highbound = list(ranges[rand].keys())[0]
        timesguess = ranges[rand][highbound]
        target = random.randint(0, highbound)
        logger.info(f"{target}" )
        await ctx.send(f"在{timesguess}回合内，於{lowbound}至{highbound}之間猜出隨機數")
        while timesguess > 0:
            msg = await self.bot.wait_for("message")
            if msg.content == "結束猜數":
                await ctx.send(f"答案是{target}喲~下次在努力吧")
                break
            try:
                guess = int(msg.content)
                if not guess == target:
                    if guess > target and guess < highbound:
                        highbound = guess
                    elif guess < target and guess > lowbound:
                        lowbound = guess
                    timesguess = timesguess - 1
                    if timesguess == 0:
                        await ctx.reply(f"答案是{target}喲~下次在努力吧")
                        break
                    await ctx.send(f"不對捏~在{lowbound}與{highbound}之間挑個數字\n還有{timesguess}次機會")
                else:
                    await msg.channel.send(f"恭喜猜對了！！ <:honami_confetti:1123510686799122532>", reference=msg)
                    break
            except Exception as ex:
                if isinstance(ex, ValueError):
                    await msg.channel.send(f"不對捏 只能傳數字哦")
                logger.error(ex)
                traceback.print_exception(type(ex), ex, ex.__traceback__, file=sys.stderr)
    
    @commands.command(aliases=['猜拳'], pass_context=True)
    async def rockscissorpaper(self, ctx, guess:str = None):
        if guess is None:
            #TODO: Prompt options to choose
            return await ctx.reply("你耍賴！沒出怎麽判勝敗啦！！")
        await self.determineResultRPS(ctx, guess)

    def checkWinLoseRPS(self, option1 = "", option2 = ""):
        #0 = tie, 1 = win, 2 = lose, combination checking 
        combination = {
            "石頭剪刀": 1, "石頭布": 2, "石頭石頭": 0,
            "剪刀石頭": 2, "剪刀剪刀": 0, "剪刀布": 1,
            "布石頭": 1, "布剪刀": 2, "布布": 0
        }
        tcom = "".join((option1.strip(), option2.strip()))
        if tcom not in combination:
            raise Exception("Combination not in the dictionary!! Please check and revert")
        
        return combination.get(tcom)

    async def determineResultRPS(self, ctx, guess):
        options = ["石頭", "剪刀", "布", "槍"]
        try:
            if guess not in options:
                return await ctx.reply("我不明白你出的選項呢")
            if guess == "槍":
                return await ctx.reply("你作弊！這不是其中的選項吧..（委屈）")
            rand = random.randint(0, 2)
            chosen = options[rand]
            win: int = self.checkWinLoseRPS(chosen, guess)
            rstr: str = f"我出{chosen}！"
            if win == 1:
                rstr += "你輸啦！"
            elif win == 2:
                rstr += "哎呀，怎麽會.. 遇到勁敵了呢.."
            else:
                rstr += "平局了呢.."
            await ctx.reply(rstr)
        except:
            traceback.print_exc()
            await ctx.reply("沒辦法辨識内容呢")

async def setup(bot):
    await bot.add_cog(MiniGame(bot))