# AiriBot

## Environment setup: python required
this part had been migrated to subprocess which will be auto run during deployment.
For more information, please check `main.py` and `requirements.txt`

## Configure SQLite
https://www.tutorialspoint.com/sqlite/sqlite_installation.htm

## TODO list:
1. add customizable message for greeting message
2. add role based on the reaction given, required more flexibility to assign roles (in manual manner)
3. generate random number/repeated pattern
4. complete tic tac toe game (need range?)
5. youtube video streaming (bot doing streaming in channel?), ~~music streaming~~
6. ~~scoreboad using gsheet~~
7. enhance or reduce image quality
n. *to be added...*

## Available functions as follows (dated at 10/07/2023)
1. send greeting message to member on the newly joined
2. ability to assign the default role when user join
    - administrator need to enable the functionability
    - administrator need to assign a default role to be assigned
3. play **guess random number** using the bot
4. play **paper rock scissor** with the bot
5. extract **emoji** based on condition below:
    - directly extract based on the emoji pass in as argument,
    - extract based on the message reply to,
    - extract based on the reactions given to a message, in addition, the user can provide parameter to specify what is the range of emoji to be extracted
6. extract sticker based on the message reply to, animated png will be converted to gif format
7. youtube music playing at voice channel
8. scoreboard (~~integration with google sheet api, certain functions still underlaying developing progress~~ integrated database)
9. moderation tools - manage emoji (add and remove emoji)

## ERROR during development and solution:
### YoutubeDL : DownloadError: ERROR: ffprobe/avprobe and ffmpeg/avconv not found. Please install one.
    https://stackoverflow.com/questions/30770155/ffprobe-or-avprobe-not-found-please-install-one

### 'choco' is not recognized as an internal or external command
    https://bobbyhadz.com/blog/choco-is-not-recognized-as-internal-or-external-command

### Discord.py bot audio streaming cuts off
    https://stackoverflow.com/questions/66120459/discord-py-bot-audio-streaming-cuts-off

## Experimental library (watching list)
1. Discord bot video: https://github.com/mrjvs/Discord-video-experiment
2. Youtube dl: https://github.com/ytdl-org/youtube-dl 

## References:
1. Python Google Sheets – An Easy Way To Use Google API https://hands-on.cloud/python-google-sheets-api/
2. Discord Emoji https://gist.github.com/scragly/b8d20aece2d058c8c601b44a689a47a0
3. Different prefix for each Cog? https://stackoverflow.com/questions/63105582/different-prefix-for-each-cog
4. https://snyk.io/advisor/python/gspread/functions/gspread.utils.rowcol_to_a1
5. https://pypi.org/project/discord.py-pagination/
6. https://builtin.com/data-science/python-ocr
7. https://stackoverflow.com/questions/1602934/check-if-a-given-key-already-exists-in-a-dictionary
8. https://pypi.org/project/discord-pretty-help/
