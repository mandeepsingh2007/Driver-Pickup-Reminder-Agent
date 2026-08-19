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

# ─── Google Sheets ───
# The schedule lives in a live Google Sheet. Keeping the status in the cloud
# (rather than a local file) is what lets the agent run on a cron schedule.
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "")  # blank = first worksheet

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

    # Validate Google Sheets access
    sheet_missing = []
    if not GOOGLE_SHEET_ID:
        sheet_missing.append("GOOGLE_SHEET_ID")
    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_JSON):
        sheet_missing.append(f"service account file '{GOOGLE_SERVICE_ACCOUNT_JSON}'")

    if sheet_missing:
        raise ValueError(
            f"Google Sheets is not configured — missing: {', '.join(sheet_missing)}.\n"
            "Create a Google Cloud service account, download its JSON key, "
            "share the sheet with the service account email, and set "
            "GOOGLE_SHEET_ID. See README > Google Sheets Setup."
        )

    return True
