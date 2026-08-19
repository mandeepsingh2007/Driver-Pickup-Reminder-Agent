"""
Flask Webhook Server for the Driver Pickup Reminder Agent.
Deployed on Render — serves TwiML for Twilio voice calls.

This server is completely stateless. It receives query parameters
from the call URL and generates a personalized voice message.
"""

import os
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse

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
        TwiML XML response with <Say> verbs.

    Note: the message is built with Twilio's VoiceResponse helper rather than
    an f-string template so that special characters in the driver name or
    location (e.g. & or <) are XML-escaped automatically and can never break
    the TwiML.
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

    response = VoiceResponse()
    response.say(message, voice="Polly.Aditi", language="en-IN")
    response.pause(length=1)
    response.say(
        f"Once again, your pickup is at {pickup_location} at {pickup_time}. "
        f"Please be on time. Thank you.",
        voice="Polly.Aditi",
        language="en-IN",
    )

    return Response(str(response), mimetype="application/xml")


@app.route("/call-status", methods=["POST"])
def call_status():
    """
    Status callback endpoint for Twilio call events.
    Logs call completion, no-answer, busy, or failure events.
    """
    call_sid = request.values.get("CallSid", "")
    call_status_val = request.values.get("CallStatus", "")
    to_number = request.values.get("To", "")

    print(f"[TWILIO CALLBACK] CallSid: {call_sid} | To: {to_number} | Status: {call_status_val}")
    return {"status": "received", "call_sid": call_sid, "call_status": call_status_val}


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
    # Debug is OFF by default. Enable locally with FLASK_DEBUG=true if needed;
    # it must never be on in production (Render runs this via gunicorn anyway).
    debug = os.environ.get("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
