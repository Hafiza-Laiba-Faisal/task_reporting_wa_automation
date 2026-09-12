# Setup Guide — WhatsApp Task Automation

## Requirements

- Ubuntu / Debian Linux
- Python 3.11+
- Google Chrome installed
- Internet connection

---

## Step 1: Clone the Repo

```bash
git clone https://github.com/Hafiza-Laiba-Faisal/task_reporting_wa_automation.git
cd task_reporting_wa_automation
```

---

## Step 2: Create Virtual Environment & Install Dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

---

## Step 3: Configure .env

Copy the example file:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# WhatsApp group name — must match exactly as shown in WhatsApp
WHATSAPP_GROUP_NAME=TenBit_Daily_Task_Reporting

# LLM Provider (openrouter recommended — free models available)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free
```

Everything else can stay as default.

---

## Step 4: Google Sheets Setup (Optional)

Skip this step if you only want Excel output.

### 4a. Create Google Cloud Project

1. Go to: https://console.cloud.google.com/
2. Click **New Project** → name it `TenBit Automation` → **Create**
3. Go to **APIs & Services → Library**
4. Search and enable: **Google Sheets API**
5. Search and enable: **Google Drive API**

### 4b. Create Service Account

1. Go to **APIs & Services → Credentials**
2. Click **+ CREATE CREDENTIALS → Service account**
3. Name: `tenbit-automation` → **Create and Continue → Done**

### 4c. Download Credentials JSON

1. Click on the service account you just created
2. Go to **Keys** tab → **Add Key → Create new key**
3. Select **JSON** → **Create**
4. A file downloads (e.g. `tenbit-automation-abc123.json`)
5. Rename it to `credentials.json` and move it to the project root:

```bash
mv ~/Downloads/tenbit-automation-*.json ./credentials.json
```

### 4d. Create Google Sheet

1. Go to: https://sheets.google.com/
2. Create a new blank spreadsheet
3. Name it: `TenBit Task Report`
4. Copy the **Spreadsheet ID** from the URL:

```
https://docs.google.com/spreadsheets/d/  1BxiMVs0XRA...  /edit
                                          ↑ this is the ID
```

### 4e. Share Sheet with Service Account

1. Open `credentials.json`, find the `client_email` field:
   ```
   "client_email": "tenbit-automation@your-project.iam.gserviceaccount.com"
   ```
2. Go to your Google Sheet → **Share** button (top right)
3. Paste that email → Role: **Editor** → uncheck "Notify people" → **Share**

### 4f. Update .env

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_ID=1BxiMVs0XRA...          # paste your spreadsheet ID
GOOGLE_SHEETS_CREDENTIALS=./credentials.json
GOOGLE_SHEETS_SHARE_WITH=               # optional: comma-separated emails
```

---

## Step 5: Run the App

```bash
.venv/bin/python start_app.py
```

Browser opens at: **http://127.0.0.1:8000**

---

## Step 6: First-Time WhatsApp Login

1. In the UI, click **▶️ Run Task Extraction**
2. A Chrome window will open with WhatsApp Web
3. On your phone: **WhatsApp → 3 dots → Linked Devices → Link a Device**
4. Scan the QR code shown on screen
5. Session saves automatically — no re-scan needed next time

---

## Daily Usage

```bash
cd task_reporting_wa_automation
.venv/bin/python start_app.py
```

Then in the browser:
- Click **▶️ Run Task Extraction** — collects messages + extracts tasks
- Click **⬇️ Download Excel** — download the report
- Click **🔗 Sync to Google Sheets** — sync to cloud (if enabled)

---

## Troubleshooting

**App won't start:**
```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

**WhatsApp session expired (re-scan needed):**
```bash
rm -rf ~/.config/whatsapp_wa_bot_profile
```
Then run the app again and scan QR.

**Google Sheets error — credentials not found:**
Make sure `credentials.json` is in the project root folder.

**Rate limit error (LLM):**
Wait 2–3 minutes and click **🔄 Reprocess from DB** — no WhatsApp re-open needed.
