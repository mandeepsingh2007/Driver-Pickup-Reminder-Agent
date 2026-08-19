"""
Schedule handler for the Driver Pickup Reminder Agent.

Supports two sources for the driver schedule, chosen with SHEET_BACKEND:

    SHEET_BACKEND=excel   -> local .xlsx file  (default; no setup, best for testing)
    SHEET_BACKEND=google  -> live Google Sheet (matches the task spec; required
                             for cloud/cron runs, since a scheduled run has no
                             local disk to persist the status to)

Both backends expose the same two functions and return the same ride dict, so
the rest of the app never knows which one is active.

Expected columns (header in row 1, data from row 2):
  1 Driver Name | 2 Driver Phone Number | 3 Pickup Location
  4 Scheduled Pickup Time | 5 Reminder Status
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config

IST = ZoneInfo(config.TIMEZONE)

# Column positions (1-based), shared by both backends.
COL_DRIVER_NAME = 1
COL_DRIVER_PHONE = 2
COL_PICKUP_LOCATION = 3
COL_PICKUP_TIME = 4
COL_REMINDER_STATUS = 5


# --------------------------- shared helpers ---------------------------

def _parse_pickup_time(value, row_label=""):
    """
    Parse a pickup-time cell into an IST-aware datetime.

    Excel hands us real datetime objects; Google Sheets hands us strings whose
    format depends on how the cell is displayed. Returns None if the value
    cannot be understood.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=IST) if value.tzinfo is None else value

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
    return (now + timedelta(minutes=minutes - 5)
            <= pickup_dt <=
            now + timedelta(minutes=minutes + 5))


def _build_ride(row_index, name, phone, location, pickup_dt):
    """Build the normalized ride dict consumed by agent.py."""
    return {
        "row_index": row_index,
        "driver_name": str(name).strip(),
        "driver_phone": str(phone).strip(),
        "pickup_location": str(location).strip(),
        "pickup_time": pickup_dt,
        "pickup_time_str": pickup_dt.strftime("%I:%M %p"),  # "09:39 PM"
    }


# --------------------------- Excel backend ---------------------------

def _excel_get_pending_rides():
    from openpyxl import load_workbook

    file_path = config.EXCEL_FILE_PATH
    if not os.path.exists(file_path):
        print(f"  [ERROR] Excel file not found: {file_path}")
        return []

    wb = load_workbook(file_path)
    ws = wb.active
    now = datetime.now(IST)
    rides = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        values = [c.value for c in row]
        values += [None] * (COL_REMINDER_STATUS - len(values))
        name, phone, location, pickup_time, status = values[:COL_REMINDER_STATUS]

        if status is None or str(status).strip().lower() != "pending":
            continue
        if not all([name, phone, location, pickup_time]):
            print(f"  [WARN] Row {row_idx}: Missing required fields, skipping")
            continue

        pickup_dt = _parse_pickup_time(pickup_time, f"Row {row_idx}")
        if pickup_dt and _is_due(pickup_dt, now):
            rides.append(_build_ride(row_idx, name, phone, location, pickup_dt))

    wb.close()
    return rides


def _excel_mark_reminder_status(row_index, status):
    from openpyxl import load_workbook

    wb = load_workbook(config.EXCEL_FILE_PATH)
    ws = wb.active
    ws.cell(row=row_index, column=COL_REMINDER_STATUS, value=status)
    wb.save(config.EXCEL_FILE_PATH)
    wb.close()


# ------------------------ Google Sheets backend ------------------------

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Cache the worksheet handle so we authorize only once per process.
_worksheet = None


def _get_worksheet():
    """Authorize (once) and return the target Google worksheet."""
    global _worksheet
    if _worksheet is not None:
        return _worksheet

    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES
    )
    spreadsheet = gspread.authorize(creds).open_by_key(config.GOOGLE_SHEET_ID)
    _worksheet = (spreadsheet.worksheet(config.GOOGLE_WORKSHEET_NAME)
                  if config.GOOGLE_WORKSHEET_NAME else spreadsheet.sheet1)
    return _worksheet


def _google_get_pending_rides():
    try:
        rows = _get_worksheet().get_all_values()  # row 1 is the header
    except Exception as e:
        print(f"  [ERROR] Could not read Google Sheet: {e}")
        return []

    now = datetime.now(IST)
    rides = []

    for row_idx, row in enumerate(rows[1:], start=2):
        # Pad short rows so column indexing never raises.
        cells = row + [""] * (COL_REMINDER_STATUS - len(row))
        name, phone, location, pickup_time, status = cells[:COL_REMINDER_STATUS]

        if not status or status.strip().lower() != "pending":
            continue
        if not all([name, phone, location, pickup_time]):
            print(f"  [WARN] Row {row_idx}: Missing required fields, skipping")
            continue

        pickup_dt = _parse_pickup_time(pickup_time, f"Row {row_idx}")
        if pickup_dt and _is_due(pickup_dt, now):
            rides.append(_build_ride(row_idx, name, phone, location, pickup_dt))

    return rides


def _google_mark_reminder_status(row_index, status):
    try:
        _get_worksheet().update_cell(row_index, COL_REMINDER_STATUS, status)
    except Exception as e:
        print(f"  [ERROR] Could not update Google Sheet row {row_index}: {e}")


# ----------------------------- public API -----------------------------

def get_pending_rides():
    """
    Return rides that are "Pending" AND whose pickup time is inside the
    reminder window. Each item carries row_index for the status write-back.

    Only rows still marked "Pending" are returned, which is what stops a
    driver from being called twice for the same ride.
    """
    if config.SHEET_BACKEND == "google":
        return _google_get_pending_rides()
    return _excel_get_pending_rides()


def mark_reminder_status(row_index, status):
    """
    Update the Reminder Status cell for a given row (1-based; row 1 is the
    header).

    Args:
        row_index (int): The row number to update
        status (str): "Sent", "Failed - No Answer", "Failed - Busy",
                      or "Failed - Error"
    """
    if config.SHEET_BACKEND == "google":
        return _google_mark_reminder_status(row_index, status)
    return _excel_mark_reminder_status(row_index, status)
