# Excel & Google Sheets Integration Guide

## 📊 Current Excel Implementation

### How It Works:

```
LLM extracts tasks
    ↓
TaskProcessor.extract_tasks()
    ↓
Creates dict: {
    "2026-09-12": {
        "Rameen": {"tasks": ["Design UI", "Review PR"], "statuses": ["completed", "in_progress"]},
        "Ayan": {"tasks": ["Write tests"], "statuses": ["open"]}
    },
    "2026-09-11": { ... }
}
    ↓
ExcelWriter.write_tasks(rows)
    ↓
Generates XLSX with layout:
    ┌─────────────────────────────────────────┐
    │    TenBit Daily Task Report             │ (Row 1 - Title)
    ├─────────┬──────────────┬──────────────┤
    │  Date   │  Rameen      │   Ayan       │ (Row 2 - Employee names)
    │         ├──────┬───────┼──────┬───────┤
    │         │Tasks │Status │Tasks │Status │ (Row 3 - Sub-headers)
    ├─────────┼──────┼───────┼──────┼───────┤
    │ 12 Sep  │ • UI │ ✅    │ • .. │ 📋    │ (Row 4+ - Data)
    │         │ • PR │ 🔄    │      │       │
    │ 11 Sep  │ ...  │ ...   │ ...  │ ...   │
    └─────────┴──────┴───────┴──────┴───────┘
    
    File: /data/tasks.xlsx
```

### Excel Features:

✅ **Layout:**
- Date column (frozen)
- Employee columns (2 sub-columns each: Tasks + Status)
- Automatically sized
- Frozen headers for scrolling

✅ **Formatting:**
- Color-coded status (green=done, amber=in-progress, blue=open, red=blocked)
- Emoji status labels (✅ 🔄 📋 🚫 🔍)
- Alternating row colors
- Border styling
- Text wrapping

✅ **Data Logic:**
- Group tasks by date + assignee
- Handle multi-line tasks (wrap text)
- Auto-detect dominant status if multiple statuses
- Create new file if not exists
- Update existing file on next run

### File Location:
```
/home/tenbitsolutions/task_reporting_wa_automation/data/tasks.xlsx
```

### Update Trigger:
```
Every time "Run Task Extraction" completes:
    TaskProcessor.run()
        ↓
    extract_tasks()  ← Get tasks from LLM
        ↓
    write_excel(tasks)  ← Update XLSX
        ↓
    File saved automatically
```

---

## 🔄 Data Flow: LLM → Excel

### Step-by-Step:

```
1. User clicks "Run Task Extraction"
   ↓
2. System opens WhatsApp browser
   ↓
3. Collects messages from group
   ↓
4. Sends to LLM (Mistral, Claude, etc.)
   ↓
5. LLM returns:
   [
     {
       "task": "Design UI mockups",
       "assignee": "Rameen",
       "deadline": "2026-09-12",
       "priority": "high",
       "status": "in_progress",
       "sender": "Sir Uzair",
       "timestamp": "2026-09-12 8:30 AM"
     },
     {
       "task": "Write unit tests",
       "assignee": "Ayan",
       "status": "open",
       ...
     },
     ...
   ]
   ↓
6. TaskProcessor creates DB records:
   INSERT INTO tasks VALUES (...)
   ↓
7. ExcelWriter reads ALL tasks from DB:
   SELECT * FROM tasks
   ↓
8. Groups by date + assignee:
   2026-09-12:
     Rameen: ["Design UI", "Review PR"]
     Ayan: ["Write tests"]
   2026-09-11:
     Rameen: ["Deploy"]
     ...
   ↓
9. Generates XLSX with layout above
   ↓
10. File saved to: /data/tasks.xlsx
   ↓
11. User clicks: [⬇️ Download Excel]
    → Browser downloads tasks.xlsx
```

### What Each Part Does:

| Component | What It Does | Where |
|-----------|------------|-------|
| **LLM** | Extracts tasks from messages | `app/ai/mistral_client.py` |
| **TaskProcessor** | Processes tasks, saves to DB | `app/pipeline/processor.py` |
| **ExcelWriter** | Reads DB, formats, writes XLSX | `app/excel/writer.py` |
| **Database** | Stores all tasks with metadata | `data/tasks.db` (SQLite) |
| **Frontend** | Shows download link, displays tasks | `app/templates/index.html` |

---

## 🔌 Google Sheets Integration (NEW)

### Architecture Needed:

```
Current:                      New:
LLM                          LLM
  ↓                            ↓
TaskProcessor         TaskProcessor
  ↓                            ↓
DB                           DB
  ├─→ ExcelWriter ─→ XLSX    ├─→ ExcelWriter ─→ XLSX
  │                          └─→ GoogleSheetsWriter ─→ Google Sheets API
  └─→ Frontend
```

### Components Needed:

#### 1. **Google Sheets Controller** (NEW)
```python
# File: app/google_sheets/controller.py

class GoogleSheetsController:
    """
    Handles all Google Sheets operations:
    - Authentication (OAuth 2.0)
    - Create spreadsheet
    - Write tasks
    - Update existing sheet
    - Share with team
    """
    
    def __init__(self, config):
        # Load credentials
        # Initialize Google Sheets API client
        # Set up authentication
        pass
    
    def write_tasks(self, tasks: list[dict]):
        """
        Same as ExcelWriter but writes to Google Sheets instead of XLSX
        """
        pass
    
    def create_spreadsheet(self, title: str) -> str:
        """
        Create new Google Sheet and return spreadsheet ID
        """
        pass
    
    def share_with_team(self, sheet_id: str, emails: list[str]):
        """
        Share sheet with team members
        """
        pass
    
    def update_existing_sheet(self, sheet_id: str, tasks: list[dict]):
        """
        Update already existing sheet with new data
        """
        pass
```

#### 2. **Google Sheets Writer** (NEW)
```python
# File: app/excel/google_sheets_writer.py

class GoogleSheetsWriter:
    """
    Same interface as ExcelWriter but writes to Google Sheets
    """
    
    def __init__(self, sheet_id: str, credentials_path: str):
        self.sheet_id = sheet_id
        self.service = build('sheets', 'v4', credentials=credentials)
    
    def write_tasks(self, rows: list[dict]):
        """
        Write tasks to Google Sheet
        - Create headers
        - Format like Excel version
        - Handle colors, formatting
        """
        pass
```

#### 3. **Google Sheets Config** (NEW)
```python
# In app/config.py - add these:

class Settings:
    # Google Sheets
    self.google_sheets_enabled = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
    self.google_sheets_id = os.getenv("GOOGLE_SHEETS_ID", "")  # Spreadsheet ID
    self.google_sheets_credentials = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")  # Path to JSON
    self.google_sheets_share_with = os.getenv("GOOGLE_SHEETS_SHARE_WITH", "").split(",")
    self.google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")  # Org folder
```

#### 4. **Frontend Configuration Panel Addition** (NEW)
```html
<!-- Add to app/templates/index.html -->

<div class="card">
  <h2 class="section-title">🔗 Google Sheets Integration</h2>
  <form id="googleSheetsForm">
    <div class="form-row">
      <div class="form-group">
        <label>Enable Google Sheets?</label>
        <input type="checkbox" id="googleSheetsEnabled" name="google_sheets_enabled" />
        <small>Enable to sync tasks to Google Sheets</small>
      </div>
      <div class="form-group">
        <label>Spreadsheet ID</label>
        <input id="sheetsId" name="google_sheets_id" placeholder="Paste spreadsheet ID here" />
        <small>Find in Google Sheets URL</small>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>Credentials JSON File Path</label>
        <input id="credsPath" name="google_sheets_credentials" placeholder="/path/to/credentials.json" />
        <small>OAuth 2.0 credentials from Google Cloud</small>
      </div>
      <div class="form-group">
        <label>Share With (Email addresses)</label>
        <input id="shareWith" name="google_sheets_share_with" placeholder="user@example.com, team@example.com" />
        <small>Comma-separated emails</small>
      </div>
    </div>
    <button type="submit" class="btn-primary">💾 Save Google Sheets Config</button>
    <button type="button" id="testGoogleBtn" class="btn-secondary">🧪 Test Connection</button>
  </form>
</div>
```

#### 5. **Backend API Endpoints** (NEW)
```python
# In app/frontend.py - add these:

@app.post("/api/google-sheets/config")
async def save_google_sheets_config(request: dict):
    """
    Save Google Sheets configuration
    {
        "google_sheets_enabled": true,
        "google_sheets_id": "1abc123...",
        "google_sheets_credentials": "/path/to/creds.json",
        "google_sheets_share_with": "user@example.com"
    }
    """
    pass

@app.get("/api/google-sheets/config")
async def get_google_sheets_config():
    """
    Return current Google Sheets configuration
    """
    pass

@app.post("/api/google-sheets/test")
async def test_google_sheets_connection():
    """
    Test Google Sheets API connection
    Returns: {"status": "ok", "sheet_url": "..."} or error
    """
    pass

@app.post("/api/google-sheets/sync")
async def sync_to_google_sheets():
    """
    Manually sync current tasks to Google Sheets
    """
    pass
```

#### 6. **Update Processor** (MODIFY)
```python
# In app/pipeline/processor.py - modify run():

def run(self) -> list[dict]:
    init_db()
    run_id = str(uuid.uuid4())
    started_at = datetime.utcnow().isoformat(timespec="seconds")
    record_run(run_id, self.cfg.whatsapp_group_name, started_at, "running")
    
    tasks = self.extract_tasks()
    
    # Current: Write to Excel
    self.write_excel(tasks)
    
    # NEW: Also write to Google Sheets if enabled
    if self.cfg.google_sheets_enabled:
        self.write_google_sheets(tasks)  # NEW METHOD
    
    finalize_run(...)
    return tasks

def write_google_sheets(self, tasks: list[dict]) -> None:
    """NEW: Write tasks to Google Sheets"""
    if not self.cfg.google_sheets_id:
        logger.warning("Google Sheets disabled — no sheet ID")
        return
    
    from app.excel.google_sheets_writer import GoogleSheetsWriter
    writer = GoogleSheetsWriter(
        sheet_id=self.cfg.google_sheets_id,
        credentials_path=self.cfg.google_sheets_credentials
    )
    writer.write_tasks(tasks)
    logger.info("Tasks synced to Google Sheets")
```

---

## 🚀 How to Set Up Google Sheets

### Prerequisites:
1. Google Cloud Project
2. Google Sheets API enabled
3. OAuth 2.0 credentials (JSON file)
4. Google Sheets spreadsheet created

### Step-by-Step Setup:

#### **Step 1: Create Google Cloud Project**
```
1. Go to: https://console.cloud.google.com/
2. Create new project: "WhatsApp Task Automation"
3. Enable APIs:
   - Google Sheets API
   - Google Drive API
```

#### **Step 2: Create OAuth 2.0 Credentials**
```
1. Go to: Credentials → Create Credentials → OAuth 2.0 Client ID
2. Type: Desktop application (or Web)
3. Download JSON file → Save as: credentials.json
4. Move to: /home/tenbitsolutions/task_reporting_wa_automation/credentials.json
```

#### **Step 3: Create Google Sheet**
```
1. Go to: https://sheets.google.com/
2. Create new spreadsheet: "TenBit Task Report"
3. Copy the Spreadsheet ID from URL:
   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
4. Save: GOOGLE_SHEETS_ID=1abc123...
```

#### **Step 4: Update .env**
```bash
# Google Sheets
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_ID=1abc123...xyz
GOOGLE_SHEETS_CREDENTIALS=/home/tenbitsolutions/task_reporting_wa_automation/credentials.json
GOOGLE_SHEETS_SHARE_WITH=rameen@tenbit.com,haris@tenbit.com
```

#### **Step 5: Install Dependencies**
```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

#### **Step 6: Test Connection**
```
1. Open UI: http://localhost:8000/
2. Go to: Google Sheets Integration section
3. Click: [🧪 Test Connection]
4. Should show: ✅ "Connected successfully!"
```

#### **Step 7: Run Extraction**
```
1. Click: [▶️ Run Task Extraction]
2. System will:
   - Extract tasks from WhatsApp
   - Write to Excel (/data/tasks.xlsx)
   - Write to Google Sheets (real-time!)
   - Show: ✅ "Synced to Google Sheets"
```

---

## 📋 Data Sync Flow

```
WhatsApp Messages
    ↓
LLM Processing
    ↓
TaskProcessor
    ├─ Save to SQLite DB
    ├─ write_excel(tasks)
    │   └─ /data/tasks.xlsx (local file)
    └─ write_google_sheets(tasks)
        └─ Google Sheets (cloud)
            └─ Shared with team (auto-share)
    ↓
Frontend shows:
  ✅ Tasks extracted: 47
  ✅ Excel updated: /data/tasks.xlsx
  ✅ Google Sheet synced: [Link]
```

---

## 🎯 What Each Component Does

### **ExcelWriter** (Current)
- ✅ Reads tasks from DB
- ✅ Formats for Excel
- ✅ Creates XLSX file locally
- ✅ Static format: Date | Employee (Tasks + Status)
- ✅ Downloads via [⬇️ Download Excel]

### **GoogleSheetsWriter** (New)
- ✅ Reads tasks from DB
- ✅ Same layout as Excel
- ✅ Writes to cloud (Google Sheets)
- ✅ Real-time updates
- ✅ Auto-share with team
- ✅ Link provided to team
- ✅ Everyone sees latest immediately

### **GoogleSheetsController** (New)
- ✅ Authentication (OAuth)
- ✅ Create/update sheets
- ✅ Share permissions
- ✅ Error handling
- ✅ Fallback if API down

---

## 🔧 Implementation Checklist

### Phase 1: Google Sheets Writer (Core)
- [ ] Create `app/excel/google_sheets_writer.py`
- [ ] Implement write_tasks() method
- [ ] Match Excel layout
- [ ] Handle colors/formatting
- [ ] Error handling

### Phase 2: Google Sheets Controller
- [ ] Create `app/google_sheets/controller.py`
- [ ] OAuth authentication
- [ ] Create spreadsheet method
- [ ] Update existing sheet
- [ ] Share with team

### Phase 3: Configuration
- [ ] Add to `app/config.py`
- [ ] Add env variables
- [ ] Create config endpoints
- [ ] Add to frontend form

### Phase 4: Integration
- [ ] Update `app/pipeline/processor.py`
- [ ] Call write_google_sheets()
- [ ] Add test endpoint
- [ ] Add sync button

### Phase 5: Frontend
- [ ] Add Google Sheets section to UI
- [ ] Add configuration form
- [ ] Add test button
- [ ] Show sync status
- [ ] Display sheet link

### Phase 6: Testing
- [ ] Test OAuth flow
- [ ] Test write operations
- [ ] Test sharing
- [ ] Test error handling
- [ ] Test auto-sync

---

## 📊 Comparison: Excel vs Google Sheets

| Feature | Excel | Google Sheets |
|---------|-------|---------------|
| **Storage** | Local file | Cloud (Google Drive) |
| **Access** | Download file | Anyone with link |
| **Real-time** | ❌ Manual refresh | ✅ Live updates |
| **Collaboration** | ❌ One person at a time | ✅ Multiple users |
| **Version Control** | ❌ Manual | ✅ Auto history |
| **Mobile** | ❌ Need app | ✅ Instant view |
| **Sharing** | ❌ Email file | ✅ Link sharing |
| **Updates** | Separate downloads | ✅ Always current |

---

## 🎬 User Journey: Excel → Google Sheets

### Current (Excel Only):
```
1. Run extraction
2. System updates Excel file
3. User: [⬇️ Download Excel]
4. User sends file to team via email
5. Team imports to Google Sheets manually
6. Process repeats → conflicts, versions
```

### New (With Google Sheets):
```
1. Run extraction
2. System updates Excel file
3. System ALSO updates Google Sheet (auto!)
4. Team members see updated sheet instantly
5. Everyone on same page, no conflicts
```

---

## ✅ Summary

### Current Implementation:
- LLM extracts tasks
- Processor saves to DB
- ExcelWriter creates XLSX
- User downloads file

### With Google Sheets:
- LLM extracts tasks (same)
- Processor saves to DB (same)
- ExcelWriter creates XLSX (same)
- GoogleSheetsWriter creates Google Sheet (NEW!)
- Team sees updates in real-time (NEW!)
- Auto-shared with team (NEW!)

**Everything is additive — no breaking changes!** ✅

---

## 🚀 Next Steps

1. Read this guide
2. Implement GoogleSheetsWriter
3. Implement GoogleSheetsController
4. Update config & processor
5. Add frontend UI
6. Get Google credentials
7. Test & deploy

**System will be fully cloud-enabled!** ☁️
