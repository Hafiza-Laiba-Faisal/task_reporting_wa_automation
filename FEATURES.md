# Features — WhatsApp Task Automation

## What This System Does

Automatically collects messages from a WhatsApp group, extracts employee tasks using AI, and exports them to Excel and Google Sheets — every day, with one click.

---

## Core Features

### 1. WhatsApp Message Collection
- Opens WhatsApp Web using a persistent browser session
- Collects messages from the last **2 days** (today + yesterday)
- Saves sender name, timestamp, and message text to local database
- Session is saved after first QR scan — no re-scan needed daily

### 2. AI Task Extraction (LLM)
- Sends all collected messages to an AI model in one batch
- AI understands full conversation context before extracting tasks
- Extracts: task description, assignee, status, priority, deadline, confidence score
- Morning message ("working on X") → `in_progress`
- Evening message ("X done") → `completed` (updates same record, no duplicate)
- Supports multiple LLM providers (see LLM section below)

### 3. Excel Export
- Generates a formatted `.xlsx` file with this layout:

```
| Date     | Ayan          | Rameen        | Haris         | ...  |
|          | Tasks  Status | Tasks  Status | Tasks  Status | ...  |
|----------|---------------|---------------|---------------|------|
| 08 Sep   | • Task 1  ✅  | • Task 2  🔄  |      —        | ...  |
| 09 Sep   | • Task 3  📋  |      —        | • Task 4  ✅  | ...  |
```

- Color-coded status cells (green = done, amber = in progress, blue = open, red = blocked)
- Old date rows are **preserved** — reprocess only updates the last 2 days
- Download via the UI with one click

### 4. Google Sheets Sync
- Same layout as Excel, written to a cloud Google Spreadsheet
- Auto-syncs after every run (if enabled)
- Old date rows preserved — only last 2 days updated
- Can share with team emails automatically
- Requires: Google Cloud service account + credentials.json (see SETUP.md)

### 5. Smart Deduplication (Upsert)
- Each task is fingerprinted by: `task text + assignee + date`
- If the same task appears again (e.g. evening status update), it **updates** the existing record
- No duplicate rows in database or Excel

### 6. Sender Name Mapping
- Phone numbers and WhatsApp handles are mapped to real names
- Configured in `.env` under `SENDER_NAME_MAP`
- Example: `923096633317=Haris Javed,AT=Ayan`
- Names appear correctly in Excel/Sheets columns

---

## LLM Providers Supported

All providers use OpenAI-compatible API — switch with one config change.

| Provider | Type | Cost | Notes |
|----------|------|------|-------|
| OpenRouter | Cloud | Free tier available | Default — Nemotron Super free model |
| NVIDIA NIM | Cloud | Free tier available | Fast, high quality |
| Mistral | Cloud | Free tier | Rate limits apply |
| OpenAI | Cloud | Paid | GPT-4o, GPT-4o-mini |
| Ollama | Local | Free | Fully offline, runs on your machine |

Switch provider from the UI → **LLM Provider Configuration** section.

---

## Web Interface (Dashboard)

Access at: `http://127.0.0.1:8000` after starting the app.

### Quick Actions
| Button | What it does |
|--------|-------------|
| ▶️ Run Task Extraction | Opens WhatsApp, collects messages, extracts tasks, updates Excel + Sheets |
| 🔄 Reprocess from DB | Re-extracts tasks from saved messages — no WhatsApp needed |
| ⬇️ Download Excel | Downloads the generated `.xlsx` report |
| 🔗 Sync to Google Sheets | Manually pushes current tasks to Google Sheets |
| 🔃 Refresh All | Reloads all config and data from server |

### Configuration Panels
- **General Config** — WhatsApp group name, dry run mode
- **LLM Config** — Provider, model, API key, base URL
- **Google Sheets** — Enable/disable, spreadsheet ID, credentials, team emails

### Database Viewer
- **Tasks tab** — Search by assignee/task, filter by status
- **Messages tab** — Search by sender/content, filter by sender

---

## Data Flow

```
WhatsApp Group
    ↓ (Playwright browser)
Message Collector
    ↓ (saves to SQLite)
LLM Extractor
    ↓ (batch API call)
Task Processor
    ├──→ SQLite DB (upsert)
    ├──→ Excel file (last 2 days, old rows preserved)
    └──→ Google Sheets (last 2 days, old rows preserved)
```

---

## Known Behaviors

**Consecutive messages show as `unknown`**
WhatsApp hides the sender name for consecutive messages from the same person. The LLM sees no name and assigns `unknown`. Fix: add the person to `SENDER_NAME_MAP` in `.env` with their phone number.

**Duplicate tasks in same column**
If LLM extracts the same task from morning and evening messages separately, both appear. This is by design — the upsert logic merges them if the wording is identical.

**Tasks attributed to wrong person**
If someone quotes or forwards another person's message, the LLM may assign the task to the original sender. This is an LLM interpretation issue — review and reprocess if needed.

---

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Database | `data/tasks.db` | All messages + tasks (SQLite) |
| Excel report | `data/tasks.xlsx` | Latest 2-day export |
| Credentials | `credentials.json` | Google Sheets auth (do not commit) |
| Config | `.env` | All settings |
| Logs | `logs/` | Per-module log files |
| Screenshots | `screenshots/` | Browser debug snapshots |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Browser automation | Playwright (Chromium) |
| Database | SQLite (via Python sqlite3) |
| Excel | openpyxl |
| Google Sheets | gspread + google-auth |
| LLM | OpenAI-compatible API (OpenRouter / NVIDIA / Mistral / Ollama) |
| Frontend | Plain HTML + CSS + Vanilla JS |
| Server | Uvicorn (ASGI) |
