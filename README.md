# Mr. Cabie — Driver Pickup Reminder Agent (v1)

An automated agent that reminds drivers about upcoming pickups by calling them 30 minutes before the scheduled pickup time via Twilio. It reads the driver schedule from a Google Sheet, makes the call, plays a voice reminder, updates the sheet, and logs the result.

---

## How It Works

1. **Agent reads the Google Sheet** every 60 seconds looking for rides with a pickup time approximately 30 minutes from now (within a 25–35 minute window).
2. **For each matching ride**, it triggers an outbound call via Twilio to the driver's phone number.
3. **Twilio calls the driver** and plays a personalized voice message:
   > "Hello [Driver Name], this is an automated reminder from Mr. Cabie. You have a pickup scheduled at [Location] at [Time]. Please call or message your customer to confirm the pickup and make sure you reach the location on time. Thank you and drive safe."
4. **Agent tracks the call status** — if completed, the row's status is updated to "Sent"; if unanswered, it is marked as "Failed - No Answer". Only rows still marked `Pending` are picked up, so a driver is never called twice.
5. **All call attempts are logged** in `call_logs.json`.

---

## Architecture

```
      +------------------+
      |   Google Sheet   |   <-- the schedule (source of truth)
      |  (Sheets API)    |
      +--------+---------+
          ^         |
   update |         | read pending rides
   status |         v
      +---+------------------+
      |      agent.py        |   runs on a schedule:
      |     (Scheduler)      |   GitHub Actions cron (cloud)
      +----------+-----------+   or locally for a demo
                 |
          Trigger Call
                 v
        +-----------------+
        |   Twilio API    |
        | (Outbound Call) |
        +--------+--------+
                 |
       +---------+---------+
       |                   |
       v                   v
+----------------+   +------------------+
| Driver's Phone |<--|   Render Server  |
+----------------+   |    (server.py)   |
        TwiML XML    |  /voice endpoint |
                     +------------------+
```

**Split Deployment:**
- `server.py`: Deployed on Render (Free tier) at `https://driver-pickup-reminder-agent.onrender.com` — serves the TwiML voice XML that Twilio fetches during the call.
- `agent.py`: Scans the sheet, triggers Twilio calls, polls call status, writes the status back. Runs via GitHub Actions cron in the cloud (see [Running in the Cloud](#running-in-the-cloud-no-laptop-needed)), or locally with `python agent.py` for a demo.

Because the schedule *and* the reminder status both live in the Google Sheet, the agent keeps no local state — which is what lets it run as a short scheduled job instead of a process that must stay alive.

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- A Twilio account (Account SID, Auth Token, and Twilio Phone Number)
- A Google Sheet with the schedule, plus a Google Cloud service account (Step 3 below)

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

### Step 3: Google Sheets Setup

The agent reads and writes a live Google Sheet, so it needs read/write access via a service account:

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and **enable the Google Sheets API**.
2. Create a **Service Account** → **Keys** → **Add Key → JSON**. Save the downloaded file as `service_account.json` in the project root.
3. Open your Google Sheet → **Share** → add the service account's email (`name@project.iam.gserviceaccount.com`) as an **Editor**. Without this the agent gets a permission error.
4. Copy the sheet ID from its URL: `https://docs.google.com/spreadsheets/d/`**`<SHEET_ID>`**`/edit`.
5. Make sure the sheet has these columns, header in row 1, data from row 2:

   | A | B | C | D | E |
   |---|---|---|---|---|
   | Driver Name | Driver Phone Number | Pickup Location | Scheduled Pickup Time | Reminder Status |

> `service_account.json` holds a private key and is gitignored — never commit it.

### Step 4: Configure Environment Variables

Create or update the `.env` file in the root directory (template in `.env.example`):

```env
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+17372508034
RENDER_WEBHOOK_URL=https://driver-pickup-reminder-agent.onrender.com

# Google Sheet (from Step 3)
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_WORKSHEET_NAME=          # blank = first worksheet

CHECK_INTERVAL_SECONDS=60
REMINDER_MINUTES_BEFORE=30
```

### Step 5: Run the Agent

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
  Google Sheet ID: 1AbC...xYz
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
  [INFO] Scanning Google Sheet for pending rides...
  [FOUND] 1 ride(s) due for reminder!

  [CALL] Initiating reminder for Mandeep Singh (+919971129359)
         Pickup Location : New Delhi
         Scheduled Time  : 12:35 AM
       [INFO] Call SID: CA98f962d6631f53297eedd40e19d9d968
       [INFO] Waiting for call status completion...
       [SUCCESS] Call completed — Reminder status set to 'Sent'
```

---

## Running in the Cloud (no laptop needed)

`agent.py` supports a **single-cycle mode** so it can run on a scheduler instead of an always-on loop:

```bash
python agent.py --once   # scan once, act, then exit
```

**Why this matters:** the always-on loop only survives while your laptop is awake and the terminal is open. If the machine sleeps or the process dies, no driver gets called for that window — and nobody finds out. A cloud scheduler removes that single point of failure.

**Free option — GitHub Actions** (included at `.github/workflows/reminder-agent.yml`): runs `--once` every 5 minutes.
1. In your repo: **Settings → Secrets and variables → Actions**, add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `RENDER_WEBHOOK_URL`, `GOOGLE_SHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the whole JSON key).
2. Enable Actions — the agent now runs in the cloud on schedule.
3. Note: scheduled workflows only run on the repository's **default branch**.

**Alternatives:** a Render Cron Job (paid — see the commented service in `render.yaml`), or your OS cron / Windows Task Scheduler calling `python agent.py --once`.

> Each scheduled run happens on a fresh, throwaway machine — which is exactly why the status is written back to the Google Sheet rather than a local file. Nothing is kept on disk between runs.

---

## Testing Guide: End-to-End Test With Your Mobile Number

Follow these steps to run a live test call to your mobile phone:

### 1. Verify Phone Number (Twilio Free Trial Accounts)
If using a Twilio Free Trial account, Twilio only allows calling numbers that have been verified in your account:
- Log in to your [Twilio Console](https://console.twilio.com/).
- Navigate to **Phone Numbers** > **Manage** > **Verified Caller IDs**.
- Add your mobile phone number (e.g. `+919971129359`) and complete OTP verification.

### 2. Add a Test Row to the Google Sheet
- Open your Google Sheet.
- Add a row (or edit an existing one):
  - `Driver Phone Number` → your verified mobile number (format: `+91XXXXXXXXXX`).
  - `Scheduled Pickup Time` → **exactly 30 minutes from the current time (IST)**, e.g. `2026-08-19 10:45:00`.
    - *Example*: if it's `10:15 AM`, set the pickup time to `10:45 AM`.
  - `Reminder Status` → `Pending`.
- No need to save — Google Sheets saves automatically, and the agent reads it live.

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
- Watch the Google Sheet: `Reminder Status` for your row flips to `Sent` in real time.
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
├── sheet_handler.py         # Google Sheets read/write + time-window logic
├── call_handler.py          # Twilio API integration & status polling
├── server.py                # Flask webhook server (deployed on Render)
├── agent.py                 # Main scheduler agent loop (supports --once)
├── call_logs.json           # Execution logs
├── service_account.json     # Google service-account key (gitignored)
├── .github/workflows/       # GitHub Actions cron (cloud scheduler)
├── Procfile                 # Deployment process file
├── render.yaml              # Render configuration file
└── README.md                # Documentation
```

---

## Google Sheet Format

Header in row 1, data from row 2. Column order matters:

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

Only rows marked `Pending` are ever picked up, so a driver is never called twice for the same ride.

`Scheduled Pickup Time` is read as IST. `YYYY-MM-DD HH:MM:SS` is the safest format; other common formats (e.g. `18/08/2026 21:39`) are parsed as day-first.

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
| **Call Confirmation (DTMF)** | Let the driver press 1 to confirm / 2 to decline during the call, and record the response back to the sheet. |
| **Analytics Dashboard** | Web dashboard for real-time monitoring of fleet call status. |

---

## Notes & Technical Specifications

- **Timezone**: All schedule calculations are based on IST (`Asia/Kolkata`).
- **Reminder Window**: The agent scans for rides scheduled within a 25 to 35 minute window (target: 30 minutes before pickup).
- **Trial Limitations**: Twilio trial accounts require recipient numbers to be registered in Verified Caller IDs.
