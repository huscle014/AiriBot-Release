import discord
from discord.ext import commands
from discord.ext.commands import has_permissions
# from discord import PartialEmoji as pe, ui
from discord import app_commands

import traceback
import sys
import asyncio
# import os

import utils.logger as logger
import staticrunner as sr
# from utils.cutils import apngtogif

import Paginator

class Administration(commands.Cog):
    """Moderation tools and administration related commands."""

    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot
        self.logger = logger.Logger("Administration")

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
    @commands.hybrid_command(name="set-default-role", aliases=['預設身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    @app_commands.describe(role="the server role to be set as the default role upon member join. ")
    async def set_default_role(self, ctx, role: discord.Role):
        """Set the default role of the server when a new member join."""

        if ctx.message.guild.id in sr.StaticRunner.defaultRole:
            if sr.StaticRunner.defaultRole[ctx.message.guild.id] is not None:
                d_role = ctx.guild.get_role(int(sr.StaticRunner.defaultRole[ctx.message.guild.id]))
                message = await ctx.send(f"預設身分組已設置為`{d_role.name}`，是否要覆寫？", view=self.ConfirmRoleOverwrite(role, ctx.message.guild.id))
                await message.edit(view=None)
                return
        sr.StaticRunner.defaultRole[ctx.message.guild.id] = role.id
        await ctx.send(f"成功將預設身份組設置爲`{role.name}`!!")

    @commands.hybrid_command(name="check-default-role", aliases=['查看預設身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def check_default_role(self, ctx):
        """Check the current default role of the server."""

        if ctx.message.guild.id not in sr.StaticRunner.defaultRole:
            await ctx.send(f"目前沒有預設身份組喲！")
        else:
            d_role = ctx.guild.get_role(int(sr.StaticRunner.defaultRole[ctx.message.guild.id]))
            await ctx.send(f"目前的預設身份組爲`{d_role.name}`")

    @commands.hybrid_command(name="remove-default-role", aliases=['移除預設身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    async def remove_default_role(self, ctx):
        """Remove the default role of the server."""

        if ctx.message.guild.id not in sr.StaticRunner.defaultRole:
            await ctx.send(f"目前沒有預設身份組喲！")
        else:
            sr.StaticRunner.defaultRole[ctx.message.guild.id] = 0
            await ctx.send(f"已把預設身份組移除")

    @commands.hybrid_command(name="default-role-on-member-join", pass_context=True)
    @has_permissions(manage_roles=True)
    async def enable_default_role_on_join(self, ctx, enable: bool):
        current_ = sr.StaticRunner.setDefaultRoleOnUserJoin.get(ctx.guild.id, False)
        if enable:
            if current_:
                return await ctx.send("原本就已設置哦~", ephemeral=True)
        else:
            if not current_:
                return await ctx.send("沒有設置自動給予身份組哦~", ephemeral=True)
            await ctx.send("已設置哦", ephemeral=True)
        await ctx.send(f"已把自動給予身份組的設置{'開啓' if enable else '關閉'}哦~", ephemeral=True)
        sr.StaticRunner.setDefaultRoleOnUserJoin[ctx.guild.id] = enable

    @commands.hybrid_command(name="assign-role", aliases=['身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    @app_commands.rename(user='server-member')
    @app_commands.describe(role="server role")
    async def give_role(self, ctx, user: discord.Member, role: discord.Role):
        """Give a role to a targeted member. """

        if role in user.roles:
            await ctx.send(f"成員已經有該身份組了喲~ (╹ڡ╹ )", ephemeral=True)
        else:
            await user.add_roles(role)
            await ctx.send(f"<@{user.id}>，管管給你了`{role.name}`的身份組，如果有疑問可以向任何管管回應喲！")

    @commands.hybrid_command(name="remove-role", aliases=['移除身份組'], pass_context=True)
    @has_permissions(manage_roles=True)
    @app_commands.rename(user='server-member')
    @app_commands.describe(role="server role")
    async def remove_role(self, ctx, user: discord.Member, role: discord.Role):
        """Remove a role from a member"""
        if role not in user.roles:
            await ctx.send(f"成員目前沒有該身份組喲~ (╹ڡ╹ )", ephemeral=True)
        else:
            await user.remove_roles(role)
            await ctx.send(f"已將該成員的身份組移除了喲", ephemeral=True)

    """
    moderation - manage guild emoji
    """
    @commands.hybrid_command(name="add-emoji", aliases=['添加表符'], pass_context=True)
    @has_permissions(manage_emojis_and_stickers=True)
    @app_commands.describe(name="the name of the emoji to be given")
    @app_commands.describe(image="the image of the emoji to be created")
    async def add_emoji(self, ctx: commands.Context, name: str, image: discord.Attachment):
        """Add emoji to the server"""

        if ctx.guild.emoji_limit == len(ctx.guild.emojis):
            return await ctx.send(f"無法添加表符！已達目前伺服器限制\nFailed to add emoji, maximum emoji limit reached")

        if not image.content_type.startswith("image"):
            return await ctx.send(f"不是圖片捏")
        if name is None:
            msgname: discord.Message = await ctx.send(f"表符要設定什麽名字呢？（請回覆此訊息）")
            def check(m):
                if m.author == ctx.author and m.reference is not None:
                    if m.reference.message_id == msgname.id:
                        return True
                return False
            
            msg = await self.bot.wait_for("message", check=check)
            name = msg.content
        self.logger.debug(f"name of the emoji :: {name} {image.filename} ")
        try:
            file: discord.File = await image.to_file()
            image = file.fp.read()
            
            emoji = await ctx.guild.create_custom_emoji(name=name, image=image)

            await ctx.send(f"已添加新的表符 `{name}` {emoji}") 
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send(f"無法添加表符，遇到了一點問題呢") 

    @commands.hybrid_command(name="remove-emoji", aliases=['移除表符'], pass_context=True)
    @has_permissions(manage_emojis_and_stickers=True)
    @app_commands.describe(emoji="the emoji to be removed from the server")
    @app_commands.describe(reason="the reason to remove the emoji, for audit purpose")
    async def remove_emoji(self, ctx: commands.Context, emoji: discord.PartialEmoji, reason: str = None):
        """Remove emoji from the server"""

        emoji = discord.utils.get(ctx.guild.emojis, name=emoji.name)
        if emoji is not None:
            self.logger.debug(f"partial emoji retrieved :: {emoji}")
            return await self.__delete_emoji_method(ctx, emoji, reason, f"是否確定將{emoji}刪除？\n如確定刪除表符，在這則訊息留個✅，否則留個❌")
        else:
            return await ctx.send(f"沒找到所提供的表符呢")
        # if name is not None:
        #     emoji = discord.utils.get(ctx.guild.emojis, name=emoji.name)
        #     if emoji is not None:
        #         self.logger.debug(f"partial emoji retrieved :: {emoji}")
        #         return await self.__delete_emoji_method(ctx, emoji, reason, f"是否確定將{emoji}刪除？\n如確定刪除表符，在這則訊息留個✅，否則留個❌")
        #     else:
        #         emoji: pe = pe.from_str(name)
        #         if emoji is not None and emoji.id is not None:
        #             return await self.__delete_emoji_method(ctx, emoji, reason)
        #         return await ctx.send(f"沒找到所提供的表符呢")
        # else:
        #     # TODO: show the list of the emote using pagination and buttons << next time ba
        #     emojis = ctx.guild.emojis
        #     page_limit = 15
        #     index = 0
        #     embeds = []
        #     page = 1

        #     embed = discord.Embed(color=discord.Color.from_rgb(255, 170, 204))
        #     for emoji in emojis:
        #         if not index == 0 and (index % page_limit == 0 or index == len(emojis) - 1):
        #             if index == len(emojis) - 1:
        #                 if index % 3 == 1:
        #                     embed.add_field(name="", value="\b")
        #                     embed.add_field(name="", value="\b")
        #                 elif index % 3 == 2:
        #                     embed.add_field(name="", value="\b")
                        
        #             embed.title = f"Emoji list in `{ctx.guild.name}`"
        #             embed.description = f"這些是伺服器裏的全部表符哦~ 可以複製後輸入 `移除表符 +表符` 以進行刪除動作哦"
        #             embed.set_footer(text=f"Page {page}")
        #             embeds.append(embed)
                    
        #             embed = discord.Embed(color=discord.Color.from_rgb(255, 170, 204))
        #             page = page + 1

        #         embed.add_field(name="", value=f"{emoji} `{str(emoji.name)}`")
        #         index = index + 1

        #     ... # Inside a command.
        #     await Paginator.Simple(ephemeral=True, timeout=180).start(ctx, pages=embeds)

    async def __delete_emoji_method(self, ctx, emoji: discord.PartialEmoji, reason: str, confirm_text = "如確定刪除表符，在這則訊息留個✅，否則留個❌"):
        msg: discord.Message = await ctx.send(confirm_text) 
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
            self.logger.debug(f"result :: {reaction_done}")

            await ctx.guild.delete_emoji(emoji, reason=reason)
            reason = f"\n刪除理由：`{reason}`" if reason is not None else ''

            return await ctx.send(f"已把 `{emoji.name}` 刪除 {reason}") 
        except Administration.CancelledAction:
            return await ctx.send(f"已取消把 `{emoji.name}` 刪除的請求哦") 
        except Exception as error:
            self.logger.debug(error)
            return await ctx.send(f"無法刪除 `{emoji.name}` ，似乎遇到了一點麻煩") 
        finally:
            try:
                await msg.delete()
            except:
                pass

    @commands.hybrid_command(name="add-sticker", aliases=['添加貼圖'], pass_context=True)
    @has_permissions(manage_emojis_and_stickers=True)
    @app_commands.describe(name="the name of the sticker to be given")
    @app_commands.describe(description="the description of the sticker")
    @app_commands.describe(reason="the description of the sticker")
    @app_commands.describe(emoji="the emoji which the sticker relate to")
    @app_commands.describe(reason="the reason to creation of the sticker, mainly for audit log")
    async def add_sticker(self, ctx: commands.Context, name: str, description: str, emoji:str, image: discord.Attachment, reason: str = None):
        """Add sticker to the server"""

        if len(ctx.guild.stickers) == ctx.guild.sticker_limit:
            return await ctx.send(f"無法添加貼圖！已達目前伺服器限制\nFailed to create sticker, maximum sticker limit reached")
        
        if not image.content_type.startswith("image"):
            return await ctx.send(f"不是圖片捏\nThe attachment seem not like a valid image")
        if name is None:
            msgname: discord.Message = await ctx.send(f"表符要設定什麽名字呢？（請回覆此訊息）")
            def check(m):
                if m.author == ctx.author and m.reference is not None:
                    if m.reference.message_id == msgname.id:
                        return True
                return False
            
            msg = await self.bot.wait_for("message", check=check)
            name = msg.content
        self.logger.debug(f"name of the sticker :: {name} {image.filename} ")
        try:
            # path = None
            # try:
            #     if image.content_type == 'image/png':
            #         path, filename = apngtogif(image.url)
            #         file = discord.File(path, filename=filename)
            #         sticker = await ctx.guild.create_sticker(name=name, description=description, emoji=emoji, reason=reason, file=file)

            #         file.close()
                    
            #         if path is not None and os.path.exists(path):
            #             os.remove(path)
            # except:
            #     file: discord.File = await image.to_file()
            #     sticker = await ctx.guild.create_sticker(name=name, description=description, emoji=emoji, reason=reason, file=file)

            
            file: discord.File = await image.to_file()
            sticker = await ctx.guild.create_sticker(name=name, description=description, emoji=emoji, reason=reason, file=file)
            
            await ctx.send(f"已添加新的貼圖 `{name}`\nAdded new sticker to the server") 

            context: commands.Context = await self.bot.get_context(ctx.message)
            await context.send(stickers=[sticker])
        except Exception as error:
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send(f"無法添加貼圖，遇到了一點問題呢\nFailed to create sticker, \nError descrption:`{error}`") 
        
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