# 🚕 Mr. Cabie — Driver Pickup Reminder Agent (v1)

An automated agent that reminds drivers about upcoming pickups by calling them **30 minutes before the scheduled pickup time** via Twilio. It reads the driver schedule from an Excel sheet, makes the call, plays a voice reminder, and logs the result.

---

## 📋 How It Works

1. **Agent reads the Excel sheet** every 60 seconds looking for rides with a pickup time ~30 minutes from now
2. **For each matching ride**, it triggers an outbound call via Twilio to the driver's phone
3. **Twilio calls the driver** and plays a personalized voice message:
   > *"Hello [Driver Name], this is a reminder from Mr. Cabie. You have a pickup at [Location] at [Time]. Please call your customer and be on time."*
4. **Agent tracks the call status** — if completed, the Excel row is marked "Sent"; if unanswered, it's marked "Failed - No Answer"
5. **All call attempts are logged** in `call_logs.json`

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                  LOCAL MACHINE                    │
│                                                  │
│  ┌──────────┐     ┌───────────────┐              │
│  │  Excel   │────▶│   agent.py    │              │
│  │  Sheet   │◀────│  (Scheduler)  │              │
│  └──────────┘     └───────┬───────┘              │
│                           │                      │
│                    Trigger Call                   │
│                           │                      │
└───────────────────────────┼──────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │   Twilio API    │
                   │  (Outbound Call)│
                   └────────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼                           ▼
     ┌─────────────┐            ┌──────────────────┐
     │   Driver's   │            │  Render Server   │
     │    Phone     │◀───────────│   (server.py)    │
     └─────────────┘   TwiML    │  /voice endpoint  │
                      Message   └──────────────────┘
```

**Split Deployment:**
- `server.py` → Deployed on **Render (free tier)** — serves the TwiML voice message
- `agent.py` → Runs **locally** — reads Excel, triggers calls, updates statuses

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+
- A [Twilio account](https://www.twilio.com/try-twilio) (free trial works)
- A [Render account](https://render.com) (free tier)

### Step 1: Clone & Virtual Environment

```bash
cd "mr cabie assignment"

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy the template
cp .env.example .env

# Edit .env with your values
```

Fill in your `.env` file:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
RENDER_WEBHOOK_URL=https://your-app-name.onrender.com
EXCEL_FILE_PATH=Sample_Driver_Pickup_Schedule V2.xlsx
CHECK_INTERVAL_SECONDS=60
REMINDER_MINUTES_BEFORE=30
```

### Step 4: Deploy Webhook to Render

1. Push your code to a **GitHub repository**
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New → Web Service**
4. Connect your GitHub repo
5. Settings:
   - **Name**: `mr-cabie-reminder`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app`
   - **Plan**: Free
6. Click **Deploy**
7. Copy the URL (e.g., `https://mr-cabie-reminder.onrender.com`)
8. Update `RENDER_WEBHOOK_URL` in your `.env` file

### Step 5: Run the Agent

```bash
# Make sure venv is activated
venv\Scripts\activate

# Run the agent
python agent.py
```

You'll see output like:

```
╔══════════════════════════════════════════════════════════════╗
║   🚕  Mr. Cabie — Driver Pickup Reminder Agent (v1)        ║
╚══════════════════════════════════════════════════════════════╝

  ✓ Configuration validated successfully

  🚀 Agent started! Checking every 60 seconds.
  Press Ctrl+C to stop.

──────────────────────────────────────────────────────────────
  Cycle #1 │ 2026-08-18 21:09:00 IST
──────────────────────────────────────────────────────────────
  📋 Scanning Excel for pending rides...
  🔔 Found 1 ride(s) due for reminder!

  📞 Calling Rahul Kumar at +919876543210
     Pickup: Cyber City Gurugram at 09:39 PM
     ⏳ Call initiated (SID: CA1234567890...)
     ⏳ Waiting for call to complete...
     ✓ Call completed — Reminder sent!
```

---

## 📁 Project Structure

```
mr cabie assignment/
├── venv/                    # Virtual environment
├── .env                     # Your credentials (gitignored)
├── .env.example             # Template
├── .gitignore
├── requirements.txt         # Python dependencies
├── config.py                # Configuration loader
├── sheet_handler.py         # Excel read/write operations
├── call_handler.py          # Twilio call trigger + status polling
├── server.py                # Flask webhook (deployed on Render)
├── agent.py                 # Main scheduler (runs locally)
├── call_logs.json           # Call attempt logs (auto-generated)
├── Procfile                 # Render deployment
├── render.yaml              # Render config
├── README.md                # This file
└── Sample_Driver_Pickup_Schedule V2.xlsx
```

---

## 📊 Excel Sheet Format

| Driver Name | Driver Phone Number | Pickup Location | Scheduled Pickup Time | Reminder Status |
|-------------|--------------------|-----------------|-----------------------|-----------------|
| Rahul Kumar | +919876543210 | Cyber City Gurugram | 2026-08-18 21:39 | Pending |
| Suresh Singh | +919876543211 | Sector 14 Faridabad | 2026-08-18 22:00 | Pending |

**Reminder Status values:**
- `Pending` — Not yet processed
- `Sent` — Call completed, reminder delivered
- `Failed - No Answer` — Driver didn't pick up
- `Failed - Busy` — Line was busy
- `Failed - Error` — Call failed due to an error

---

## 📝 Call Logs

All call attempts are logged in `call_logs.json`:

```json
[
  {
    "timestamp": "2026-08-18T21:09:00+05:30",
    "driver_name": "Rahul Kumar",
    "driver_phone": "+919876543210",
    "pickup_location": "Cyber City Gurugram",
    "pickup_time": "09:39 PM",
    "call_sid": "CA1234567890abcdef",
    "call_status": "completed",
    "reminder_status": "Sent"
  }
]
```

---

## 🔮 v2 Improvement Ideas

If given more time, here's what could be added:

| Feature | Description |
|---------|-------------|
| **Conversational AI** | Allow drivers to respond on the call (confirm, ask questions) |
| **Live GPS Tracking** | Use driver's real-time location for smarter ETA-based reminders |
| **Escalation** | Notify fleet manager if driver doesn't answer after retries |
| **Retry Logic** | Automatically retry unanswered calls after 5 minutes |
| **WhatsApp/SMS Fallback** | Send a text if call fails |
| **Google Sheets API** | Direct integration instead of local Excel |
| **Dashboard** | Web UI to monitor call statuses and driver responses in real-time |
| **Multi-language** | Support Hindi/English messages based on driver preference |
| **Scheduling** | Deploy agent to cloud (e.g., Render cron or AWS Lambda) instead of running locally |

---

## ⚠️ Notes

- The agent checks for rides within a **±5 minute window** around the 30-minute mark to avoid missing rides due to timing
- **Twilio free trial** requires verified phone numbers — you can only call numbers you've verified in your Twilio console
- The Render free tier server may **spin down after inactivity** — the first call after idle may take ~30 seconds to connect. This is normal.
- All times are in **IST (Asia/Kolkata)** timezone

---

## 📄 License

Built for Mr. Cabie — Internal use only.
