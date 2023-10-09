import Paginator
import discord
from discord.ext import commands

class EmbedPaginator(Paginator.Simple):

    async def start(self, ctx: discord.Interaction|commands.Context, pages: list[discord.Embed], content: str = None):
        
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.pages = pages
        self.total_page_count = len(pages)
        self.ctx = ctx
        self.current_page = self.InitialPage

        self.PreviousButton.callback = self.previous_button_callback
        self.NextButton.callback = self.next_button_callback
        self.PreviousButton.disabled = False
        self.NextButton.disabled = False

        self.page_counter = Paginator.SimplePaginatorPageCounter(style=self.PageCounterStyle,
                                                       TotalPages=self.total_page_count,
                                                       InitialPage=self.InitialPage)

        self.add_item(self.PreviousButton)
        self.add_item(self.page_counter)
        self.add_item(self.NextButton)

        self.message = await ctx.send(content=content, embed=self.pages[self.InitialPage], view=self, ephemeral=self.ephemeral)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        self.stop()
        await self.message.edit(view=self)