# Frontend Controls — Complete List

## 📍 Where Each Control Is

### 1️⃣ **Dashboard Stats Section** (Top)
```
┌─────────────────────────────────────────────────────┐
│  📱 WhatsApp Task Automation                         │
│  Collect, extract & track tasks from WhatsApp groups │
│                              System Status: ✅ Ready  │
│────────────────────────────────────────────────────│
│  📊 Total Tasks    │ 💬 Messages    │ 👥 Group  │ ⏱️ Run    │
│  ┌──────────────┐  │  ┌──────────┐   │ ┌────────┐ │ ┌──────────┐ │
│  │      0       │  │  │    0     │   │ │ Not Set│ │ │  Never   │ │
│  │ No tasks yet │  │  │ No msgs  │   │ │ Set it │ │ │ Run to  │ │
│  └──────────────┘  │  └──────────┘   │ └────────┘ │ └──────────┘ │
│                                                     │
│  Display Only — No interaction (auto-updates)      │
└─────────────────────────────────────────────────────┘
```

### 2️⃣ **Quick Actions Section**
```
┌─────────────────────────────────────────────────────┐
│  [▶️ Run Task Extraction] [🔄 Reprocess] [⬇️ Download] [🔃 Refresh] │
│   (Opens WhatsApp)      (No browser)    (Excel)     (All data)    │
│                                                                     │
│  All are CLICKABLE BUTTONS                                         │
└─────────────────────────────────────────────────────┘
```

### 3️⃣ **Operation Status Section**
```
┌─────────────────────────────────────────────────────┐
│ 📝 Operation Status                             [Clear]│
│┌───────────────────────────────────────────────────┐│
││ ✅ System ready. Configure WhatsApp group and...  ││ ← Messages
││ (text area, scrollable if long)                   ││
│└───────────────────────────────────────────────────┘│
│ Color coded:                                        │
│  • ✅ Green (#86efac) = Success                    │
│  • ❌ Red (#fca5a5) = Error                        │
│  • ⚠️ Yellow (#fde047) = Warning                   │
│  • 📝 Gray (#94a3b8) = Info                        │
└─────────────────────────────────────────────────────┘
```

### 4️⃣ **Configuration Section** (⚙️ Most Important for LLM!)
```
┌─────────────────────────────────────────────────────┐
│ ⚙️ Configuration                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Target WhatsApp Group *                 LLM Provider│
│ [________________] (required)   [Dropdown ▼]        │
│ Name must match exactly               • Mistral Small│
│ e.g., Tenbit Operations              • Mistral Large│
│                                       • OpenRouter: GPT-4│
│                                       • Ollama: Local │
│                                                     │
│ LLM API Key (Optional)        Execution Mode       │
│ [****PASSWORD****]            [Dropdown ▼]         │
│ Leave blank to use .env        • Production (Save)  │
│                                • Test Mode (Dry)    │
│                                                     │
│ [💾 Save Configuration] [🧪 Test Connection]      │
│  (saves to .env)        (verifies API + DB)        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 5️⃣ **Task Viewer Section**
```
┌─────────────────────────────────────────────────────┐
│ 🗄️ Database Viewer                                  │
├─────────────────────────────────────────────────────┤
│ [📋 Tasks] [💬 Messages]  ← Tab buttons            │
│                                                     │
│ [Search by task name...] [🔄 Refresh] [47 tasks] │
│ ┌─ Status Filter: [All Status ▼]                  │
│   • All Status                                     │
│   • ✅ Completed                                   │
│   • 🔄 In Progress                                 │
│   • 📝 Open                                        │
│   • 🚫 Blocked                                     │
│                                                     │
│ ┌────────────────────────────────────────────────┐ │
│ │ Assignee │ Task   │ Status │ Priority │ ... │ │
│ ├────────────────────────────────────────────────┤ │
│ │ Rameen   │ Design │ ✅ Comp│ High    │ ... │ │
│ │ Haris    │ Dev    │ 🔄 IP  │ Medium  │ ... │ │
│ │ Ayan     │ QA     │ 📝 Open│ Low     │ ... │ │
│ └────────────────────────────────────────────────┘ │
│                                                     │
│ Table is READ-ONLY (no editing from UI yet)       │
└─────────────────────────────────────────────────────┘
```

### 6️⃣ **Message Viewer Section**
```
┌─────────────────────────────────────────────────────┐
│ [📋 Tasks] [💬 Messages]  ← Switched to Messages   │
│                                                     │
│ [Search by sender...] [🔄 Refresh] [150 messages] │
│ ┌─ Sender Filter: [All Senders ▼]                 │
│   (populated from DB when opened)                 │
│   • All Senders                                    │
│   • Sir Uzair                                      │
│   • Rameen                                         │
│   • Haris Javed                                    │
│   • Ayan                                           │
│                                                    │
│ ┌────────────────────────────────────────────────┐ │
│ │ Sender  │ Message Text │ Timestamp │ Collected│ │
│ ├────────────────────────────────────────────────┤ │
│ │ Rameen  │ Working on... │ 8:30 AM   │ Sep 12 │ │
│ │ Sir Uz  │ Design done   │ 5:45 PM   │ Sep 12 │ │
│ └────────────────────────────────────────────────┘ │
│                                                     │
│ Table is READ-ONLY (message viewer only)          │
└─────────────────────────────────────────────────────┘
```

### 7️⃣ **Footer**
```
┌─────────────────────────────────────────────────────┐
│ WhatsApp Task Automation System v1.0                │
│ Backend: FastAPI | Database: SQLite | LLM: Mixed    │
│ Last Update: Sep 12, 2026 8:30:45 PM               │
│ Server Time: 8:30:45 PM                            │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 LLM-Related Controls (What We Care About)

### Control 1: **LLM Provider Dropdown**
- **Where:** Configuration Section, top-right
- **Current Options:**
  ```
  • Mistral Small (Fast & Free)
  • Mistral Large (More Accurate)
  • OpenRouter: GPT-4 Turbo
  • Ollama: Local Model
  ```
- **What It Does:** Selects which LLM API to use
- **How It Works:**
  1. User picks provider
  2. Frontend sends to backend via POST /api/config
  3. Backend stores in .env
  4. Next run uses that provider

### Control 2: **LLM API Key Input**
- **Where:** Configuration Section, bottom-left
- **Type:** Password field (hidden input)
- **Default:** Empty (will use .env value if not filled)
- **What It Does:** Allows user to override API key without editing .env
- **How It Works:**
  1. User enters API key
  2. Frontend sends to backend via POST /api/config
  3. Backend stores in .env (or memory)
  4. System uses this key for API calls

### Control 3: **Test Connection Button** ⭐
- **Where:** Configuration Section, bottom-right button
- **What It Does:** Verifies LLM API + Database connectivity
- **How It Works:**
  1. Makes test API call to configured LLM
  2. Checks database connection
  3. Shows: ✅ "Connection successful!" or ❌ "Failed: ..."
  4. User knows if setup is correct before running

### Control 4: **Run Task Extraction Button** ▶️
- **Where:** Quick Actions Section
- **What It Does:** Launches full pipeline
- **Behind the scenes:**
  1. Opens WhatsApp browser
  2. Collects all messages
  3. Sends messages to configured LLM
  4. LLM extracts tasks
  5. Saves to DB + Excel
- **If LLM config is wrong:** Shows error message

### Control 5: **Reprocess from DB Button** 🔄
- **Where:** Quick Actions Section
- **What It Does:** Re-extracts tasks from existing messages
- **Why:** Test new LLM without collecting messages again
- **Behind the scenes:**
  1. Reads all messages from DB
  2. Sends to configured LLM (may be different than original)
  3. Overwrites tasks with new extraction
  4. Updates Excel

---

## 📊 Current LLM Options in Frontend

### What User Sees:
```html
<select id="modelName" name="llm_model">
  <option value="mistral-small-latest">Mistral Small (Fast & Free)</option>
  <option value="mistral-large-latest">Mistral Large (More Accurate)</option>
  <option value="gpt-4-turbo">OpenRouter: GPT-4 Turbo</option>
  <option value="ollama-local">Ollama: Local Model</option>
</select>
```

### How to Add New Option:
1. Edit `app/templates/index.html` (line ~97)
2. Add new `<option>`:
   ```html
   <option value="claude-3-sonnet">Claude 3 Sonnet (via OpenRouter)</option>
   ```
3. Save file
4. Restart server
5. Frontend automatically shows new option ✅

**No backend code changes needed!**

---

## 🔗 Data Flow: Frontend → Backend

### When User Changes LLM:

```
Frontend (UI)
    ↓
User selects: "Claude 3 Sonnet"
    ↓
User enters: API key "sk-..."
    ↓
User clicks: [💾 Save Configuration]
    ↓
JavaScript event: configForm.submit()
    ↓
POST /api/config with FormData:
  {
    "whatsapp_group_name": "Tenbit Operations",
    "llm_api_key": "sk-...",
    "llm_model": "claude-3-sonnet",
    "dry_run": "false"
  }
    ↓
Backend (FastAPI)
    ↓
app/frontend.py: save_config() endpoint
    ↓
Stores in: app/config.py → environment variables
    ↓
Next time system runs:
  → Reads: LLM_MODEL="claude-3-sonnet"
  → Looks up: OpenRouter for Claude
  → Uses: openrouter_api_key + openrouter_model
    ↓
Frontend: Shows ✅ "Configuration saved!"
    ↓
User clicks: [▶️ Run Task Extraction]
    ↓
System uses Claude for extraction! ✅
```

---

## 🎬 Complete User Journey

### Scenario: User wants to try Claude 3

```
1. User opens: http://localhost:8000/

2. Sees Configuration Panel

3. Clicks LLM Provider dropdown
   Sees options:
   • Mistral Small
   • Mistral Large
   • OpenRouter: GPT-4 Turbo
   • Ollama: Local Model
   
4. Admin adds Claude option (edit HTML)
   
5. User refreshes page
   Now sees:
   • ...previous options...
   • Claude 3 Sonnet (via OpenRouter) ← NEW

6. User selects Claude 3 Sonnet

7. User enters API key: "sk-or-v1-..."

8. User clicks [💾 Save Configuration]

9. System shows: ✅ "Configuration saved!"

10. User clicks [🧪 Test Connection]
    Shows: ✅ "Connection successful!"

11. User clicks [▶️ Run Task Extraction]

12. System:
    • Opens WhatsApp
    • Collects messages
    • Sends to Claude 3 (via OpenRouter)
    • Claude extracts tasks
    • Saves to DB
    • Updates Excel

13. User sees: ✅ "47 tasks extracted!"

14. User clicks [📋 Tasks] tab

15. Views all tasks extracted by Claude ✅
```

---

## ✅ Summary

### Frontend Controls (User Perspective):
| Control | Purpose | Impact |
|---------|---------|--------|
| **LLM Provider Dropdown** | Choose which AI to use | Changes API endpoint |
| **API Key Input** | Enter authentication | Enables API calls |
| **Test Connection** | Verify setup | Confirms all working |
| **Run Button** | Start pipeline | Collects + extracts |
| **Reprocess Button** | Use new LLM on old data | Tests without recollecting |
| **Search/Filter** | Find tasks/messages | View only (no edit) |

### What's Auto-Handled:
✅ LLM API routing
✅ Error messages
✅ Status updates
✅ Task extraction
✅ Database updates
✅ Excel generation

### What User Controls:
✅ Which LLM to use
✅ API key management
✅ Execution mode (test/prod)
✅ WhatsApp group name
✅ Running the pipeline

**System is flexible & user-friendly!** 🚀
