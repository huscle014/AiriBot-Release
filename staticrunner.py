import discord

class StaticRunner:
    defaultRole: dict[int: discord.Role] = {0: None}
    setDefaultRoleOnUserJoin: dict[int: bool] = {0: False}