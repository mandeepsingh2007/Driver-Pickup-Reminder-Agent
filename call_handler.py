"""
Twilio Call Handler for the Driver Pickup Reminder Agent.
Triggers outbound calls and checks call status via Twilio API.
"""

import time
from urllib.parse import urlencode
from twilio.rest import Client
import config


def get_twilio_client():
    """Create and return a Twilio client instance."""
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def make_reminder_call(driver_name, driver_phone, pickup_location, pickup_time_str):
    """
    Make an outbound reminder call to the driver via Twilio.
    
    The call will hit the /voice endpoint on our Render webhook server,
    which serves a personalized TwiML voice message.
    
    Args:
        driver_name (str): Driver's name for personalization
        driver_phone (str): Driver's phone number (e.g., +919876543210)
        pickup_location (str): Pickup location for the message
        pickup_time_str (str): Formatted pickup time (e.g., "09:39 PM")
    
    Returns:
        str: The Twilio Call SID for status tracking, or None if call failed
    """
    client = get_twilio_client()
    
    # Build the webhook URL with query params for personalized message
    query_params = urlencode({
        "driver_name": driver_name,
        "pickup_location": pickup_location,
        "pickup_time": pickup_time_str,
    })
    voice_url = f"{config.RENDER_WEBHOOK_URL}/voice?{query_params}"
    
    try:
        call = client.calls.create(
            to=driver_phone,
            from_=config.TWILIO_PHONE_NUMBER,
            url=voice_url,
            method="POST",
            timeout=30,  # Ring for 30 seconds before giving up
        )
        return call.sid
    except Exception as e:
        print(f"  [ERROR] Failed to initiate call to {driver_phone}: {e}")
        return None


def check_call_status(call_sid):
    """
    Check the current status of a call via Twilio API.
    
    Args:
        call_sid (str): The Twilio Call SID
    
    Returns:
        str: Call status — "completed", "no-answer", "busy", "failed", "canceled",
             "in-progress", "ringing", "queued"
    """
    client = get_twilio_client()
    
    try:
        call = client.calls(call_sid).fetch()
        return call.status
    except Exception as e:
        print(f"  [ERROR] Failed to fetch call status for {call_sid}: {e}")
        return "error"


def wait_for_call_completion(call_sid, max_wait=120, poll_interval=5):
    """
    Wait for a call to complete by polling Twilio API.
    
    Args:
        call_sid (str): The Twilio Call SID
        max_wait (int): Maximum seconds to wait (default 120)
        poll_interval (int): Seconds between status checks (default 5)
    
    Returns:
        str: Final call status
    """
    elapsed = 0
    
    while elapsed < max_wait:
        status = check_call_status(call_sid)
        
        # Terminal statuses — call is done
        if status in ("completed", "no-answer", "busy", "failed", "canceled", "error"):
            return status
        
        time.sleep(poll_interval)
        elapsed += poll_interval
    
    # Timed out waiting
    return check_call_status(call_sid)


def map_call_status_to_reminder_status(call_status):
    """
    Map Twilio call status to our Excel reminder status string.
    
    Args:
        call_status (str): Twilio call status
    
    Returns:
        str: Reminder status for Excel
    """
    status_map = {
        "completed": "Sent",
        "no-answer": "Failed - No Answer",
        "busy": "Failed - Busy",
        "failed": "Failed - Error",
        "canceled": "Failed - Error",
        "error": "Failed - Error",
    }
    return status_map.get(call_status, "Failed - Error")
