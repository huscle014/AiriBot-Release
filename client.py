import discord

from discord.ext import commands

import asyncio
from time import sleep
from multiprocessing.pool import ThreadPool as Pool
from datetime import datetime
import time
import traceback
import uuid
import threading

from utils.cutils import check_send_email, load_translator
from utils.constant import Constant as const
import utils.logger as logger
from utils.google.gmailclient import GmailClient as gc

from plugin.commandsetup import CogSetup
from plugin.event import setup as eventsetup
import staticrunner
from utils.delayexecutor import run_scheduler

class Client:

    def __init__(self):
        self.__intents = discord.Intents.all()
        self.__bot = commands.Bot(command_prefix='!', intents=self.__intents)
        self.pool = Pool()
        self.logger = logger.Logger("main")
        self.first_loaded = False

    def __startup(self):
        """Handling for exception to trigger restart"""
        try:
            staticrunner.StaticRunner.time_deploy_start = time.time()
            if not self.first_loaded:
                asyncio.run(CogSetup(self.__bot).setup())
                eventsetup(self.__bot)
                load_translator()
                
                # Create a thread for running the scheduler
                scheduler_thread = threading.Thread(target=run_scheduler)

                # Start the scheduler thread in the background
                scheduler_thread.daemon = True
                scheduler_thread.start()

            self.first_loaded = True

            self.__bot.run(const.BOT_TOKEN)
        except Exception as e:
            trace = traceback.format_exc()
            error_case_id = f"{datetime.now()}-{uuid.uuid4()}"
            self.logger.error(f"Error occurs :: \nCase ID :: {error_case_id}\nTraceback :: {trace}")
            if check_send_email(): 
                try:
                    gc.ApplicationCredSender.send_email(subject=f"Error occurs on {const.APPNAME} at {datetime.now()}", 
                                                        recipients=const.SMTP_RCV, body=f"<h3>Traceback</h3><pre>{trace}</pre><h6>Case ID: <span>{error_case_id}</span></h6>")
                except Exception as ex:
                    self.logger.warning(f"Failed to send email with exception :: {ex}")
            
            return f"error occurs :: {e}"

    def run(self):
        result = self.pool.apply_async(self.__startup)
        try:
            value = result.get()
            self.logger.warning(f"{value}\n===================\nRestart process in 3 seconds..")
            sleep(3)
            self.run()
        except Exception as ex:
            self.logger.info(ex)
            print('Unable to get the result')