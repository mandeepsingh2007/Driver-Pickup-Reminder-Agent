"""
Driver Pickup Reminder Agent — Main Scheduler (v1)

This is the main entry point that runs locally. It:
1. Reads the Excel sheet every CHECK_INTERVAL_SECONDS
2. Finds rides with pickup time approximately 30 minutes from now
3. Triggers Twilio calls for each matching ride
4. Polls Twilio API for call completion status
5. Updates the Excel sheet with the reminder status
6. Logs all call attempts to call_logs.json
"""

import json
import os
import signal
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from colorama import init, Fore, Style

# Ensure stdout uses UTF-8 encoding on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import config
from sheet_handler import get_pending_rides, mark_reminder_status
from call_handler import (
    make_reminder_call,
    wait_for_call_completion,
    map_call_status_to_reminder_status,
)

# Initialize colorama for colored console output
init(autoreset=True)

# Call logs file
CALL_LOGS_FILE = "call_logs.json"

# Graceful shutdown flag
running = True


def signal_handler(sig, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global running
    print(f"\n{Fore.YELLOW}[WARN] Shutdown signal received. Stopping agent...{Style.RESET_ALL}")
    running = False


def load_call_logs():
    """Load existing call logs from JSON file."""
    if os.path.exists(CALL_LOGS_FILE):
        try:
            with open(CALL_LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_call_log(log_entry):
    """Append a call log entry and save to JSON file."""
    logs = load_call_logs()
    logs.append(log_entry)
    with open(CALL_LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False, default=str)


def print_banner():
    """Print the agent startup banner."""
    banner = f"""
{Fore.CYAN}==============================================================
  Mr. Cabie — Driver Pickup Reminder Agent (v1)
=============================================================={Style.RESET_ALL}
"""
    print(banner)


def print_config():
    """Print current configuration."""
    print(f"{Fore.CYAN}[CONFIG] Configuration Details:{Style.RESET_ALL}")
    print(f"  Excel File     : {config.EXCEL_FILE_PATH}")
    print(f"  Webhook URL    : {config.RENDER_WEBHOOK_URL}")
    print(f"  Check Interval : {config.CHECK_INTERVAL_SECONDS} seconds")
    print(f"  Reminder Before: {config.REMINDER_MINUTES_BEFORE} minutes")
    print(f"  Twilio Number  : {config.TWILIO_PHONE_NUMBER}")
    print(f"{Fore.CYAN}--------------------------------------------------------------{Style.RESET_ALL}\n")


def process_ride(ride):
    """
    Process a single ride: make the call, wait for completion, update status.
    
    Args:
        ride (dict): Ride details from sheet_handler
    
    Returns:
        dict: Call log entry
    """
    ist = ZoneInfo(config.TIMEZONE)
    now = datetime.now(ist)

    driver_name = ride["driver_name"]
    driver_phone = ride["driver_phone"]
    pickup_location = ride["pickup_location"]
    pickup_time_str = ride["pickup_time_str"]
    row_index = ride["row_index"]

    print(f"\n{Fore.YELLOW}[CALL] Initiating reminder for {driver_name} ({driver_phone}){Style.RESET_ALL}")
    print(f"       Pickup Location : {pickup_location}")
    print(f"       Scheduled Time  : {pickup_time_str}")

    # Step 1: Make the call
    call_sid = make_reminder_call(driver_name, driver_phone, pickup_location, pickup_time_str)

    if not call_sid:
        # Call initiation failed
        reminder_status = "Failed - Error"
        mark_reminder_status(row_index, reminder_status)
        log_entry = {
            "timestamp": now.isoformat(),
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "pickup_location": pickup_location,
            "pickup_time": pickup_time_str,
            "call_sid": None,
            "call_status": "failed",
            "reminder_status": reminder_status,
        }
        print(f"       {Fore.RED}[ERROR] Call failed to initiate{Style.RESET_ALL}")
        save_call_log(log_entry)
        return log_entry

    print(f"       {Fore.CYAN}[INFO] Call SID: {call_sid}{Style.RESET_ALL}")

    # Step 2: Wait for call to complete
    print(f"       {Fore.CYAN}[INFO] Waiting for call status completion...{Style.RESET_ALL}")
    final_status = wait_for_call_completion(call_sid)

    # Step 3: Map status and update Excel
    reminder_status = map_call_status_to_reminder_status(final_status)
    mark_reminder_status(row_index, reminder_status)

    # Step 4: Log the result
    log_entry = {
        "timestamp": now.isoformat(),
        "driver_name": driver_name,
        "driver_phone": driver_phone,
        "pickup_location": pickup_location,
        "pickup_time": pickup_time_str,
        "call_sid": call_sid,
        "call_status": final_status,
        "reminder_status": reminder_status,
    }
    save_call_log(log_entry)

    # Print result
    if final_status == "completed":
        print(f"       {Fore.GREEN}[SUCCESS] Call completed — Reminder status set to 'Sent'{Style.RESET_ALL}")
    elif final_status == "no-answer":
        print(f"       {Fore.RED}[NO ANSWER] Driver did not answer — Logged{Style.RESET_ALL}")
    elif final_status == "busy":
        print(f"       {Fore.RED}[BUSY] Line busy — Logged{Style.RESET_ALL}")
    else:
        print(f"       {Fore.RED}[FAILED] Call status: {final_status} — Logged{Style.RESET_ALL}")

    return log_entry


def run_check_cycle(cycle_count):
    """
    Run a single check cycle: read sheet, find due rides, process them.
    
    Args:
        cycle_count (int): Current cycle number for display
    """
    ist = ZoneInfo(config.TIMEZONE)
    now = datetime.now(ist)

    print(f"\n{Fore.CYAN}--------------------------------------------------------------{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Cycle #{cycle_count} | {now.strftime('%Y-%m-%d %H:%M:%S IST')}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}--------------------------------------------------------------{Style.RESET_ALL}")

    # Read pending rides from Excel
    print(f"  [INFO] Scanning Excel for pending rides...")
    pending_rides = get_pending_rides()

    if not pending_rides:
        print(f"  [INFO] No rides due for reminder in current window.")
        return

    print(f"  {Fore.GREEN}[FOUND] {len(pending_rides)} ride(s) due for reminder!{Style.RESET_ALL}")

    # Process each ride
    for ride in pending_rides:
        if not running:
            break
        process_ride(ride)


def main():
    """Main entry point for the agent."""
    global running

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Print banner
    print_banner()

    # Validate configuration
    try:
        config.validate_config()
        print(f"{Fore.GREEN}[SUCCESS] Configuration validated successfully.{Style.RESET_ALL}\n")
    except ValueError as e:
        print(f"{Fore.RED}[ERROR] Configuration Error:\n  {e}{Style.RESET_ALL}")
        sys.exit(1)

    # Print config summary
    print_config()

    print(f"{Fore.GREEN}[RUNNING] Agent active. Polling schedule every {config.CHECK_INTERVAL_SECONDS} seconds.{Style.RESET_ALL}")
    print("Press Ctrl+C to stop.\n")

    cycle_count = 0

    # Main loop
    while running:
        cycle_count += 1
        
        try:
            run_check_cycle(cycle_count)
        except Exception as e:
            print(f"\n  {Fore.RED}[ERROR] Cycle #{cycle_count} execution failed: {e}{Style.RESET_ALL}")

        # Wait for next cycle
        for _ in range(config.CHECK_INTERVAL_SECONDS):
            if not running:
                break
            time.sleep(1)

    print(f"\n{Fore.CYAN}[INFO] Agent shutdown complete.{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
