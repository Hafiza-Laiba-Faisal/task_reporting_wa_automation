# Decision Document — WhatsApp Task Reporting Automation

> **Project:** TenBit Daily Task Reporting Automation
> **Stack:** Python · Playwright · Mistral AI · SQLite · openpyxl · FastAPI
> **Last Updated:** September 2026

---

## 1. PROJECT OBJECTIVE

This project automates the extraction of actionable tasks from one specific WhatsApp group (`TenBit_Daily_Task_Reporting`) and writes them into an Excel workbook. The business problem is that team members share daily work updates in WhatsApp, but those updates are manually copied into spreadsheets — which is slow, error-prone, and easy to miss.

The automation:
- Opens WhatsApp Web using a persistent browser session (no QR scan after first run)
- Locates and verifies the configured target group
- Collects today's messages from that group
- Sends all messages together to Mistral AI for context-aware batch task extraction
- Writes structured tasks to Excel and SQLite
- Exposes a web UI for configuration, triggering runs, and viewing the DB

---

## 2. REQUIREMENTS

**Functional:**
1. Read messages from one specific WhatsApp group only
2. Identify actionable tasks; skip chatter, greetings, phone numbers
3. Extract: task description, assignee, deadline, priority, status
4. Preserve source metadata: original message, sender, timestamp, group
5. Avoid duplicate task creation via message fingerprinting
6. Update Excel automatically after each run
7. Maintain processing state in SQLite
8. Support re-processing from DB without re-opening WhatsApp
9. Resolve phone-number-based sender names to real names via config
10. Provide a web UI to view messages and tasks from DB
11. Support dry-run mode for safe testing

---

## 3. NON-GOALS

- Read multiple groups or entire WhatsApp account
- Send WhatsApp messages automatically
- Use the official WhatsApp Business API
- Use n8n, Zapier, or any low-code platform
- Guarantee indefinite reliability if WhatsApp Web changes its DOM

---

## 4. ARCHITECTURE DECISIONS

### 4.1 WhatsApp Automation: Playwright + Persistent Browser Profile

**Decision:** Use Playwright with `launch_persistent_context()` pointed at a dedicated Chromium profile.

**Why:**
- First run: user scans QR once; session saved to `~/.config/whatsapp_wa_bot_profile`
- All subsequent runs: browser opens directly to logged-in WhatsApp — no QR needed
- Full control over the automation flow

**Risk:** WhatsApp Web DOM can change; selectors may break.
**Mitigation:** Multiple fallback selectors tried in order; screenshots saved on failure.

---

### 4.2 Group Finding Strategy

**Decision:** Use WhatsApp search box to find the group, then match only the title element — not the full cell text.

**Problem solved:** `div[data-testid='cell-frame-container']` `inner_text()` returns the full cell including last message, timestamp, unread count — making exact name matching impossible.

**Fix:** Extract only `span[data-testid='cell-frame-title']` or `span[title]` from each row. This gives just the group name for clean comparison.

**Selectors tried in order:**
```
div[data-testid='cell-frame-container']
li[data-testid='cell-frame-container']
div[role='option']
div[role='listitem']
div[role='row']
```

**Title extraction selectors:**
```
span[data-testid='cell-frame-title']
span[title]
div[data-testid='cell-frame-title']
span[dir='auto']
```

---

### 4.3 Group Verification

**Decision:** Use `header[data-testid='conversation-header']` specifically, not `header` (which resolves to 4 elements on the page).

**Problem solved:** Playwright strict mode violation — multiple `<header>` elements exist (chat list header, conversation header, etc.).

---

### 4.4 Message Collection

**Decision:** After group opens, wait for `div[data-testid='conversation-panel-messages']` to confirm messages are loaded, then collect from `div[data-testid='msg-container']`.

**Why not `div[role='listitem']`:** That selector matches the sidebar chat list, not the chat messages.

**Message selectors tried in order:**
```
div[data-testid='msg-container']
div.message-in, div.message-out
div[role='row']
```

---

### 4.5 LLM Extraction: Batch Mode (all messages in one call)

**Decision:** Send ALL messages from the current run to Mistral in a single API call, not message-by-message.

**Why:**
- Per-message calls: no context → "I am working on MYP Creatives" can't be understood in isolation
- Batch call: Mistral reads the full conversation → understands context, merges related messages, splits task lists

**Format sent to Mistral:**
```
Date: 9 Sep 2026

[7:45] Chaudhry Safian: Create EITMAAD carousel and posts
[12:23] Rimsha: Rimsha Tasks list: HRA Social Media Creatives: ...
[1:35] MUHAMMAD UZAIR: I am Working on MYP Creatives
```

**Mistral returns:** A JSON array of tasks with assignee, status, priority, etc.

---

### 4.6 Sender Name Resolution

**Problem:** WhatsApp shows unsaved contacts as phone numbers (e.g., `+92 304 4233803 Chaudhry Safian`). The sender field in messages becomes polluted with phone numbers.

**Decision:** Add `SENDER_NAME_MAP` to `.env`:
```
SENDER_NAME_MAP=923044233803=Chaudhry Safian,923234770731=Muhammad Uzair
```

`config.py` parses this and `message_collector.py` calls `resolve_sender_name()` on every extracted sender — strips digits from raw text and matches against the map.

---

### 4.7 Reprocess from DB

**Problem:** Mistral has rate limits. If `/api/run` hits a 429 during extraction, messages are already saved in DB but tasks were never written.

**Decision:** Add `/api/reprocess` endpoint — reads messages from SQLite, runs batch extraction, writes tasks and Excel. Does not open WhatsApp.

**Flow:**
```
/api/run     → WhatsApp → collect messages → DB → Mistral → tasks → Excel
/api/reprocess           → DB → Mistral → tasks → Excel
```

---

### 4.8 Web UI

**Pages/endpoints:**
- `/` — Main UI with config form, run buttons, DB viewer tabs
- `/api/run` — Full pipeline (opens WhatsApp)
- `/api/reprocess` — Re-extract from DB (no WhatsApp)
- `/api/db/messages` — View collected messages
- `/api/db/tasks` — View extracted tasks
- `/api/config` GET/POST — Read/write configuration

**DB Viewer tabs:**
- **Tasks DB:** Assignee, Task, Status badge, Priority badge, Deadline, Sender, Time, Confidence
- **Messages DB:** Sender, Message, Time, Collected At

---

## 5. FAILURE HANDLING

| Failure | Behavior |
|---|---|
| Chat list empty after search | Try 5 different selectors; wait up to `MAX_GROUP_SEARCH_WAIT_SECONDS` |
| Group title mismatch | Stop; save screenshot to `screenshots/` |
| Multiple `<header>` elements | Use `header[data-testid='conversation-header']` specifically |
| Messages pane not loaded | Wait up to 15s for `div[data-testid='conversation-panel-messages']` |
| Mistral 429 rate limit | Raise `RateLimitError`; return HTTP 429 from `/api/reprocess`; user retries manually |
| Mistral returns markdown-wrapped JSON | Strip ` ```json ` fences before parsing |
| LLM returns wrong field names | Normalize: `source_sender` → `sender`, `assigned_to` → `assignee` |
| Invalid priority/status value | Sanitize to allowed values before Pydantic validation |
| Duplicate message fingerprint | Skip silently; log count |

---

## 6. CONFIGURATION REFERENCE

```env
# WhatsApp
WHATSAPP_GROUP_NAME=TenBit_Daily_Task_Reporting
WHATSAPP_URL=https://web.whatsapp.com
WHATSAPP_PROFILE_PATH=~/.config/whatsapp_wa_bot_profile

# Mistral
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=mistral-small-latest

# Pipeline
TARGET_WINDOW_DAYS=7
DRY_RUN=false
MAX_MESSAGES_PER_RUN=200
MAX_GROUP_SEARCH_WAIT_SECONDS=60

# Output
EXCEL_OUTPUT_PATH=./data/tasks.xlsx
DB_PATH=./data/tasks.db
LOG_LEVEL=INFO

# Sender name mapping (phone → real name)
# Format: 92xxxxxxxxxx=Name,92yyyyy=OtherName
SENDER_NAME_MAP=923044233803=Chaudhry Safian,923234770731=Muhammad Uzair,923278800186=AR,923090857761=Hanan Haider Kiani
```

---

## 7. PROJECT STRUCTURE

```
task_reporting_wa_automation/
├── app/
│   ├── whatsapp/
│   │   ├── browser.py          # Playwright browser, persistent profile
│   │   ├── group_finder.py     # Search, title extraction, verify, click
│   │   ├── message_collector.py # Collect today's messages, resolve sender names
│   │   └── parsers.py
│   ├── ai/
│   │   ├── extractor.py        # LLMTaskExtractor — batch mode entry point
│   │   ├── mistral_client.py   # MistralBatchExtractor — single API call
│   │   ├── prompts.py          # System prompt for batch extraction
│   │   └── schemas.py          # Pydantic TaskExtraction model
│   ├── database/
│   │   ├── models.py
│   │   └── repository.py
│   ├── excel/
│   │   └── writer.py
│   ├── pipeline/
│   │   └── processor.py        # Orchestrates batch extraction + Excel write
│   ├── static/
│   │   ├── app.js              # UI logic, DB viewer, run/reprocess buttons
│   │   └── style.css
│   ├── templates/
│   │   └── index.html          # Web UI with tabs
│   ├── config.py               # Settings + sender name resolution
│   ├── frontend.py             # FastAPI app with all endpoints
│   └── logger.py
├── data/
│   ├── tasks.db
│   └── tasks.xlsx
├── logs/
├── screenshots/
├── tests/
├── .env
├── .env.example
├── main.py
├── requirements.txt
└── decision.md
```

---

## 8. KNOWN RISKS & MITIGATIONS

| Risk | Mitigation |
|---|---|
| WhatsApp Web DOM changes | Multiple fallback selectors; screenshots on failure |
| QR scan required every run | Persistent browser profile saves session |
| Mistral rate limits | `/api/reprocess` endpoint; messages saved in DB first |
| Phone numbers as sender names | `SENDER_NAME_MAP` in `.env` |
| LLM merges unrelated tasks | Batch prompt explicitly instructs to keep separate tasks separate |
| Wrong group opened | Verify via `conversation-header` before collecting messages |

---

## 9. FUTURE IMPROVEMENTS

- Auto-scroll to load older messages for historical runs
- Multi-group support
- Task status sync with project trackers (Jira, Linear, Notion)
- WhatsApp Business API migration when available
- Scheduled runs via cron/systemd
