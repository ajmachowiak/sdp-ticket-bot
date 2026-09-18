import os
import logging
from dotenv import load_dotenv
from datetime import datetime

# load env variables from .env file
load_dotenv()

# --- sdp api config ---
# base API URL
SDP_BASE_URL = os.getenv("SDP_BASE_URL")
SDP_ACCOUNTS_URL = os.getenv("SDP_ACCOUNTS_URL")

# OAuth2 server-based app credentials
SDP_CLIENT_ID = os.getenv("SDP_CLIENT_ID")
SDP_CLIENT_SECRET = os.getenv("SDP_CLIENT_SECRET")
SDP_REFRESH_TOKEN = os.getenv("SDP_REFRESH_TOKEN")

# --- file system and path settings ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
ENGINEERS_FILE = os.path.join(BASE_DIR, "engineers.md")
ROTA_FILE = os.path.join(BASE_DIR, "rota.md")

# --- log folder settings ---
os.makedirs(LOGS_DIR, exist_ok=True)

# generates log file name using specified format
def get_log_filename():
    """Generates a log filename using HHMMSS_DDMMYYYY.log format"""
    now = datetime.now()
    return os.path.join(LOGS_DIR, now.strftime("%H%M%S_%d%m%Y.log"))

# --- customer default ticket settings ---
# SDP payload defaults used if Md template omits specific fields
SDP_REQUESTER_EMAIL = "itsupport@company.com"
SDP_CATEGORY = "Compliance Checks"
SDP_REQUEST_TYPE = "Support"
SDP_MODE = "Web form"
SDP_IMPACT = "Affects User"
SDP_URGENCY = "Low"
SDP_PRIORITY = "Low"