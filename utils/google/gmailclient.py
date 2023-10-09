from __future__ import print_function
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from google.oauth2 import service_account

import base64
from email.message import EmailMessage
import os
import blowfish

import smtplib
from email.mime.text import MIMEText

from utils.constant import Constant as constant
import utils.logger as logger
from utils.cutils import kms_get_key

class GmailClient:
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']

    class ServiceAccountSender:
        CRED_DIR_PATH = f"{os.getcwd()}\\gworkshop_cred\\"
        SERVICE_ACCOUNT = f"{CRED_DIR_PATH}service_account.json"
        ACC_SENDER = "airi-bot@airibot-391611.iam.gserviceaccount.com"

        def send_email(self, *, receiver = "", subject = "", content = ""):

            try:
                service = self.service_account_login()
                message = EmailMessage()
                message.set_content(content)
                message['To'] = receiver
                message['From'] = self.ACC_SENDER
                message['Subject'] = subject

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

                create_message = {
                    'raw': encoded_message
                }

                email = service.users().messages().send(userId="me", 
                                                        body=create_message).execute()
            except Exception as error:
                print(f'An error occurred: {error}')

        def service_account_login(self):
            SERVICE_ACCOUNT_FILE = self.SERVICE_ACCOUNT

            credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=GmailClient.SCOPES)
            delegated_credentials = credentials.with_subject(self.ACC_SENDER)
            service = build('gmail', 'v1', credentials=delegated_credentials)
            return service
        
    class ApplicationCredSender:

        logger = logger.Logger("ApplicationCredSender")

        @staticmethod
        def send_email(subject, body, recipients, sender = constant.SMTP_SENDER, password = constant.SMTP_APPLICATION_SECRET):
            GmailClient.ApplicationCredSender.logger.info("===== send_email =====")
            msg = MIMEText(body, 'html')
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            with smtplib.SMTP_SSL(constant.SMTP_SERVER, constant.SMTP_PORT) as smtp_server:
                if password == constant.SMTP_APPLICATION_SECRET:
                    cipher = blowfish.Cipher(bytes(kms_get_key(), "utf-8"))
                    password = b"".join(cipher.decrypt_ecb(base64.decodebytes(bytes(password, "utf-8")))).decode('utf8', errors='ignore')
                    smtp_server.login(sender, password)
                else:
                    smtp_server.login(sender, password)
                smtp_server.sendmail(sender, recipients, msg.as_string())
                GmailClient.ApplicationCredSender.logger.info(f"email sent successfully, recipients :: {', '.join(recipients)}")


if __name__ == '__main__':
    pass