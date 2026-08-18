"""
Excel Sheet Handler for the Driver Pickup Reminder Agent.
Reads pending rides and updates reminder status in the Excel file.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from openpyxl import load_workbook
import config


# Column indices (1-based, matching Excel)
COL_DRIVER_NAME = 1
COL_DRIVER_PHONE = 2
COL_PICKUP_LOCATION = 3
COL_PICKUP_TIME = 4
COL_REMINDER_STATUS = 5

IST = ZoneInfo(config.TIMEZONE)


def get_pending_rides():
    """
    Read the Excel sheet and return rides that:
    - Have Reminder Status == "Pending"
    - Have Scheduled Pickup Time approximately 30 minutes from now (±5 min window)
    
    Returns:
        list of dict: Each dict contains ride details + row_index for updating
    """
    file_path = config.EXCEL_FILE_PATH

    if not os.path.exists(file_path):
        print(f"  [ERROR] Excel file not found: {file_path}")
        return []

    wb = load_workbook(file_path)
    ws = wb.active
    
    now = datetime.now(IST)
    reminder_minutes = config.REMINDER_MINUTES_BEFORE
    
    # Window: pickup_time should be between (now + 25 min) and (now + 35 min)
    window_start = now + timedelta(minutes=reminder_minutes - 5)
    window_end = now + timedelta(minutes=reminder_minutes + 5)
    
    pending_rides = []
    
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
        driver_name = row[COL_DRIVER_NAME - 1].value
        driver_phone = row[COL_DRIVER_PHONE - 1].value
        pickup_location = row[COL_PICKUP_LOCATION - 1].value
        pickup_time = row[COL_PICKUP_TIME - 1].value
        reminder_status = row[COL_REMINDER_STATUS - 1].value
        
        # Skip if not pending
        if reminder_status is None or str(reminder_status).strip().lower() != "pending":
            continue
        
        # Skip if any required field is missing
        if not all([driver_name, driver_phone, pickup_location, pickup_time]):
            print(f"  [WARN] Row {row_idx}: Missing required fields, skipping")
            continue
        
        # Parse pickup time — handle both datetime objects and strings
        if isinstance(pickup_time, datetime):
            pickup_dt = pickup_time.replace(tzinfo=IST) if pickup_time.tzinfo is None else pickup_time
        elif isinstance(pickup_time, str):
            try:
                pickup_dt = datetime.strptime(pickup_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
            except ValueError:
                try:
                    pickup_dt = datetime.strptime(pickup_time, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
                except ValueError:
                    print(f"  [WARN] Row {row_idx}: Cannot parse pickup time '{pickup_time}', skipping")
                    continue
        else:
            print(f"  [WARN] Row {row_idx}: Invalid pickup time type, skipping")
            continue
        
        # Check if pickup time falls within the reminder window
        if window_start <= pickup_dt <= window_end:
            pending_rides.append({
                "row_index": row_idx,
                "driver_name": str(driver_name).strip(),
                "driver_phone": str(driver_phone).strip(),
                "pickup_location": str(pickup_location).strip(),
                "pickup_time": pickup_dt,
                "pickup_time_str": pickup_dt.strftime("%I:%M %p"),  # e.g., "09:39 PM"
            })
    
    wb.close()
    return pending_rides


def mark_reminder_status(row_index, status):
    """
    Update the Reminder Status column for a given row.
    
    Args:
        row_index (int): The Excel row number (1-based, min 2)
        status (str): One of "Sent", "Failed - No Answer", "Failed - Busy", "Failed - Error"
    """
    file_path = config.EXCEL_FILE_PATH
    
    wb = load_workbook(file_path)
    ws = wb.active
    
    ws.cell(row=row_index, column=COL_REMINDER_STATUS, value=status)
    
    wb.save(file_path)
    wb.close()
