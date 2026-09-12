# System Architecture Diagrams

## 🏗️ Current Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     WhatsApp Task Automation                    │
└────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND LAYER                                  │
│  (HTML + CSS + JavaScript)                                              │
│                                                                         │
│  ┌─────────────────────┐  ┌──────────────────┐  ┌───────────────────┐ │
│  │  Dashboard Panel    │  │  Configuration   │  │  Database Viewer  │ │
│  │                     │  │  - LLM Provider  │  │  - Tasks Table    │ │
│  │  - Total Tasks      │  │  - API Key       │  │  - Messages Table │ │
│  │  - Total Messages   │  │  - Group Name    │  │  - Search/Filter  │ │
│  │  - Active Group     │  │  - Exec Mode     │  └───────────────────┘ │
│  │  - Last Run         │  │  - [Save] [Test] │                        │
│  └─────────────────────┘  └──────────────────┘                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │              Quick Actions                                        │ │
│  │  [▶ Run] [🔄 Reprocess] [⬇ Download] [🔃 Refresh]              │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                   ↕
                            FastAPI Backend
                          (REST API Endpoints)
                                   ↕
┌─────────────────────────────────────────────────────────────────────────┐
│                        BACKEND LAYER                                     │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Frontend Controller (app/frontend.py)                         │   │
│  │  - GET /api/config                                             │   │
│  │  - POST /api/config                                            │   │
│  │  - POST /api/run                                               │   │
│  │  - POST /api/reprocess                                         │   │
│  │  - GET /api/db/tasks                                           │   │
│  │  - GET /api/db/messages                                        │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                   ↕                                     │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Pipeline Processor (app/pipeline/processor.py)                │   │
│  │  - extract_tasks()     ← Gets tasks from DB                   │   │
│  │  - write_excel()       ← Generates XLSX                       │   │
│  │  - run()               ← Orchestrates full pipeline            │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                        ↙                    ↖                          │
│       ┌─────────────────────┐        ┌──────────────────┐             │
│       │   LLM Processing    │        │  Excel Writer    │             │
│       │                     │        │                  │             │
│       │  - NVIDIA NIM       │        │  - Format data   │             │
│       │  - OpenRouter       │        │  - Style cells   │             │
│       │  - OpenAI           │        │  - Create XLSX   │             │
│       │  - Mistral          │        │  - Save file     │             │
│       │  - Ollama           │        │  - Colors/Fonts  │             │
│       │                     │        │  - Headers       │             │
│       │  → Extracts tasks   │        │                  │             │
│       │    from messages    │        │  Output:         │             │
│       └─────────────────────┘        │  /data/          │             │
│                ↕                      │  tasks.xlsx      │             │
│       ┌─────────────────────┐        │                  │             │
│       │  Database Layer     │        └──────────────────┘             │
│       │                     │                                         │
│       │  SQLite3            │                                         │
│       │  - messages table   │                                         │
│       │  - tasks table      │                                         │
│       │  - runs table       │                                         │
│       │                     │                                         │
│       │  File: /data/       │                                         │
│       │  tasks.db           │                                         │
│       └─────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   ↕
┌─────────────────────────────────────────────────────────────────────────┐
│                  EXTERNAL INTEGRATIONS LAYER                            │
│                                                                         │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────┐   │
│  │  WhatsApp Web  │  │  LLM APIs       │  │  File System         │   │
│  │                │  │                 │  │                      │   │
│  │ - Browser      │  │  - NVIDIA       │  │ - Excel files        │   │
│  │ - Playwright   │  │  - OpenRouter   │  │ - Config files       │   │
│  │ - Screenshots  │  │  - OpenAI       │  │ - Database files     │   │
│  │ - QR Scanning  │  │  - Mistral      │  │ - Log files          │   │
│  │ - Message Coll │  │  - Ollama       │  │                      │   │
│  └────────────────┘  └─────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Current Data Flow (Complete)

```
START
  ↓
User opens UI: http://localhost:8000/
  ↓
Frontend loads
  ├─ GET /api/config       → Shows current settings
  ├─ GET /api/db/tasks     → Shows existing tasks
  └─ GET /api/db/messages  → Shows existing messages
  ↓
User configures:
  ├─ WhatsApp Group Name
  ├─ LLM Provider
  ├─ LLM API Key
  └─ Execution Mode
  ↓
POST /api/config → Backend saves to .env
  ↓
User clicks [▶ Run Task Extraction]
  ↓
POST /api/run
  ├─ WhatsAppBrowser.open()
  │   ├─ Launch Playwright browser
  │   ├─ Navigate to WhatsApp Web
  │   ├─ Wait for QR scan
  │   └─ Authenticate
  │
  ├─ GroupFinder.run()
  │   ├─ Search for configured group
  │   └─ Open group chat
  │
  ├─ MessageCollector.collect()
  │   ├─ Scroll up to find messages
  │   ├─ Extract: sender, text, timestamp
  │   ├─ Parse message format
  │   ├─ Normalize text
  │   └─ Save to DB (messages table)
  │
  ├─ LLMTaskExtractor.extract_batch()
  │   ├─ Read config → LLM_PROVIDER
  │   ├─ Route to correct extractor:
  │   │   ├─ NVIDIA → NvidiaBatchExtractor
  │   │   ├─ OpenRouter → OpenRouterBatchExtractor
  │   │   ├─ OpenAI → NvidiaBatchExtractor (compatible)
  │   │   ├─ Mistral → MistralBatchExtractor
  │   │   └─ Ollama → OllamaBatchExtractor
  │   │
  │   ├─ Build prompt with messages:
  │   │   "Extract tasks from these WhatsApp messages:
  │   │    Date: 12 Sep 2026
  │   │    [8:30 AM] Rameen: Design UI mockups
  │   │    [9:15 AM] Sir Uzair: Approved, please proceed
  │   │    ..."
  │   │
  │   ├─ Call LLM API with:
  │   │   ├─ system_prompt: Task extraction instructions
  │   │   ├─ user_message: Formatted messages
  │   │   └─ temperature: 0.1 (deterministic)
  │   │
  │   ├─ LLM returns:
  │   │   [
  │   │     {
  │   │       "task": "Design UI mockups",
  │   │       "assignee": "Rameen",
  │   │       "status": "in_progress",
  │   │       "priority": "high",
  │   │       "deadline": null,
  │   │       "confidence": 0.95
  │   │     },
  │   │     { ... more tasks ... }
  │   │   ]
  │   │
  │   ├─ Parse JSON response
  │   ├─ Validate fields
  │   └─ Return list[TaskExtraction]
  │
  ├─ TaskProcessor.extract_tasks()
  │   ├─ Create task fingerprints: (task + assignee + date)
  │   ├─ Check for duplicates
  │   └─ Prepare records for DB
  │
  ├─ Database upsert
  │   ├─ INSERT OR REPLACE INTO tasks VALUES (...)
  │   │   (same fingerprint = update, new = insert)
  │   └─ Save: task_key, task, assignee, status, date, etc.
  │
  ├─ ExcelWriter.write_tasks()
  │   ├─ SELECT * FROM tasks (all records)
  │   ├─ Group by: date → assignee
  │   ├─ Format layout:
  │   │   ┌─────────────────────────────┐
  │   │   │ TenBit Daily Task Report    │
  │   │   ├──────┬──────────┬──────────┤
  │   │   │ Date │ Rameen   │ Ayan     │
  │   │   │      │Tasks|Sts │Tasks|Sts │
  │   │   ├──────┼──────┼──┼──────┼──┤
  │   │   │Sep12 │•UI   │✅│•Tst  │📋│
  │   │   │      │•PR   │🔄│      │  │
  │   │   └──────┴──────┴──┴──────┴──┘
  │   │
  │   ├─ Apply styling:
  │   │   ├─ Colors by status
  │   │   ├─ Fonts (bold, size)
  │   │   ├─ Borders
  │   │   ├─ Text wrapping
  │   │   └─ Row heights
  │   │
  │   └─ Save to: /data/tasks.xlsx
  │
  └─ Browser.close()
  ↓
Frontend displays:
  ✅ "47 tasks extracted!"
  ✅ "Excel updated"
  
User clicks [📋 Tasks] tab
  ↓
GET /api/db/tasks
  └─ Returns all tasks for table display
  ↓
User clicks [⬇ Download Excel]
  ↓
Browser downloads: /data/tasks.xlsx
  ↓
END
```

---

## 🚀 New Architecture: WITH Google Sheets

```
Current:
  LLM → DB → ExcelWriter → XLSX

New (Google Sheets added):
  LLM → DB ├→ ExcelWriter → XLSX
           └→ GoogleSheetsWriter → Google Sheets ☁️


┌──────────────────────────────────────────────────────────────────────────┐
│                    With Google Sheets Integration                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Configuration Panel (Enhanced)                                    │ │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐│ │
│  │  │ LLM Settings │  │ Excel Settings   │  │ Google Sheets Config││ │
│  │  │ - Provider   │  │ - Output path    │  │ - Enable/Disable    ││ │
│  │  │ - API Key    │  │ - Auto-generate  │  │ - Spreadsheet ID    ││ │
│  │  │ - Model      │  │                  │  │ - Credentials JSON  ││ │
│  │  │              │  │                  │  │ - Share with emails ││ │
│  │  │              │  │                  │  │ - [Test] [Save]     ││ │
│  │  └──────────────┘  └──────────────────┘  └──────────────────────┘│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  New Endpoints                                                     │ │
│  │  - POST /api/google-sheets/config                                 │ │
│  │  - GET /api/google-sheets/config                                  │ │
│  │  - POST /api/google-sheets/test                                   │ │
│  │  - POST /api/google-sheets/sync (manual)                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Pipeline Processor (Modified)                                    │ │
│  │                                                                   │ │
│  │  def run():                                                       │ │
│  │    tasks = extract_tasks()  ← LLM extracts                       │ │
│  │    write_excel(tasks)       ← Local XLSX                         │ │
│  │    ┌──────────────────────────────────────────────────────────┐  │ │
│  │    │ if google_sheets_enabled:                                │  │ │
│  │    │   write_google_sheets(tasks)  ← NEW!                    │  │ │
│  │    │   - Format data                                          │  │ │
│  │    │   - Connect to Google Sheets API                         │  │ │
│  │    │   - Update sheet with latest tasks                       │  │ │
│  │    │   - Share with team (auto)                               │  │ │
│  │    └──────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                           │
│           ┌─────────────────────────────────────────┐                  │
│           │   GoogleSheetsWriter (NEW)              │                  │
│           │                                         │                  │
│           │  ├─ Authenticate (OAuth)                │                  │
│           │  ├─ Build request to Sheets API         │                  │
│           │  ├─ Format cells/colors/fonts           │                  │
│           │  ├─ Insert data into sheet              │                  │
│           │  ├─ Create ranges (headers, data)       │                  │
│           │  └─ Share sheet with team               │                  │
│           │                                         │                  │
│           │  Output: Google Sheet URL               │                  │
│           │  Shared with: rameen@, haris@, ...      │                  │
│           └─────────────────────────────────────────┘                  │
│                              ↓                                           │
│           ┌─────────────────────────────────────────┐                  │
│           │   Google Sheets Cloud                   │                  │
│           │                                         │                  │
│           │  Spreadsheet: TenBit Task Report        │                  │
│           │  ┌──────────────────────────────────┐  │                  │
│           │  │ Date | Rameen (T|S) | Ayan (T|S)│  │                  │
│           │  ├──────┼────────┼──┼────────┼───┤  │                  │
│           │  │ 12S  │ •UI ✅ │  │ •Test 📋│   │  │                  │
│           │  │      │ •PR 🔄 │  │        │   │  │                  │
│           │  └──────┴────────┴──┴────────┴───┘  │                  │
│           │                                         │                  │
│           │  Real-time updates                     │                  │
│           │  Accessible from anywhere              │                  │
│           │  Shared with team                      │                  │
│           │  Version history (auto)                │                  │
│           └─────────────────────────────────────────┘                  │
│                                                                         │
│  Frontend shows:                                                        │
│  ✅ Excel updated: /data/tasks.xlsx                                    │
│  ✅ Google Sheets synced: https://docs.google.com/spreadsheets/...    │
│  ✅ Shared with: rameen@, haris@, ...                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow: LLM → Excel + Google Sheets

```
Messages from WhatsApp
    ↓
    ↓
LLM Processing (extract_batch)
    ↓
    ├─ NVIDIA NIM      → API call → Tasks
    ├─ OpenRouter      → API call → Tasks
    ├─ OpenAI          → API call → Tasks
    ├─ Mistral         → API call → Tasks
    └─ Ollama (local)  → Local    → Tasks
    ↓
    ├─ Validate
    └─ Return list[TaskExtraction]
    ↓
Database Layer
    ├─ Upsert to tasks table
    └─ Fingerprint: (task + assignee + date)
    ↓
    ├─────────────────────┬─────────────────────┐
    ↓                     ↓                     ↓
ExcelWriter        GoogleSheetsWriter      Frontend API
    ↓                     ↓                     ↓
┌─────────────┐  ┌──────────────────┐  ┌─────────────┐
│ /data/      │  │ Google Sheets    │  │ REST API    │
│ tasks.xlsx  │  │ - Auth (OAuth)   │  │ - /api/... │
│             │  │ - Write cells    │  │             │
│ Local file  │  │ - Format data    │  │ JSON data   │
│             │  │ - Share link     │  │             │
│ Download    │  │                  │  │ Real-time   │
│ via UI      │  │ Cloud sheet      │  │ dashboard   │
└─────────────┘  │ Shared with team │  └─────────────┘
                 └──────────────────┘
```

---

## 🎯 Component Responsibilities

### **Frontend (HTML/CSS/JS)**
- User interface
- Configuration forms
- Status display
- Data visualization (tables)
- Download triggers

### **Backend API (FastAPI)**
- Route requests
- Config management
- Database queries
- File operations
- Error handling

### **LLM Processing**
- Message parsing
- Task extraction
- Confidence scoring
- Status determination
- Priority assignment

### **Database (SQLite)**
- Store messages
- Store tasks
- Store runs
- Track processing
- Upsert logic (avoid duplicates)

### **Excel Writer**
- Format layout
- Apply styling
- Color-code status
- Generate XLSX file
- Save locally

### **Google Sheets Writer** (NEW)
- Authenticate with OAuth
- Connect to Sheets API
- Format layout (same as Excel)
- Write data to cloud
- Share with team
- Handle errors

### **Google Sheets Controller** (NEW)
- Manage authentication
- Create spreadsheets
- Update permissions
- Handle API errors
- Provide fallback

---

## 🔐 Security Considerations

```
Frontend (Browser)
    ↓ (HTTPS)
FastAPI Backend (Trusted)
    ├─ Store API keys securely (.env, not in code)
    ├─ Validate all inputs
    ├─ Rate limiting
    └─ Error messages (don't expose internals)
    ↓
External APIs
    ├─ LLM APIs (via configured API keys)
    ├─ Google Sheets API (via OAuth 2.0)
    └─ WhatsApp Web (via Playwright)
    ↓
Database (Local SQLite)
    └─ No encryption (local file)
```

---

## 📈 Scalability

### Current Setup (Single Machine):
- ✅ Works for small teams
- ✅ All on one machine
- ✅ No distributed processing
- ✅ Manual run trigger

### Future Improvements:
- [ ] Scheduled runs (cron/scheduler)
- [ ] Multiple machines (Kubernetes)
- [ ] Message queue (Redis/RabbitMQ)
- [ ] Background jobs (Celery)
- [ ] WebSocket (real-time updates)
- [ ] Database replication (PostgreSQL)

---

## ✅ Summary

**Current:** WhatsApp → LLM → SQLite DB → Excel (.xlsx)

**With Google Sheets:** WhatsApp → LLM → SQLite DB → Excel + Google Sheets ☁️

All components are **loosely coupled** — can swap any layer (LLM provider, export format, etc.) without affecting others.
