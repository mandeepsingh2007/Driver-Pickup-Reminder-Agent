# Mr. Cabie — Driver Pickup Reminder Agent (v1)

An automated agent that reminds drivers about upcoming pickups by calling them 30 minutes before the scheduled pickup time via Twilio. It reads the driver schedule, makes the call, plays a voice reminder, updates the schedule with the result, and logs every attempt.

The schedule can come from either a **local Excel file** (included in this repo — no setup, just clone and run) or a **live Google Sheet**. See [Step 3](#step-3-choose-your-schedule-source).

---

## How It Works

1. **Agent reads the schedule** every 60 seconds looking for rides with a pickup time approximately 30 minutes from now (within a 25–35 minute window).
2. **For each matching ride**, it triggers an outbound call via Twilio to the driver's phone number.
3. **Twilio calls the driver** and plays a personalized voice message:
   > "Hello [Driver Name], this is an automated reminder from Mr. Cabie. You have a pickup scheduled at [Location] at [Time]. Please call or message your customer to confirm the pickup and make sure you reach the location on time. Thank you and drive safe."
4. **Agent tracks the call status** — if completed, the row's status is updated to "Sent"; if unanswered, it is marked as "Failed - No Answer". Only rows still marked `Pending` are picked up, so a driver is never called twice.
5. **All call attempts are logged** in `call_logs.json`.

---

## Architecture

```
      +------------------------+
      |       SCHEDULE         |   Excel file  (default)
      |  (source of truth)     |        or
      +-----------+------------+   Google Sheet (live, via API)
          ^             |
   update |             | read pending rides
   status |             v
      +---+------------------------+
      |         agent.py           |   python agent.py         (polling loop)
      |        (Scheduler)         |   python agent.py --once  (cron / cloud)
      +-------------+--------------+
                    |
             Trigger Call
                    v
          +-------------------+
          |    Twilio API     |
          |  (Outbound Call)  |
          +---------+---------+
                    |
         +----------+----------+
         |                     |
         v                     v
 +----------------+   +-------------------+
 | Driver's Phone |<--|   Render Server   |
 +----------------+   |    (server.py)    |
         TwiML XML    |  /voice endpoint  |
                      +-------------------+
```

**Split Deployment:**
- `server.py`: Deployed on Render (Free tier) at `https://driver-pickup-reminder-agent.onrender.com` — serves the TwiML voice XML that Twilio fetches during the call.
- `agent.py`: Scans the schedule, triggers Twilio calls, polls call status, writes the status back. Runs locally with `python agent.py`, or in the cloud via cron (see [Running in the Cloud](#running-in-the-cloud-no-laptop-needed)).

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

### Step 3: Choose Your Schedule Source

Set `SHEET_BACKEND` in `.env` to pick where the schedule is read from. Everything else in the app is identical either way.

| | **Option A — Excel** | **Option B — Google Sheet** |
|---|---|---|
| `SHEET_BACKEND` | `excel` *(default)* | `google` |
| Setup needed | **None** — file is in this repo | Google Cloud project + service account |
| Time to first run | ~1 minute | ~10 minutes |
| Best for | **Testing and reviewing this project** | Matching the task spec; required for cloud runs |

---

#### Option A — Local Excel file ✅ *recommended for testing*

**Nothing to configure.** `Sample_Driver_Pickup_Schedule V2.xlsx` is committed to this repo, and `SHEET_BACKEND=excel` is the default — so you can clone, add your Twilio credentials, and run.

Just edit the `.xlsx` in Excel / LibreOffice to add test rides. Remember to **save and close the file** before the agent's next cycle, since a file locked open by Excel can't be written to.

---

#### Option B — Live Google Sheet ⚠️ *not recommended for a quick test*

This matches the task's stated input and is what the cloud scheduler needs, but it requires a Google Cloud service account — roughly 10 minutes of one-time setup, and a Google account with Cloud Console access. **If you just want to see the agent work, use Option A instead.**

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and **enable the Google Sheets API**.
2. Create a **Service Account** → **Keys** → **Add Key → JSON**. Save the downloaded file as `service_account.json` in the project root.
3. Open your Google Sheet → **Share** → add the service account's email (`name@project.iam.gserviceaccount.com`) as an **Editor**. Skipping this is the most common cause of a permission error.
4. Copy the sheet ID from its URL: `https://docs.google.com/spreadsheets/d/`**`<SHEET_ID>`**`/edit`.
5. In `.env`, set `SHEET_BACKEND=google` and `GOOGLE_SHEET_ID=<SHEET_ID>`.

To create the sheet quickly, import the included `.xlsx`: in Google Sheets, **File → Import → Upload**, then **Replace spreadsheet**. Format the `Scheduled Pickup Time` column as **plain text** so Google doesn't reformat the timestamps.

> `service_account.json` holds a private key and is gitignored — never commit it.

### Step 4: Configure Environment Variables

Create or update the `.env` file in the root directory (template in `.env.example`):

```env
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+17372508034
RENDER_WEBHOOK_URL=https://driver-pickup-reminder-agent.onrender.com

# Schedule source: "excel" (default, no setup) or "google"
SHEET_BACKEND=excel

# Used when SHEET_BACKEND=excel
EXCEL_FILE_PATH=Sample_Driver_Pickup_Schedule V2.xlsx

# Used when SHEET_BACKEND=google (see Option B)
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json
GOOGLE_SHEET_ID=
GOOGLE_WORKSHEET_NAME=

CHECK_INTERVAL_SECONDS=60
REMINDER_MINUTES_BEFORE=30
```

Only the block matching your chosen `SHEET_BACKEND` needs real values — the other can stay blank.

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
  Schedule Source: excel
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
  [INFO] Scanning schedule for pending rides...
  [FOUND] 1 ride(s) due for reminder!
  [INFO] Warming up webhook server...
  [OK] Webhook is awake.

  [CALL] Initiating reminder for Mandeep Singh (+919971129359)
         Pickup Location : New Delhi
         Scheduled Time  : 12:35 AM
       [INFO] Call SID: CA98f962d6631f53297eedd40e19d9d968
       [INFO] Waiting for call status completion...
       [SUCCESS] Call completed — Reminder status set to 'Sent'
```

---

## Testing Guide: End-to-End Test With Your Mobile Number

Follow these steps to run a live test call to your own phone. This uses **Option A (Excel)** — no Google setup required.

### 1. Verify Phone Number (Twilio Free Trial Accounts)
If using a Twilio Free Trial account, Twilio only allows calling numbers that have been verified in your account:
- Log in to your [Twilio Console](https://console.twilio.com/).
- Navigate to **Phone Numbers** > **Manage** > **Verified Caller IDs**.
- Add your mobile phone number (e.g. `+919971129359`) and complete OTP verification.

### 2. Add a Test Row to the Schedule
- Open `Sample_Driver_Pickup_Schedule V2.xlsx`.
- Edit any row (or add a new one):
  - `Driver Phone Number` → your verified mobile number (format: `+91XXXXXXXXXX`).
  - `Scheduled Pickup Time` → **about 30 minutes from the current time (IST)**, e.g. `2026-08-19 10:45:00`.
    - *Example*: if it's `10:15 AM`, set the pickup time to `10:45 AM`.
    - Anything between 25 and 35 minutes ahead will be picked up, so you don't need to be exact.
  - `Reminder Status` → `Pending`.
- **Save and close the file** — the agent can't update a row while Excel holds the file open.

*(On Option B, edit the Google Sheet instead — no saving needed, the agent reads it live.)*

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
- Reopen the schedule: `Reminder Status` for your row now reads `Sent`.
- Open `call_logs.json`: A complete audit entry will be recorded with timestamp, SID, and status.

> **If the call connects but plays an error message**, the Render webhook was still waking up. The free tier sleeps after ~15 minutes idle and a cold start outlasts Twilio's ~15s webhook timeout. The agent now pings `/health` before dialling to avoid this, but the very first call after a long idle period can still be tight — just run the test again.

---

## Running in the Cloud (no laptop needed)

`agent.py` supports a **single-cycle mode** so it can run on a scheduler instead of an always-on loop:

```bash
python agent.py --once   # scan once, act, then exit
```

**Why this matters:** the always-on loop only survives while your laptop is awake and the terminal is open. If the machine sleeps or the process dies, no driver gets called for that window — and nobody finds out. A cloud scheduler removes that single point of failure.

**This requires `SHEET_BACKEND=google`.** Each scheduled run happens on a fresh, throwaway machine, so a status written to a local Excel file would vanish — and the same driver would be called again on the next run. The Google Sheet keeps that state in the cloud.

**Free option — GitHub Actions** (included at `.github/workflows/reminder-agent.yml`): runs `--once` every 5 minutes.
1. In your repo: **Settings → Secrets and variables → Actions**, add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `RENDER_WEBHOOK_URL`, `GOOGLE_SHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the whole JSON key).
2. Enable Actions — the agent now runs in the cloud on schedule.
3. Note: scheduled workflows only run on the repository's **default branch**.

**Alternatives:** a Render Cron Job (paid — see the commented service in `render.yaml`), or your OS cron / Windows Task Scheduler calling `python agent.py --once`.

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
├── sheet_handler.py         # Schedule read/write (Excel + Google) & time window
├── call_handler.py          # Twilio API integration & status polling
├── server.py                # Flask webhook server (deployed on Render)
├── agent.py                 # Main scheduler agent loop (supports --once)
├── Sample_Driver_Pickup_Schedule V2.xlsx   # Sample schedule (Option A)
├── call_logs.json           # Execution logs
├── service_account.json     # Google service-account key (gitignored, Option B)
├── .github/workflows/       # GitHub Actions cron (cloud scheduler)
├── Procfile                 # Deployment process file
├── render.yaml              # Render configuration file
└── README.md                # Documentation
```

---

## Schedule Format

Same columns for both Excel and Google Sheets. Header in row 1, data from row 2. Column order matters:

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
| **Call Confirmation (DTMF)** | Let the driver press 1 to confirm / 2 to decline during the call, and record the response back to the schedule. |
| **Multi-channel Fallback** | Send a WhatsApp/SMS reminder first (cheaper, and drivers read it), falling back to a voice call if unconfirmed. |
| **Multilingual Voice** | A `Language` column driving Hindi or regional TTS voices, so the reminder is actually understood. |
| **Escalation Management** | Retry unanswered calls with backoff, then alert a fleet manager if the driver still can't be reached. |
| **Travel-time-aware Timing** | Use a maps API to remind the driver when they need to *leave*, accounting for live traffic, instead of a fixed 30 minutes. |
| **Conversational AI** | Bi-directional voice conversation so the driver can ask questions or reschedule. |
| **Analytics Dashboard** | Web dashboard for real-time fleet call status, plus which drivers repeatedly miss reminders. |

---

## Notes & Technical Specifications

- **Timezone**: All schedule calculations are based on IST (`Asia/Kolkata`).
- **Reminder Window**: The agent scans for rides scheduled within a 25 to 35 minute window (target: 30 minutes before pickup).
- **Trial Limitations**: Twilio trial accounts require recipient numbers to be registered in Verified Caller IDs.
- **Webhook Warm-up**: Before dialling, the agent pings the Render `/health` endpoint so a sleeping free-tier server is awake by the time Twilio requests the TwiML.
