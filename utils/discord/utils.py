import discord
from discord.ext import commands

async def context(ctx, ephemeral=False):
    if isinstance(ctx, discord.Interaction):
        ctx = await commands.Context.from_interaction(ctx)
    try:
        await ctx.defer(ephemeral = ephemeral)
    except:
        pass
    return ctx

def context_or_interaction(ctx: discord.Interaction|commands.Context) -> discord.Interaction|commands.Context:
    if isinstance(ctx, discord.Interaction):
        interaction: discord.Interaction = ctx
        if interaction.is_expired():
            return interaction.followup
        return interaction
    elif isinstance(ctx, commands.Context) and ctx.interaction is not None:
        context: commands.Context = ctx
        if ctx.interaction.is_expired():
            return context.interaction.followup
        return context.interaction
    return ctx

async def response(ctx: discord.Interaction|commands.Context, *args, **kargs):
    ctx = context_or_interaction(ctx)
    if isinstance(ctx, discord.Interaction):
        interaction: discord.Interaction = ctx
        if interaction.response.is_done():
            return await interaction.followup.send(*args, **kargs)
        return await interaction.response.send_message(*args, **kargs)
    return await ctx.send(*args, **kargs)