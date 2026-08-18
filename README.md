# Mr. Cabie — Driver Pickup Reminder Agent (v1)

An automated agent that reminds drivers about upcoming pickups by calling them 30 minutes before the scheduled pickup time via Twilio. It reads the driver schedule from an Excel sheet, makes the call, plays a voice reminder, updates the schedule, and logs the result.

---

## How It Works

1. **Agent reads the Excel sheet** every 60 seconds looking for rides with a pickup time approximately 30 minutes from now (within a 25–35 minute window).
2. **For each matching ride**, it triggers an outbound call via Twilio to the driver's phone number.
3. **Twilio calls the driver** and plays a personalized voice message:
   > "Hello [Driver Name], this is an automated reminder from Mr. Cabie. You have a pickup scheduled at [Location] at [Time]. Please call or message your customer to confirm the pickup and make sure you reach the location on time. Thank you and drive safe."
4. **Agent tracks the call status** — if completed, the Excel row status is updated to "Sent"; if unanswered, it is marked as "Failed - No Answer".
5. **All call attempts are logged** in `call_logs.json`.

---

## Architecture

```
+--------------------------------------------------+
|                  LOCAL MACHINE                   |
|                                                  |
|  +----------+     +---------------+              |
|  |  Excel   |---->|   agent.py    |              |
|  |  Sheet   |<----|  (Scheduler)  |              |
|  +----------+     +-------+-------+              |
|                           |                      |
|                    Trigger Call                  |
|                           |                      |
+---------------------------+----------------------+
                            |
                            v
                   +-----------------+
                   |   Twilio API    |
                   |  (Outbound Call)|
                   +--------+--------+
                            |
              +-------------+-------------+
              |                           |
              v                           v
     +-----------------+        +------------------+
     | Driver's Phone  |<-------|   Render Server  |
     +-----------------+ TwiML  |    (server.py)   |
                         XML    |  /voice endpoint |
                                +------------------+
```

**Split Deployment:**
- `server.py`: Deployed on Render (Free tier) at `https://driver-pickup-reminder-agent.onrender.com` — serves TwiML voice XML.
- `agent.py`: Runs locally — scans Excel, triggers Twilio calls, polls call status, updates sheet.

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- A Twilio account (Account SID, Auth Token, and Twilio Phone Number)

### Step 1: Virtual Environment Setup

```bash
# Navigate to project directory
cd "mr cabie assignment"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Create or update the `.env` file in the root directory:

```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here
RENDER_WEBHOOK_URL=https://driver-pickup-reminder-agent.onrender.com
EXCEL_FILE_PATH=Sample_Driver_Pickup_Schedule V2.xlsx
CHECK_INTERVAL_SECONDS=60
REMINDER_MINUTES_BEFORE=30
```

### Step 4: Run the Agent

```bash
# Ensure virtual environment is active
python agent.py
```

Console Output Example:

```
==============================================================
  Mr. Cabie — Driver Pickup Reminder Agent (v1)
==============================================================

[SUCCESS] Configuration validated successfully.

[CONFIG] Configuration Details:
  Excel File     : Sample_Driver_Pickup_Schedule V2.xlsx
  Webhook URL    : https://driver-pickup-reminder-agent.onrender.com
  Check Interval : 60 seconds
  Reminder Before: 30 minutes
  Twilio Number  : +17372508034
--------------------------------------------------------------

[RUNNING] Agent active. Polling schedule every 60 seconds.
Press Ctrl+C to stop.

--------------------------------------------------------------
Cycle #1 | 2026-08-19 00:05:06 IST
--------------------------------------------------------------
  [INFO] Scanning Excel for pending rides...
  [FOUND] 1 ride(s) due for reminder!

  [CALL] Initiating reminder for Mandeep Singh (+919971129359)
         Pickup Location : New Delhi
         Scheduled Time  : 12:35 AM
       [INFO] Call SID: CA98f962d6631f53297eedd40e19d9d968
       [INFO] Waiting for call status completion...
       [SUCCESS] Call completed — Reminder status set to 'Sent'
```

---

## Testing Guide: End-to-End Test With Your Mobile Number

Follow these steps to run a live test call to your mobile phone:

### 1. Verify Phone Number (Twilio Free Trial Accounts)
If using a Twilio Free Trial account, Twilio only allows calling numbers that have been verified in your account:
- Log in to your [Twilio Console](https://console.twilio.com/).
- Navigate to **Phone Numbers** > **Manage** > **Verified Caller IDs**.
- Add your mobile phone number (e.g. `+919971129359`) and complete OTP verification.

### 2. Update Excel Schedule for Testing
- Open `Sample_Driver_Pickup_Schedule V2.xlsx`.
- Select any row (or add a new row).
- Set `Driver Phone Number` to your verified mobile number (format: `+91XXXXXXXXXX`).
- Set `Scheduled Pickup Time` to **exactly 30 minutes from current local time (IST)**.
  - *Example*: If current time is `10:15 AM`, set pickup time to `10:45 AM`.
- Set `Reminder Status` to `Pending`.
- Save the Excel file.

### 3. Start the Agent
In your terminal, run:
```bash
python agent.py
```

### 4. Verify Call & Execution
- Within 60 seconds, `agent.py` will detect the ride scheduled 30 minutes away.
- Your mobile phone will ring from the configured `TWILIO_PHONE_NUMBER`.
- Answer the call to listen to the automated text-to-speech message.
- Check the terminal: output will show call initiation and status completion.
- Open `Sample_Driver_Pickup_Schedule V2.xlsx`: `Reminder Status` for your row will now display `Sent`.
- Open `call_logs.json`: A complete audit entry will be recorded with timestamp, SID, and status.

---

## Project Structure

```
mr cabie assignment/
├── venv/                    # Virtual environment
├── .env                     # Local environment configuration & API keys
├── .env.example             # Environment template
├── .gitignore               # Version control exclusion file
├── requirements.txt         # Dependencies list
├── config.py                # Configuration loader and validator
├── sheet_handler.py         # Excel schedule parser and status updater
├── call_handler.py          # Twilio API integration & status polling
├── server.py                # Flask webhook server (deployed on Render)
├── agent.py                 # Main scheduler agent loop
├── call_logs.json           # Execution logs
├── Procfile                 # Deployment process file
├── render.yaml              # Render configuration file
└── README.md                # Documentation
```

---

## Excel Sheet Format

| Driver Name | Driver Phone Number | Pickup Location | Scheduled Pickup Time | Reminder Status |
|-------------|--------------------|-----------------|-----------------------|-----------------|
| Rahul Kumar | +919876543210 | Cyber City Gurugram | 2026-08-18 21:39:00 | Pending |
| Suresh Singh | +919876543211 | Sector 14 Faridabad | 2026-08-18 22:00:00 | Pending |

**Reminder Status values:**
- `Pending`: Scheduled, awaiting reminder window.
- `Sent`: Call placed successfully and reminder delivered.
- `Failed - No Answer`: Driver did not pick up the call.
- `Failed - Busy`: Phone line was busy.
- `Failed - Error`: Error during call dispatch.

---

## Call Logs Format (`call_logs.json`)

```json
[
  {
    "timestamp": "2026-08-19T00:05:06.223962+05:30",
    "driver_name": "Mandeep Singh",
    "driver_phone": "+919971129359",
    "pickup_location": "New Delhi",
    "pickup_time": "12:35 AM",
    "call_sid": "CA98f962d6631f53297eedd40e19d9d968",
    "call_status": "completed",
    "reminder_status": "Sent"
  }
]
```

---

## Future Scope (v2 Improvements)

| Feature | Description |
|---------|-------------|
| **Conversational AI** | Enable bi-directional voice conversation during the call to process confirmation/questions. |
| **Live Location Tracking** | Integrate GPS tracking to trigger reminders based on actual driver distance rather than fixed timing. |
| **Escalation Management** | Automatically notify fleet managers if a driver fails to answer after multiple attempts. |
| **Multi-channel Fallback** | Send WhatsApp/SMS notifications if an voice call goes unanswered. |
| **Google Sheets API** | Synchronize directly with cloud Google Sheets instead of local Excel files. |
| **Analytics Dashboard** | Web dashboard for real-time monitoring of fleet call status. |

---

## Notes & Technical Specifications

- **Timezone**: All schedule calculations are based on IST (`Asia/Kolkata`).
- **Reminder Window**: The agent scans for rides scheduled within a 25 to 35 minute window (target: 30 minutes before pickup).
- **Trial Limitations**: Twilio trial accounts require recipient numbers to be registered in Verified Caller IDs.
