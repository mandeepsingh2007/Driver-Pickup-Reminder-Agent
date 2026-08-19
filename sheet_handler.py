"""
Google Sheets handler for the Driver Pickup Reminder Agent.

Reads pending rides from, and writes the reminder status back to, a live
Google Sheet via the Sheets API. Because the status lives in the cloud (not
on disk), the agent can run statelessly on a cron schedule — see README.

One-time setup (see README > Google Sheets Setup):
  1. Create a Google Cloud service account and download its JSON key as
     `service_account.json` in this folder.
  2. Share the Google Sheet with the service account's email
     (…@….iam.gserviceaccount.com) as an Editor.
  3. Set GOOGLE_SHEET_ID in your .env.

Expected columns (header in row 1, data from row 2):
  1 Driver Name | 2 Driver Phone Number | 3 Pickup Location
  4 Scheduled Pickup Time | 5 Reminder Status
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

import config

IST = ZoneInfo(config.TIMEZONE)

# Column positions (1-based), matching the sample sheet.
COL_DRIVER_NAME = 1
COL_DRIVER_PHONE = 2
COL_PICKUP_LOCATION = 3
COL_PICKUP_TIME = 4
COL_REMINDER_STATUS = 5

# Read + write scope for Sheets.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Cache the worksheet handle so we authorize only once per process.
_worksheet = None


def _get_worksheet():
    """Authorize (once) and return the target worksheet."""
    global _worksheet
    if _worksheet is not None:
        return _worksheet

    creds = Credentials.from_service_account_file(
        config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(config.GOOGLE_SHEET_ID)

    if config.GOOGLE_WORKSHEET_NAME:
        _worksheet = spreadsheet.worksheet(config.GOOGLE_WORKSHEET_NAME)
    else:
        _worksheet = spreadsheet.sheet1  # first worksheet

    return _worksheet


def _parse_pickup_time(value, row_label=""):
    """
    Parse a pickup-time cell into an IST-aware datetime.

    Google Sheets hands us strings whose format depends on how the cell is
    displayed, so we try the strict formats first and fall back to a tolerant
    parser. Returns None if the value can't be understood.
    """
    value = str(value).strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=IST)
        except ValueError:
            continue

    # Tolerant fallback for other display formats (e.g. "18/08/2026 21:39").
    try:
        from dateutil import parser as date_parser
    except ImportError:
        print(f"  [WARN] {row_label}: Cannot parse pickup time '{value}' "
              f"(install python-dateutil for flexible date parsing), skipping")
        return None

    try:
        dt = date_parser.parse(value, dayfirst=True)  # dd/mm/yyyy for India
        return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt
    except (ValueError, OverflowError):
        print(f"  [WARN] {row_label}: Cannot parse pickup time '{value}', skipping")
        return None


def _is_due(pickup_dt, now):
    """
    True if pickup_dt falls inside the reminder window:
    (REMINDER_MINUTES_BEFORE - 5) .. (REMINDER_MINUTES_BEFORE + 5) from now.
    """
    minutes = config.REMINDER_MINUTES_BEFORE
    window_start = now + timedelta(minutes=minutes - 5)
    window_end = now + timedelta(minutes=minutes + 5)
    return window_start <= pickup_dt <= window_end


def get_pending_rides():
    """
    Return rides that are "Pending" AND whose pickup time is inside the
    reminder window. Each item carries row_index for the status write-back.
    """
    try:
        ws = _get_worksheet()
        rows = ws.get_all_values()  # list of rows; row 1 is the header
    except Exception as e:
        print(f"  [ERROR] Could not read Google Sheet: {e}")
        return []

    now = datetime.now(IST)
    pending_rides = []

    # Data starts at sheet row 2 (row 1 is the header).
    for row_idx, row in enumerate(rows[1:], start=2):
        # Pad short rows so column indexing never raises.
        cells = row + [""] * (COL_REMINDER_STATUS - len(row))
        driver_name = cells[COL_DRIVER_NAME - 1]
        driver_phone = cells[COL_DRIVER_PHONE - 1]
        pickup_location = cells[COL_PICKUP_LOCATION - 1]
        pickup_time = cells[COL_PICKUP_TIME - 1]
        reminder_status = cells[COL_REMINDER_STATUS - 1]

        # Skip if not pending — this is what stops a driver being called twice.
        if not reminder_status or reminder_status.strip().lower() != "pending":
            continue

        # Skip if any required field is missing
        if not all([driver_name, driver_phone, pickup_location, pickup_time]):
            print(f"  [WARN] Row {row_idx}: Missing required fields, skipping")
            continue

        pickup_dt = _parse_pickup_time(pickup_time, f"Row {row_idx}")
        if pickup_dt is None:
            continue

        if _is_due(pickup_dt, now):
            pending_rides.append({
                "row_index": row_idx,
                "driver_name": driver_name.strip(),
                "driver_phone": driver_phone.strip(),
                "pickup_location": pickup_location.strip(),
                "pickup_time": pickup_dt,
                "pickup_time_str": pickup_dt.strftime("%I:%M %p"),  # "09:39 PM"
            })

    return pending_rides


def mark_reminder_status(row_index, status):
    """
    Update the Reminder Status cell for a given sheet row (1-based).

    Args:
        row_index (int): The sheet row number (min 2 — row 1 is the header)
        status (str): "Sent", "Failed - No Answer", "Failed - Busy",
                      or "Failed - Error"
    """
    try:
        ws = _get_worksheet()
        ws.update_cell(row_index, COL_REMINDER_STATUS, status)
    except Exception as e:
        print(f"  [ERROR] Could not update Google Sheet row {row_index}: {e}")
