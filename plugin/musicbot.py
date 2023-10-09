"""
Music bot for discord, using latest git sources for youtube-dl library
due to the current release have issue when unable to extract uploader id

source: https://stackoverflow.com/a/66669004, by Aditya Tomar
translated and customised message based on own requirements
"""

import discord
from discord.ext import commands
from discord import app_commands
from discord.enums import Locale
from discord.app_commands import locale_str
import random
import asyncio
import itertools
import sys
import traceback
from async_timeout import timeout
from functools import partial
import youtube_dl
from youtube_dl import YoutubeDL
from pytube import Playlist
import validators

from utils.cutils import convertSeconds
import utils.logger as logger
from utils.discord.utils import context, response

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # ipv6 addresses cause issues sometimes
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]
}

ffmpegopts = {
    # 'before_options': '-nostdin',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = YoutubeDL(ytdlopts)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx: discord.Interaction|commands.Context, search: str, *, loop, download=False, prompt=True, channel: discord.TextChannel|discord.Thread = None):
        ctx = await context(ctx)
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        # embed = discord.Embed(title="愛莉已幫忙把歌曲新增入清單内哦~", description=f"Queued [{data['title']}]({data['webpage_url']}) [{ctx.author.mention}]", color=discord.Color.from_rgb(255, 170, 204))
        # await response(ctx, embed=embed)

        title = data["title"]
        uploader = data["uploader"]
        url = data["webpage_url"]
        duration = data["duration"]

        em1 = discord.Embed(description = f">>> ### **{title}** \nby **{uploader}**\n\n鏈接由 {ctx.author.mention} 提供 <:airi_cat:1124173240621867078>\n_ _",
                            color = discord.Colour.from_rgb(255, 170, 204))
        videoID = url.split("watch?v=")[1].split("&")[0]

        if prompt:
            em1.set_thumbnail(url = f'https://img.youtube.com/vi/{videoID}/default.jpg'.format(videoID = videoID))
            em1.add_field(name="🔗 原網址", value=f"[Youtube]({url})")
            em1.add_field(name=":pencil: 標題",value=title)
            em1.add_field(name=":timer: 時長",value=convertSeconds(duration))
            # em1.add_field(name=":headphones: 清單内索引",value=f"{len(music_queue)}/{len(music_queue)}")
            em1.set_footer(text=f'© Youtube ptd, 使用條款請參閲Youtube，音樂版權歸著作者所有')
            em1.set_author(name=uploader, url=url)

        if channel is not None:
            await channel.send(embed=em1, content="愛莉已幫忙把歌曲新增入清單内哦~")
        else:
            await ctx.reply(embed=em1, content="愛莉已幫忙把歌曲新增入清單内哦~")

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title'], 'duration': data['duration']}

        return cls(discord.FFmpegPCMAudio(source, **ffmpegopts), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming li expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpegopts), data=data, requester=requester)


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
                # await self._channel.send("愛莉已把目前清單内的歌曲都播放完畢嘍~ <:aibi_comfy:1124959827416854529>") 
            except asyncio.TimeoutError as e:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'愛莉似乎遇上了一些問題，沒辦法處理，可能需要一些時間解決\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source
            
            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))

            url = source.web_url
            requestor = source.requester
            title = source.title
            duration = source.duration
            uploader = source.uploader

            em1 = discord.Embed(title = "▶ 目前正在收聽..", 
                                description = f">>> ### **{title}** \nby **{uploader}**\n\n鏈接由 {requestor.mention} 提供 <:airi_cat:1124173240621867078>\n_ _",
                                color = discord.Colour.from_rgb(255, 170, 204))#requestor.color)
            videoID = source.web_url.split("watch?v=")[1].split("&")[0]

            em1.set_thumbnail(url = f'https://img.youtube.com/vi/{videoID}/default.jpg'.format(videoID = videoID))
            em1.add_field(name="🔗 原網址", value=f"[Youtube]({url})")
            em1.add_field(name=":pencil: 標題",value=title)
            em1.add_field(name=":timer: 時長",value=convertSeconds(duration))
            em1.set_footer(text=f'© Youtube ptd, 使用條款請參閲Youtube，音樂版權歸著作者所有')
            em1.set_author(name=uploader, url=url)
            self.np = await self._channel.send(embed=em1)

            await self.next.wait() 

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players', 'logger')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.logger = logger.Logger("Music")

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx :discord.Interaction| commands.Context, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await response(ctx, '這個指令無法在私訊使用哦~')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await response(ctx, '愛莉似乎遇上了一些問題，沒辦法處理，可能需要一些時間解決')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    # @commands.hybrid_command(name='join', aliases=['connect', '加入語音'], description="連接到語音")
    @app_commands.command(name='join', description='Connect to voice.', extras={"name_localizations":{"zh-TW":"加入語音"}, "description_localizations":{"zh-TW":"連接到語音"}})
    @app_commands.describe(channel="The channel to connect to. If a channel is not specified, default join channel user in.")
    async def connect_(self, ctx :discord.Interaction| commands.Context, *, channel: discord.VoiceChannel=None):
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voce channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        ctx = await context(ctx)

        await self.__connect_(ctx, channel=channel)

    async def __connect_(self, ctx :discord.Interaction| commands.Context, *, channel: discord.VoiceChannel=None):
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                embed = discord.Embed(title="", description="你現在不在語音頻道捏~ 你需要加入語音頻道以使用這個指令", color=discord.Color.from_rgb(255, 170, 204))
                return await response(ctx, embed=embed)

        vc: discord.VoiceClient = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return await ctx.reply("愛莉已經在語音房裏了哦~")
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect(self_deaf = True)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')
        await response(ctx, f'**已加入 `{channel}`**')

    @commands.hybrid_command(name='play', aliases=['播放'], description="串流音樂")
    async def play_(self, ctx :discord.Interaction| commands.Context, *, search: str = None):
        """Request a song and add it to the queue.
        This command attempts to join a valid voice channel if the bot is not already in one.
        Uses YTDL to automatically search and retrieve a song.
        Parameters
        ------------
        search: str [Required]
            The song to search and retrieve using YTDL. This could be a simple search, an ID or URL.
        """
        ctx = await context(ctx)

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.__connect_)

        player = self.get_player(ctx)

        # If download is False, source will be a dict which will be used later to regather the stream.
        # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

        await player.queue.put(source)

    @commands.hybrid_command(name='add-playlist', aliases=['playlist', 'addlist', '新增播放清單'], description="新增播放清單")
    async def add_playlist_(self, ctx: commands.Context, playlist_url: str, index_from: int = 1, index_to: int = -1):
        """Add playlist into queue"""

        ctx = await context(ctx)

        index = 0
        if not validators.url(playlist_url):
            playlist_url = "https://www.youtube.com/playlist?list=" + playlist_url

        vc = ctx.voice_client
        if not vc:
            await ctx.invoke(self.__connect_)
        player = self.get_player(ctx)

        play_list = Playlist(playlist_url)
        playlist_len = len(play_list)
        if index_to == -1 or index_to > playlist_len:
            index_to = playlist_len

        videos_added = []

        thread = await ctx.channel.create_thread(
            name=f"{play_list.title} requested by {ctx.author.name}",
            type=discord.ChannelType.public_thread
        )
        
        thumbnail = ""
        number_of_song = 0
        total_duration = 0

        for video in play_list.videos:
            if index == 0:
                thumbnail = video.thumbnail_url

            if self.players.get(ctx.guild.id) is None:
                await ctx.reply(embed=discord.Embed(title="", description="已取消將歌曲加入歌單", color=discord.Color.from_rgb(255, 170, 204)))
                return
            
            if index == index_to:
                break

            if index >= index_from - 1 and index <= index_to:
                
                source = await YTDLSource.create_source(ctx, video.watch_url, loop=self.bot.loop, download=False, channel=thread)

                await player.queue.put(source)
                videos_added.append({
                    "title":video.title,
                    "webpage_url":video.watch_url,
                    "duration":convertSeconds(video.length),
                    "author":video.author,
                    "channel_url":video.channel_url
                })
                total_duration += video.length
                number_of_song += 1
            index += 1

        fmt = '>>> ' + '\n'.join(f"{(videos_added.index(_)) + 1}. [{_['title']}]({_['webpage_url']}) |  {_['duration']} by [{_['author']}]({_['channel_url']})\n" for _ in videos_added)

        embed = discord.Embed(
            title="愛莉已幫忙把歌曲新增入清單内哦~", 
            description=fmt, 
            color=discord.Color.from_rgb(255, 170, 204))
        
        description = '-'
        try:
            description = play_list.description
        except:
            pass
        
        embed.set_thumbnail(url = thumbnail)
        embed.add_field(name=":pencil: 標題", value=f"[{play_list.title}]({playlist_url})")
        embed.add_field(name=":clipboard: 説明",value=description)
        embed.add_field(name=":timer: 曲數/縂時長",value=f"{number_of_song} | {convertSeconds(total_duration)}")
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name='pause', aliases=['暫停播放'], description="暫停音樂播放")
    async def pause_(self, ctx):
        """Pause the currently playing song."""

        ctx = await context(ctx)

        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            embed = discord.Embed(title="", description="目前沒有正在播放的歌曲喲 <:airi_sigh:1123774050058117160>", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)
        elif vc.is_paused():
            return

        vc.pause()
        await response(ctx, ":pause_button: 目前已暫停播放哦")

    @commands.hybrid_command(name='resume', aliases=['繼續播放'],  description="恢復音樂播放")
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        ctx = await context(ctx)

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)
        elif not vc.is_paused():
            return

        vc.resume()
        await response(ctx, ":arrow_forward: 坐好嘍~ 愛莉要開車了！")

    @commands.hybrid_command(name='skip', aliases=['跳過'], description="跳轉至下一曲")
    async def skip_(self, ctx):
        """Skip the song."""
        ctx = await context(ctx)

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.defer()
    
    @commands.hybrid_command(name='remove', aliases=['移除'], description="從清單内移除歌曲")
    async def remove_(self, ctx :discord.Interaction| commands.Context, pos : int=None):
        """Removes specified song from queue"""
        ctx = await context(ctx)

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        player = self.get_player(ctx)
        if pos == None:
            player.queue._queue.pop()
            await ctx.defer()
        else:
            try:
                s = player.queue._queue[pos-1]
                del player.queue._queue[pos-1]
                embed = discord.Embed(title="", description=f"已將 [{s['title']}]({s['webpage_url']}) 移除哦 [{s['requester'].mention}]", color=discord.Color.from_rgb(255, 170, 204))
                await response(ctx, embed=embed)
            except:
                embed = discord.Embed(title="", description=f'找不到捏 這個索引"{pos}"似乎沒有正在排的歌曲', color=discord.Color.from_rgb(255, 170, 204))
                await response(ctx, embed=embed)
    
    @commands.hybrid_command(name='clear', aliases=['清空歌單'], description="清空歌單")
    async def clear_(self, ctx):
        """Deletes entire queue of upcoming songs."""
        ctx = await context(ctx)

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        player = self.get_player(ctx)
        player.queue._queue.clear()
        await response(ctx, '**愛莉已把歌單清空哦**')

    @commands.hybrid_command(name='queue', aliases=['查看歌單'], description="顯示歌單詳情")
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        ctx = await context(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        player = self.get_player(ctx)
        if player.queue.empty():
            embed = discord.Embed(title="", description="目前歌曲清單裏沒有歌曲哦~ 可以使用 **新增歌曲入列** 新增入待播清單", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)
        
        if vc.source is None:
            embed = discord.Embed(title="", description="目前的音樂可能還沒讀取完畢喲~ 可以稍微再等一會兒", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        seconds = vc.source.duration % (24 * 3600) 
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        # Grabs the songs in the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))
        fmt = '\n'.join(f"`{(upcoming.index(_)) + 1}.` [{_['title']}]({_['webpage_url']}) | ` {convertSeconds(_['duration'])} 由 {_['requester']} 請求`\n" for _ in upcoming)
        # fmt = '\n'.join(f"`{(upcoming.index(_)) + 1}.` [{_['title']}]({_['webpage_url']}) | ` 由 {_['requester']} 請求`\n" for _ in upcoming)
        fmt = f"\n__目前播放中__:\n[{vc.source.title}]({vc.source.web_url}) | ` {duration} 由 {vc.source.requester} 加入清單`\n\n__下一首:__\n" + fmt + f"\n**目前還有 {len(upcoming)} 首曲在等待清單中**"
        embed = discord.Embed(title=f'Queue for {ctx.guild.name}', description=fmt, color=discord.Color.from_rgb(255, 170, 204))
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar)

        await response(ctx, embed=embed)

    @commands.hybrid_command(name='np', aliases=['目前單曲'], description="顯示當前播放的歌曲")
    async def now_playing_(self, ctx):
        """Display information about the currently playing song."""
        ctx = await context(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        player = self.get_player(ctx)
        if not player.current:
            embed = discord.Embed(title="", description="目前沒有正在播放的歌曲喲~", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)
        
        seconds = vc.source.duration % (24 * 3600) 
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        embed = discord.Embed(title="", description=f"[{vc.source.title}]({vc.source.web_url}) [{vc.source.requester.mention}] | `{duration}`", color=discord.Color.from_rgb(255, 170, 204))
        embed.set_author(icon_url=self.bot.user.avatar, name=f"目前播放中 🎶")
        await response(ctx, embed=embed)

    @commands.hybrid_command(name='volume', aliases=['音量'], description="改變音量")
    async def change_volume(self, ctx :discord.Interaction| commands.Context, *, vol: float=None):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        ctx = await context(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)
        
        if not vol:
            embed = discord.Embed(title="", description=f"🔊 **{(vc.source.volume)*100}%**", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        if not 0 < vol < 101:
            embed = discord.Embed(title="", description="不對捏~ 音量只可以在0至100之間喲", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        embed = discord.Embed(title="", description=f'**`{ctx.author}`** 已把音量設置成 **{vol}%**', color=discord.Color.from_rgb(255, 170, 204))
        await response(ctx, embed=embed)

    @commands.hybrid_command(name='leave', aliases=["離開語音"], description="停止音樂並與語音斷開連接")
    async def leave_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """
        ctx = await context(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="愛莉目前並不在任何語音頻道内哦", color=discord.Color.from_rgb(255, 170, 204))
            return await response(ctx, embed=embed)
            
        await response(ctx, embed=discord.Embed(title="", description=f'**愛莉離開了喲**', color=discord.Color.from_rgb(255, 170, 204)))

        await self.cleanup(ctx.guild)


async def setup(bot):
    await bot.add_cog(Music(bot))