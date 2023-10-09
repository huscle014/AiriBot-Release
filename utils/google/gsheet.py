from __future__ import print_function

import os
import os.path
import re

import validators
import gspread

import utils.logger as logger

class GSheet:
    # If modifying these scopes, delete the file token.json.
    SCOPES = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive.file',
                'https://www.googleapis.com/auth/drive']

    CRED_DIR_PATH = f"{os.getcwd()}\\gworkshop_cred\\"
    SERVICE_ACCOUNT = f"{CRED_DIR_PATH}service_account.json"

    __slots__ = ('spreadsheet_id', 'client', 'sheet', 'logger')

    def __init__(self, _spreadsheet_id: str = ''):
        self.spreadsheet_id = _spreadsheet_id
        self.client = None
        self.sheet = None
        self.logger = logger.Logger("GSheet")

        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        
        self.client = self.outh_connect()
        if not self.spreadsheet_id == '':
            self.open_sheet()

    def outh_connect(self):
        gc = None
        try:
            gc = gspread.service_account(filename=self.SERVICE_ACCOUNT)
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
        return gc

    def create(self, title):
        return self.client.create(title=title)
        
    def update_cell(self, row, col, data):
        self.open_sheet()
        self.sheet.update(row, col, data)

    def update_cell_by_cell(self,cel, data):
        self.open_sheet()
        self.sheet.update(cel, data)

    #return a cell, can get row and col by cell.row/cell.col
    def find_cell(self, worksheet, data, in_row=None, in_column=None, match_case = True, regex = ""):
        self.open_sheet()
        if not regex == "":
            regx = re.compile(regex)
            return worksheet.find(regx, in_row=in_row, in_column=in_column)
        return worksheet.find(str(data), in_row=in_row, in_column=in_column, case_sensitive=match_case) 
    
    def get_row_values(self, worksheet, row = 1):
        return worksheet.row_values(row)
    
    def get_col_values(self, worksheet, col = 1):
        return worksheet.col_values(col)
        
    def check_if_exist(self, name: str, id: int) -> gspread.Worksheet: 
        self.open_sheet()

        for worksheet in self.sheet.worksheets():
            if str(id) in worksheet.title:
                return worksheet
            
        worksheet = self.create_sheet(f"{name}[id:{id}]")
        self.logger.debug(f"a new worksheet had been created for {name}[id:{id}]")
        return worksheet
    
    @staticmethod
    def get_cell_by_rowcol(row, col):
        return gspread.utils.rowcol_to_a1(row, col)
        
    def create_sheet(self, name, row = 1000, col = 1000):
        if self.spreadsheet_id is None:
            raise Exception("the spreadsheet had not bind yet")
        
        self.open_sheet()
        return self.sheet.add_worksheet(name, row, col)

    def open_sheet(self):
        if self.spreadsheet_id == '':
            raise Exception("google sheet failed to load")

        if self.sheet is None:
            if validators.url(self.spreadsheet_id):
                self.sheet = self.client.open_by_url(self.spreadsheet_id)
            else:
                self.sheet = self.client.open_by_key(self.spreadsheet_id)

    def share_(self, account, permission, role):
        self.open_sheet()
        self.sheet.share(account, permission, role)