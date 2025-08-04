# Updated cpanel_transfer.py

import os
import logging
from dotenv import load_dotenv
from pathlib import Path
from service import transfer_directory

load_dotenv()

# Logging setup
log_file = 'general.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# SSH configuration
SOURCE_HOST = os.getenv("SOURCE_HOST")
SOURCE_PORT = int(os.getenv("SOURCE_PORT", 22))
SOURCE_USER = os.getenv("SOURCE_USER")
SOURCE_PASS = os.getenv("SOURCE_PASSWORD")

TARGET_HOST = os.getenv("TARGET_HOST")
TARGET_PORT = int(os.getenv("TARGET_PORT", 22))
TARGET_USER = os.getenv("TARGET_USER")
TARGET_PASS = os.getenv("TARGET_PASSWORD")

TRANSFER_WEBSITE = os.getenv("TRANSFER_WEBSITE", "false").lower() == "true"
TRANSFER_MAIL = os.getenv("TRANSFER_MAIL", "false").lower() == "true"


source = {
    'host': SOURCE_HOST,
    'port': SOURCE_PORT,
    'user': SOURCE_USER,
    'password': SOURCE_PASS
}
target = {
    'host': TARGET_HOST,
    'port': TARGET_PORT,
    'user': TARGET_USER,
    'password': TARGET_PASS
}

# Example: choose protocol 'scp', 'sftp', or 'ftp'
transfer_directory(source, target, path="public_html", folder_name=".well-known", protocol='sftp')
