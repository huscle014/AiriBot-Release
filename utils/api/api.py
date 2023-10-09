import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import csv 
import json 
import datetime
from utils.database.connection import execute_script, select
from utils.cutils import check_similar
import asyncio
import threading

DATA_PATH = f"{os.curdir}\\resources\\data"

class BlueArhieveAPI:

    @staticmethod
    def fetch_ba_character_list(update = True):
        print("fetch ba latest character list")
        date = datetime.datetime.today().date()
        url = 'https://bluearchive.wiki/wiki/Characters'
        # Create object page
        page = requests.get(url)

        # parser-lxml = Change html to Python friendly format
        # Obtain page's information
        soup = BeautifulSoup(page.text, 'lxml')

        # Obtain information from tag <table>
        table1 = soup.find('table', attrs={"class":'charactertable'})

        if table1 is None:
            print("failed to fetch table data")
            return None

        # Obtain every title of columns with tag <th>
        headers = []
        for i in table1.find_all('th'):
            span = i.find('span')
            if span is not None:
                title = span.get('title')
            else:
                title = i.text
            headers.append(title)

        headers[0] = "Avatar"

        mydata = pd.DataFrame(columns = headers)

        # Create a for loop to fill mydata
        for j in table1.find_all('tr')[1:]:
            row_data = j.find_all('td')
            row = []
            for i in row_data:
                if i.get('class') is not None and 'rarity' in i.get('class'):
                    i = len(i.find_all('img'))
                else:
                    img = i.find('img')
                    if img is not None:
                        if img.get('class') is not None and 'affinity-icon' in img.get('class'):
                            i = img.get('alt')
                        else:
                            i = img.get('src')
                    else:
                        i = i.text
                row.append(i)
            length = len(mydata)
            mydata.loc[length] = row

        filename = f"ba_character_list_{date}"

        if not os.path.isdir(DATA_PATH):
            os.makedirs(DATA_PATH)
        mydata.to_csv(f'{DATA_PATH}/{filename}.csv', index=False)

        BlueArhieveAPI.csv_to_json(f'{DATA_PATH}/{filename}.csv', f'{DATA_PATH}/{filename}.json')

        BlueArhieveAPI.create_patch(filename, 'BA_CHARACTER', ('C_AVATAR','C_NAME','C_RARITY','C_SCHOOL','C_ROLE','C_POSITION','C_ATTACK_TYPE','C_ARMOR_TYPE','C_COMBAT_CLASS','C_WEAPON','C_COVER','C_URBAN','C_OUTDOORS','C_INDOORS','C_RELEASE_DATE'), patch="PATCH BA CHARACTER LIST", update=update)
        print(f"done retrieving character list, dated {date}")

    @staticmethod
    def get_student_skill(name = ''):
        print(f"fetch {name}'s skills")
        url = f"https://bluearchive.wiki/wiki/{name.replace(' ', '_')}"
        # Create object page
        page = requests.get(url)

        # parser-lxml = Change html to Python friendly format
        # Obtain page's information
        soup = BeautifulSoup(page.text, 'lxml')

        # Obtain information from tag <table>
        skilltables = soup.find_all('table', attrs={"class":'skilltable'})

        if skilltables is None:
            print("failed to fetch table data")
            return None
        
        response = {}
        for skill in skilltables:
            body = skill.find_next('tbody')
            # get skill name
            ski = body.find_next('td').getText('|', True).split('|')
            cost = None
            if len(ski) > 1:
                cost = ski[1]
            #get skill desciption
            s = None
            for d in body.find_all('tr', attrs={"class":'summary'}):
                t = d.find_next('p')
                s = t.getText('|', True).split('|')

            response[ski[0]] = {
                "cost": cost,
                "name": s[2],
                "jp_name": s[0],
                "description": ' '.join(s[3:])
            }

        return response

    @staticmethod
    def fetch_ba_school_list(update = True):
        print("fetch ba latest school list")
        date = datetime.datetime.today().date()
        url = 'https://bluearchive.fandom.com/wiki/School'
        # Create object page
        page = requests.get(url)

        # parser-lxml = Change html to Python friendly format
        # Obtain page's information
        soup = BeautifulSoup(page.text, 'lxml')

        # Obtain information from tag <table>
        # tables = soup.find_all('table')

        tables = soup.find(name="span", attrs={"id":"List_of_Named_Schools"}).parent.find_all_next('table')

        if tables is None:
            print("failed to fetch table data")
            return None
        
        headers = ['name','description','logo','color']
        data = pd.DataFrame(columns = headers)
        for table in tables:
            body = table.find_next('tbody')
            row = body.find_all('tr')
            name = row[0].find_next('th')
            color = "#FFFFFF"
            if name is not None:
                styles = {sty.split(":")[0].strip():sty.split(":")[1].strip() for sty in list(filter(None, [style.strip() for style in name.get('style').split(';')]))}
                color = styles.get('background', '#FFFFFF')
                name = name.text.strip()
            
            desc = row[1].find_next('td').text.strip()
            img = row[1].find_next('img')
            if img is not None:
                logo = img.get('src')
                if logo.startswith("data:image"):
                    logo = img.get('data-src')

            length = len(data)
            data.loc[length] = [name, desc, logo, color]
            
            if table.next_sibling.get_text().strip():
                break

        filename = f"ba_school_list_{date}"

        if not os.path.isdir(DATA_PATH):
            os.makedirs(DATA_PATH)
        data.to_csv(f'{DATA_PATH}/{filename}.csv', index=False)

        BlueArhieveAPI.csv_to_json(f'{DATA_PATH}/{filename}.csv', f'{DATA_PATH}/{filename}.json')

        BlueArhieveAPI.create_patch(filename, 'BA_SCHOOL', ('NAME', 'DESCRIPTION', 'ICON', 'COLOR'), patch="PATCH BA SCHOOL LIST", update=update)
        print(f"done retrieving school list, dated {date}")

    @staticmethod
    def fetch_ba_raid(update = True, *, global_only = True):
        print("fetch ba latest raid list")
        date = datetime.datetime.today().date()
        url = 'https://bluearchive.wiki/wiki/Raid'
        # Create object page
        page = requests.get(url)

        # parser-lxml = Change html to Python friendly format
        # Obtain page's information
        soup = BeautifulSoup(page.text, 'lxml')

        # Obtain information from tag <table>
        raid_tab = soup.find_all('table', attrs={"class":'raidtable'})
        for table1 in raid_tab:
            tab = table1.find_parent('article')
            if global_only and not tab.get('data-title') == 'Global':
                continue
            
            server = tab.get('data-title')

            # Obtain every title of columns with tag <th>
            headers = []
            for i in table1.find_all('th'):
                span = i.find('span')
                if span is not None:
                    title = span.get('title')
                else:
                    title = i.text
                headers.append(title)

            headers.insert(0, "Raid id")
            headers[2] = "Type"
            headers[3] = "Start date"
            headers.insert(4, "End date")
            headers.remove('Notes')

            mydata = pd.DataFrame(columns = headers)

            def format_date(input, initial_format = r'%m/%d/%Y %H:%M', target_format = r'%Y-%m-%d %H:%M:%S') -> str:
                input_date = datetime.datetime.strptime(input, initial_format)
                return input_date.strftime(target_format)
            
            # Retrieve the raid boss name list
            r = select('BA_RAID', ('ID', 'R_NAME'))[2]
            raid_boss = [rr.get('R_NAME') for rr in r]
            raid_boss_w_id = {rr.get('R_NAME'): rr.get('ID') for rr in r}

            # Create a for loop to fill mydata
            for j in table1.find_all('tr')[1:]:
                row_data = j.find_all('td')
                row = []
                for n, i in enumerate(row_data):
                    if n in [4]:
                        continue
                    if n == 0:
                        boss_match = check_similar(i.text, raid_boss, 65)
                        row.append(raid_boss_w_id.get(boss_match, "-1"))
                    img = i.find('img')
                    if img is not None:
                        if img.get('alt') is not None and img.get('alt') in ['Outdoor','Indoor','Urban']:
                            i = img.get('alt')
                        else:
                            i = img.get('src')
                    else:
                        i = i.text
                        if ' ~ ' in i:
                            d_arr = i.split(' ~ ')
                            for d in d_arr:
                                row.append(format_date(d))
                            continue
                    row.append(i)
                length = len(mydata)
                mydata.loc[length] = row

            filename = f"ba_raid_list_{server}_{date}"

            if not os.path.isdir(DATA_PATH):
                os.makedirs(DATA_PATH)
            mydata.to_csv(f'{DATA_PATH}/{filename}.csv', index=False)

            BlueArhieveAPI.csv_to_json(f'{DATA_PATH}/{filename}.csv', f'{DATA_PATH}/{filename}.json')

        BlueArhieveAPI.create_patch(filename, 'BA_RAID_RECORD', ('R_ID','R_NAME','R_TYPE','R_START_DATE','R_END_DATE','R_SEASON'), patch="PATCH BA RAID LIST", update=update)
        print(f"done retrieving raid list, dated {date}")
 
    @staticmethod
    def csv_to_json(csvFilePath, jsonFilePath):
        jsonArray = []
        
        #read csv file
        with open(csvFilePath, encoding='utf-8') as csvf: 
            #load csv file data using csv library's dictionary reader
            csvReader = csv.DictReader(csvf) 

            #convert each csv row into python dict
            for row in csvReader: 
                #add this python dict to json array
                jsonArray.append(row)
    
        #convert python jsonArray to JSON String and write to file
        with open(jsonFilePath, 'w', encoding='utf-8') as jsonf: 
            jsonString = json.dumps(jsonArray, indent=4)
            jsonf.write(jsonString)

    @staticmethod
    def create_patch(filename: str, table: str, columns: tuple, patch: str = f"PATCHING RECORDS", update = True):
        json_filename = f"{filename}.json"
        patch_filename = f"patch_{filename}.sql"

        f = open(r".\resources\data" + f"\{json_filename}")
        j = json.load(f)
        
        query = f'--{patch} - {datetime.datetime.today()}\r\n'
        for c in j:
            val = tuple(c.values())
            v = {columns[i] : val[i] for i, _ in enumerate(val)}
            query += f"INSERT OR IGNORE INTO {table} {str(columns)} values{str(val)};\n"

        path_patch = r'.\utils\database\script\patch' + f"\{patch_filename}"
        with open(path_patch, 'w') as f:
            f.write(query)

        if update:
            try:
                asyncio.run(BlueArhieveAPI.update_record(path_patch))
            except:
                scheduler_thread = threading.Thread(target=BlueArhieveAPI.update_record(path_patch))

                # Start the scheduler thread in the background
                scheduler_thread.daemon = True
                scheduler_thread.start()
            print(f"Successfully update the records")

    @staticmethod
    async def update_record(script = ""):
        execute_script(script)

from pixivapi import Client
from pathlib import Path
from pixivapi import Size

class PixivAPI:

    client = Client()

    def authenticate(self, refresh_token):
        self.client.authenticate(refresh_token=refresh_token)

    def fetch_illustration(self, userid: int = 0):
        try:
            illustration = self.client.fetch_illustration(userid)
            illustration.download(
                directory=Path.home() / 'my_pixiv_images',
                size=Size.ORIGINAL,
            )
        except Client.errors.AuthenticationRequired:
            pass

    def fetch_user_illustrations(self, artist_id: int = 2188232):
        directory = Path.home() / 'wlop'

        response = self.client.fetch_user_illustrations(artist_id)
        while True:
            for illust in response['illustrations']:
                illust.download(directory=directory, size=Size.ORIGINAL)

            if not response['next']:
                break

            response = self.client.fetch_user_illustrations(
                artist_id,
                offset=response['next'],
            )