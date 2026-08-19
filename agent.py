"""
Driver Pickup Reminder Agent — Main Scheduler (v1)

This is the main entry point that runs locally. It:
1. Reads the schedule (Excel file or Google Sheet) every CHECK_INTERVAL_SECONDS
2. Finds rides with pickup time approximately 30 minutes from now
3. Triggers Twilio calls for each matching ride
4. Polls Twilio API for call completion status
5. Updates the schedule with the reminder status
6. Logs all call attempts to call_logs.json
"""

import argparse
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
from sheet_handler import get_pending_rides, mark_reminder_status, can_write, active_sources
from call_handler import (
    make_reminder_call,
    warm_up_webhook,
    wait_for_call_completion,
    map_call_status_to_reminder_status,
)

# Initialize colorama for colored console output
init(autoreset=True)

# Call logs file
CALL_LOGS_FILE = "call_logs.json"

# Graceful shutdown flag
running = True

def _ride_key(ride):
    """Stable identity for a ride: same driver, same pickup time."""
    return (ride["driver_phone"], ride["pickup_time"])


# Rides already called during this run. A status write-back can still fail
# (e.g. someone opens the Excel file mid-cycle), which would leave the row
# "Pending" and get the driver called again on every later cycle.
called_rows = set()


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
    sources = active_sources()
    print(f"  Schedule Source: {config.SHEET_BACKEND} -> watching {', '.join(sources) or 'nothing'}")
    if "excel" in sources:
        print(f"  Excel File     : {config.EXCEL_FILE_PATH}")
    if "google" in sources:
        print(f"  Google Sheet ID: {config.GOOGLE_SHEET_ID}")
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
    targets = ride["targets"]

    print(f"\n{Fore.YELLOW}[CALL] Initiating reminder for {driver_name} ({driver_phone}){Style.RESET_ALL}")
    print(f"       Pickup Location : {pickup_location}")
    print(f"       Scheduled Time  : {pickup_time_str}")

    # Step 1: Make the call
    call_sid = make_reminder_call(driver_name, driver_phone, pickup_location, pickup_time_str)
    called_rows.add(_ride_key(ride))

    if not call_sid:
        # Call initiation failed
        reminder_status = "Failed - Error"
        try:
            mark_reminder_status(targets, reminder_status)
        except Exception as e:
            print(f"       {Fore.RED}[ERROR] Could not write status: {e}{Style.RESET_ALL}")
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

    # Step 3: Map status and update the schedule
    reminder_status = map_call_status_to_reminder_status(final_status)
    try:
        mark_reminder_status(targets, reminder_status)
    except Exception as e:
        print(f"       {Fore.RED}[ERROR] Could not write status to the schedule: {e}{Style.RESET_ALL}")
        print(f"       {Fore.YELLOW}[INFO] Row stays 'Pending'; this run will not call it again.{Style.RESET_ALL}")

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
        "sources": [name for name, _ in targets],
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

    # Read pending rides from the configured schedule source
    print(f"  [INFO] Scanning schedule for pending rides...")
    pending_rides = get_pending_rides()

    if not pending_rides:
        print(f"  [INFO] No rides due for reminder in current window.")
        return

    # Drop rows already dialled in this run (see called_rows).
    repeats = [r for r in pending_rides if _ride_key(r) in called_rows]
    pending_rides = [r for r in pending_rides if _ride_key(r) not in called_rows]
    if repeats:
        print(f"  {Fore.YELLOW}[SKIP] {len(repeats)} ride(s) already called this run "
              f"(status write-back failed).{Style.RESET_ALL}")
    if not pending_rides:
        return

    print(f"  {Fore.GREEN}[FOUND] {len(pending_rides)} ride(s) due for reminder!{Style.RESET_ALL}")

    # Refuse to dial if the outcome cannot be recorded. Calling anyway would
    # leave the row "Pending" and the driver would be called again and again.
    unwritable = [r for r in pending_rides if not can_write(r["targets"])]
    if unwritable:
        print(f"  {Fore.RED}[SKIP] Schedule is not writable right now - no calls placed.{Style.RESET_ALL}")
        if config.SHEET_BACKEND == "excel":
            print(f"  {Fore.YELLOW}       Close '{config.EXCEL_FILE_PATH}' in Excel and it will retry next cycle.{Style.RESET_ALL}")
        return

    # Wake the webhook before dialling. A sleeping free-tier server would make
    # Twilio time out and play an error message to the driver.
    print(f"  [INFO] Warming up webhook server...")
    if warm_up_webhook():
        print(f"  {Fore.GREEN}[OK] Webhook is awake.{Style.RESET_ALL}")
    else:
        print(f"  {Fore.YELLOW}[WARN] Webhook did not respond — the driver may hear an error message.{Style.RESET_ALL}")

    # Process each ride
    for ride in pending_rides:
        if not running:
            break
        process_ride(ride)


def main():
    """Main entry point for the agent."""
    global running

    parser = argparse.ArgumentParser(
        description="Mr. Cabie — Driver Pickup Reminder Agent"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single check cycle and exit. Use this for cloud schedulers "
             "(Render Cron, GitHub Actions, or OS cron/Task Scheduler) instead "
             "of the always-on polling loop.",
    )
    args = parser.parse_args()

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

    # Single-cycle mode — ideal for cloud cron schedulers (no laptop needed).
    if args.once:
        print(f"{Fore.GREEN}[RUNNING] Single-cycle mode (--once). Scanning once, then exiting.{Style.RESET_ALL}\n")
        try:
            run_check_cycle(1)
        except Exception as e:
            print(f"\n  {Fore.RED}[ERROR] Check cycle failed: {e}{Style.RESET_ALL}")
            sys.exit(1)
        print(f"\n{Fore.CYAN}[INFO] Single cycle complete. Exiting.{Style.RESET_ALL}\n")
        return

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
