"""
Configuration loader for the Driver Pickup Reminder Agent.
Loads environment variables from .env file and provides them as module-level constants.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Twilio Credentials ───
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# ─── Webhook URL (Render deployment) ───
RENDER_WEBHOOK_URL = os.getenv("RENDER_WEBHOOK_URL", "http://localhost:5000")

# ─── Excel File Path ───
EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "Sample_Driver_Pickup_Schedule V2.xlsx")

# ─── Agent Settings ───
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
REMINDER_MINUTES_BEFORE = int(os.getenv("REMINDER_MINUTES_BEFORE", "30"))

# ─── Timezone ───
TIMEZONE = "Asia/Kolkata"  # IST


def validate_config():
    """Validate that all required configuration values are set."""
    missing = []
    if not TWILIO_ACCOUNT_SID:
        missing.append("TWILIO_ACCOUNT_SID")
    if not TWILIO_AUTH_TOKEN:
        missing.append("TWILIO_AUTH_TOKEN")
    if not TWILIO_PHONE_NUMBER:
        missing.append("TWILIO_PHONE_NUMBER")
    if not RENDER_WEBHOOK_URL:
        missing.append("RENDER_WEBHOOK_URL")

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please set them in your .env file. See .env.example for reference."
        )

    return True
