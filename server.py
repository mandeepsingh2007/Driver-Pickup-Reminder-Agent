"""
Flask Webhook Server for the Driver Pickup Reminder Agent.
Deployed on Render — serves TwiML for Twilio voice calls.

This server is completely stateless. It receives query parameters
from the call URL and generates a personalized voice message.
"""

import os
from flask import Flask, request, Response

app = Flask(__name__)


@app.route("/voice", methods=["GET", "POST"])
def voice():
    """
    Serve TwiML with a personalized driver reminder message.
    
    Query Parameters:
        driver_name (str): Driver's name
        pickup_location (str): Pickup location
        pickup_time (str): Formatted pickup time
    
    Returns:
        TwiML XML response with <Say> verb
    """
    driver_name = request.args.get("driver_name", "Driver")
    pickup_location = request.args.get("pickup_location", "your pickup location")
    pickup_time = request.args.get("pickup_time", "the scheduled time")
    
    message = (
        f"Hello {driver_name}, this is an automated reminder from Mr. Cabie. "
        f"You have a pickup scheduled at {pickup_location} at {pickup_time}. "
        f"Please call or message your customer to confirm the pickup "
        f"and make sure you reach the location on time. "
        f"Thank you and drive safe."
    )
    
    # Build TwiML response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="en-IN">
        {message}
    </Say>
    <Pause length="1"/>
    <Say voice="Polly.Aditi" language="en-IN">
        Once again, your pickup is at {pickup_location} at {pickup_time}. 
        Please be on time. Thank you.
    </Say>
</Response>"""
    
    return Response(twiml, mimetype="application/xml")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Render."""
    return {"status": "ok", "service": "Mr. Cabie Driver Reminder Agent"}


@app.route("/", methods=["GET"])
def index():
    """Root endpoint — basic info."""
    return {
        "service": "Mr. Cabie - Driver Pickup Reminder Agent",
        "version": "1.0",
        "endpoints": {
            "/voice": "TwiML voice message endpoint (used by Twilio)",
            "/health": "Health check",
        }
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
