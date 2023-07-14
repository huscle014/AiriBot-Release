import discord
from discord.ext import commands, menus
from discord.ext.commands import Bot, has_permissions, CheckFailure
from discord import PartialEmoji as pe, ui

import traceback
import sys
import asyncio

from utils import logger
import staticrunner as sr

import Paginator

class Administration(commands.Cog):
    """Moderation tools and administration related commands."""

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

    class ConfirmRoleOverwrite(discord.ui.View):
        def __init__(self, role: discord.Role, guildID: int):
            super().__init__()
            self.role=role
            self.guildID=guildID
            
        @discord.ui.button(label="是", custom_id="btnyes", style=discord.ButtonStyle.primary)
        async def ansYes(self, interaction: discord.Interaction , button : discord.ui.Button):
            sr.StaticRunner.defaultRoles = self.role
            await self.disable_all_items()
            await interaction.response.edit_message(content=f"{interaction.message.content}\n\n已覆寫記錄，成功將預設身份組設置爲`{self.role.name}`!!", view=self)

        @discord.ui.button(label="否", custom_id="btnno", style=discord.ButtonStyle.red)
        async def ansNo(self, interaction: discord.Interaction , button : discord.ui.Button):
            await self.disable_all_items()
            await interaction.response.edit_message(content=f"{interaction.message.content}\n\n預設身份沒改變，依舊是`{sr.StaticRunner.defaultRole[self.guildID].name}`", view=self)

        async def on_timeout(self):
            await self.disable_all_items()
            await self.message.edit(content="You took too long! Disabled all the components.", view=self)

        async def disable_all_items(self):
            self.ansYes.disabled = True
            self.ansNo.disabled = True

    """
    moderation - manage roles
    """
    @commands.command(aliases=['預設身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def set_default_role(self, ctx, role: discord.Role = None):
        """Set the default role of the server when a new member join."""

        if role is None:
            await ctx.reply(f"使用方法不對捏~\n應該這樣使用喲：**預設身份組** `role:身分組`")
            return
        if ctx.message.guild.id in sr.StaticRunner.defaultRole:
            if sr.StaticRunner.defaultRole[ctx.message.guild.id] is not None:
                logger.info(sr.StaticRunner.defaultRole[ctx.message.guild.id].name)
                message = await ctx.reply(f"預設身分組已設置為`{sr.StaticRunner.defaultRole[ctx.message.guild.id].name}`，是否要覆寫？", view=self.ConfirmRoleOverwrite(role, ctx.message.guild.id))
                #await message.edit(view=None)
                return
        sr.StaticRunner.defaultRole[ctx.message.guild.id] = discord.Role
        await ctx.reply(f"成功將預設身份組設置爲`{role.name}`!!")

    @commands.command(aliases=['查看預設身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def check_default_role(self, ctx):
        """Check the current default role of the server."""

        if ctx.message.guild.id not in sr.StaticRunner.defaultRole:
            await ctx.reply(f"目前沒有預設身份組喲！")
        else:
            await ctx.reply(f"目前的預設身份組爲`{sr.StaticRunner.defaultRole[ctx.message.guild.id].name}`")

    @commands.command(aliases=['移除預設身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def remove_default_role(self, ctx):
        """Remove the default role of the server."""

        if ctx.message.guild.id not in sr.StaticRunner.defaultRole:
            await ctx.reply(f"目前沒有預設身份組喲！")
        else:
            sr.StaticRunner.defaultRole[ctx.message.guild.id] = None
            await ctx.reply(f"已把預設身份組移除")

    @commands.command(aliases=['身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def give_role(self, ctx, user: discord.Member, role: discord.Role):
        """Give a role to a targeted member. *the user need to have manage roles permission to execute the command"""

        #await ctx.message.delete()
        #role = discord.utils.find(lambda r: r.name == 'Member', ctx.message.guild.roles)
        if role in user.roles:
            await ctx.reply(f"成員已經有該身份組了喲~ (╹ڡ╹ )") #, ephemeral=True)
        else:
            await user.add_roles(role)
            await ctx.send(f"<@{user.id}>，管管給你了`{role.name}`的身份組，如果有疑問可以向任何管管回應喲！")

    @commands.command(aliases=['移除身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def remove_role(self, ctx, user: discord.Member, role: discord.Role):
        #await ctx.message.delete()
        #role = discord.utils.find(lambda r: r.name == 'Member', ctx.message.guild.roles)
        if role not in user.roles:
            await ctx.reply(f"成員目前沒有該身份組喲~ (╹ڡ╹ )") #, ephemeral=True)
        else:
            await user.remove_roles(role)
            await ctx.reply(f"已將該成員的身份組移除了喲")

    """
    moderation - manage guild emoji
    """
    @commands.command(aliases=['添加表符'], pass_context=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def add_emoji(self, ctx: commands.Context, name: str = None):
        attch = ctx.message.attachments
        if attch:
            for att in attch:
                if att.content_type.startswith("image"):
                    attch: discord.Attachment = att
                    break
        else:
            return await ctx.reply(f"沒附上圖片呢")
        if name is None:
            msgname: discord.Message = await ctx.reply(f"表符要設定什麽名字呢？（請回覆此訊息）")
            def check(m):
                if m.author == ctx.author and m.reference is not None:
                    if m.reference.message_id == msgname.id:
                        return True
                return False
            
            msg = await self.bot.wait_for("message", check=check)
            name = msg.content
        logger.debug(f"name of the emoji :: {name} {attch.filename} ")
        logger.debug(f"{discord.utils.get(ctx.guild.emojis, name=name)}")
        try:
            file: discord.File = await attch.to_file()
            image = file.fp.read()
            
            emoji = await ctx.guild.create_custom_emoji(name=name, image=image)

            await ctx.reply(f"已添加新的表符 `{name}` {emoji}") 
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.reply(f"無法添加表符，遇到了一點問題呢") 

    @commands.command(name='removeemoji', aliases=['移除表符'], pass_context=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def remove_emoji(self, ctx: commands.Context, name: str = None, reason: str = None):
        if name is not None:
            emoji = discord.utils.get(ctx.guild.emojis, name=name)
            if emoji is not None:
                logger.debug(f"partial emoji retrieved :: {emoji}")
                return await self.__delete_emoji_method(ctx, emoji, reason, f"是否確定將{emoji}刪除？\n如確定刪除表符，在這則訊息留個✅，否則留個❌")
            else:
                emoji: pe = pe.from_str(name)
                if emoji is not None and emoji.id is not None:
                    return await self.__delete_emoji_method(ctx, emoji, reason)
                return await ctx.reply(f"沒找到所提供的表符呢")
        else:
            # TODO: show the list of the emote using pagination and buttons << next time ba
            emojis = ctx.guild.emojis
            page_limit = 15
            index = 0
            embeds = []
            page = 1

            embed = discord.Embed(color=discord.Color.from_rgb(255, 170, 204))
            for emoji in emojis:
                if not index == 0 and (index % page_limit == 0 or index == len(emojis) - 1):
                    if index == len(emojis) - 1:
                        if index % 3 == 1:
                            embed.add_field(name="", value="\b")
                            embed.add_field(name="", value="\b")
                        elif index % 3 == 2:
                            embed.add_field(name="", value="\b")
                        
                    embed.title = f"Emoji list in `{ctx.guild.name}`"
                    embed.description = f"這些是伺服器裏的全部表符哦~ 可以複製後輸入 `移除表符 +表符` 以進行刪除動作哦"
                    embed.set_footer(text=f"Page {page}")
                    embeds.append(embed)
                    
                    embed = discord.Embed(color=discord.Color.from_rgb(255, 170, 204))
                    page = page + 1

                embed.add_field(name="", value=f"{emoji} `{str(emoji.name)}`")
                index = index + 1

            ... # Inside a command.
            await Paginator.Simple(ephemeral=True, timeout=180).start(ctx, pages=embeds)

    async def __delete_emoji_method(self, ctx, emoji: discord.PartialEmoji, reason: str, confirm_text = "如確定刪除表符，在這則訊息留個✅，否則留個❌"):
        msg: discord.Message = await ctx.reply(confirm_text) 
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        def is_owner(reaction, user):
            if reaction.message.id == msg.id and not user.id == ctx.author.id:
                return False
            if reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '❌':
                raise Administration.CancelledAction("canceled, user reacted with ❌")
            return reaction.message.id == msg.id and user.id == ctx.author.id and str(reaction.emoji) == '✅'
        try:
            done, pending = await asyncio.wait([
                # self.bot.loop.create_task(self.bot.wait_for('message')),
                self.bot.loop.create_task(self.bot.wait_for('reaction_add', check=is_owner))
            ], return_when=asyncio.FIRST_COMPLETED)

            reaction_done = done.pop().result()
            logger.debug(f"result :: {reaction_done}")

            await ctx.guild.delete_emoji(emoji, reason=reason)
            reason = f"\n刪除理由：`{reason}`" if reason is not None else ''

            return await ctx.reply(f"已把 `{emoji.name}` 刪除 {reason}") 
        except Administration.CancelledAction:
            return await ctx.reply(f"已取消把 `{emoji.name}` 刪除的請求哦") 
        except Exception as error:
            logger.debug(error)
            return await ctx.reply(f"無法刪除 `{emoji.name}` ，似乎遇到了一點麻煩") 
        
    class CancelledAction(Exception):
        # handle exception for cancelled action from user
        pass

    class DefaultButton(discord.ui.Button):
        def __init__(self, custom_id, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.custom_id = custom_id


    class DefaultView(discord.ui.View):
        def __init__(self):
            super().__init__()

        async def callback(self, button: discord.ui.Button, interaction: discord.Interaction):
            self.disable_all_items()
            self.stop()
            await interaction.response.defer()
            await interaction.edit_original_message(view=self)


async def setup(bot):
    await bot.add_cog(Administration(bot))