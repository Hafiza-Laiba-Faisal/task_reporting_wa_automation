# LLM Integration Guide — Complete

## 🎯 Current Architecture

Your system is **OpenAI-compatible** and supports multiple LLM providers without code changes!

### Supported Providers (Out of Box)
- ✅ **NVIDIA NIM** (OpenAI-compatible) — FREE, best performance
- ✅ **OpenRouter** (OpenAI-compatible) — FREE models available
- ✅ **OpenAI** (GPT-4, GPT-4o-mini) — Paid
- ✅ **Mistral** (Direct API) — Free tier available
- ✅ **Ollama** (Local/Offline) — FREE, fully offline

---

## 📊 How It Works

```
Frontend (HTML) — LLM Config Panel
        ↓
User selects: LLM Provider + API Key + Model
        ↓
POST /api/config
        ↓
Backend (config.py)
    Stores: llm_provider="nvidia" or "openrouter" or "ollama"
            llm_model="mistral-large" or "nemotron-3-super-120b"
            [provider]_api_key="sk-..." or similar
        ↓
User clicks: "Run Task Extraction"
        ↓
POST /api/run
        ↓
Backend (extractor.py)
    if llm_provider == "nvidia":
        → NvidiaBatchExtractor(config) → uses nvidia_api_key + nvidia_base_url
    elif llm_provider == "openrouter":
        → OpenRouterBatchExtractor(config) → uses openrouter_api_key + openrouter_base_url
    elif llm_provider == "ollama":
        → OllamaBatchExtractor(config) → uses ollama_base_url (no API key)
    ...etc
        ↓
All use same interface: extract_all(messages) → list[TaskExtraction]
        ↓
Tasks saved to DB + Excel file
        ↓
Frontend: ✅ Done!
```

---

## 🎛️ Frontend Controls (What User Sees)

### Configuration Panel has:

| Control | Type | Currently Supports |
|---------|------|-------------------|
| **WhatsApp Group** | Text Input | Any WhatsApp group name |
| **LLM Provider** | Dropdown | See next section |
| **Model** | Dropdown | Depends on provider |
| **API Key** | Password Input | Optional (uses .env if empty) |
| **Execution Mode** | Dropdown | Test or Production |

### Current Dropdown Options (in HTML):
```html
<option value="mistral-small-latest">Mistral Small (Fast & Free)</option>
<option value="mistral-large-latest">Mistral Large (More Accurate)</option>
<option value="gpt-4-turbo">OpenRouter: GPT-4 Turbo</option>
<option value="ollama-local">Ollama: Local Model</option>
```

---

## ➕ How to Add New LLM Provider

### Example: Adding Claude 3 (via OpenRouter)

#### **Step 1: Update Frontend HTML**
File: `app/templates/index.html` (line ~97)

**Current:**
```html
<select id="modelName" name="llm_model">
  <option value="mistral-small-latest">Mistral Small (Fast & Free)</option>
  <option value="gpt-4-turbo">OpenRouter: GPT-4 Turbo</option>
</select>
```

**Add Claude:**
```html
<select id="modelName" name="llm_model">
  <option value="mistral-small-latest">Mistral Small (Fast & Free)</option>
  <option value="gpt-4-turbo">OpenRouter: GPT-4 Turbo</option>
  <option value="anthropic/claude-3-sonnet">OpenRouter: Claude 3 Sonnet</option>  <!-- NEW -->
  <option value="anthropic/claude-3-opus">OpenRouter: Claude 3 Opus</option>    <!-- NEW -->
</select>
```

**That's it!** Frontend is done. No backend code changes needed.

---

#### **Step 2: Update Backend Config**
File: `app/config.py`

**Current (already has this):**
```python
self.openrouter_model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
```

**Update .env file to use Claude:**
```bash
# In .env:
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
OPENROUTER_MODEL=anthropic/claude-3-sonnet
```

**Done!** System will automatically use Claude via OpenRouter.

---

## 🔧 Adding Custom OpenAI-Compatible API

### Your Own API Server?

#### **Step 1: Frontend**
```html
<option value="my-api-model">My Custom API: Custom Model</option>
```

#### **Step 2: Backend Config**
File: `app/config.py`

Add new provider:
```python
# Custom OpenAI-compatible API
self.custom_api_key = os.getenv("CUSTOM_API_KEY", "")
self.custom_base_url = os.getenv("CUSTOM_BASE_URL", "http://localhost:8000/v1")
self.custom_model = os.getenv("CUSTOM_MODEL", "local-model")
self.custom_provider = os.getenv("CUSTOM_PROVIDER", "custom")
```

#### **Step 3: Backend Logic**
File: `app/ai/extractor.py`

Add check:
```python
elif provider == "custom" and self.cfg.custom_api_key:
    from openai import OpenAI  # OpenAI SDK works with ANY compatible API!
    client = OpenAI(
        api_key=self.cfg.custom_api_key,
        base_url=self.cfg.custom_base_url
    )
    logger.info("Using Custom API (model: %s)", self.cfg.custom_model)
```

#### **Step 4: .env**
```bash
LLM_PROVIDER=custom
CUSTOM_API_KEY=your-key-here
CUSTOM_BASE_URL=https://your-api.com/v1
CUSTOM_MODEL=your-model-name
```

**Done!** Your custom API will work exactly like any other provider.

---

## 📋 All Built-In Providers

### 1. **NVIDIA NIM** (OpenAI-compatible)
- **Setup:**
  ```bash
  LLM_PROVIDER=nvidia
  NVIDIA_API_KEY=your-key
  NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
  NVIDIA_MODEL=mistralai/mistral-large-2-instruct
  ```
- **Models:** `mistralai/mistral-large`, `meta/llama2`, etc.
- **Cost:** FREE tier available
- **Latency:** Low (NVIDIA's infrastructure)

### 2. **OpenRouter** (OpenAI-compatible)
- **Setup:**
  ```bash
  LLM_PROVIDER=openrouter
  OPENROUTER_API_KEY=sk-or-v1-...
  OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
  OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free
  ```
- **Models:** Hundreds of free + paid models
- **Cost:** FREE free models, or pay-as-you-go
- **Latency:** Medium

### 3. **OpenAI** (Native)
- **Setup:**
  ```bash
  LLM_PROVIDER=openai
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o-mini
  ```
- **Models:** GPT-4, GPT-4o, GPT-4o-mini
- **Cost:** Pay-per-token (gpt-4o-mini is cheap)
- **Latency:** Low

### 4. **Mistral** (Native)
- **Setup:**
  ```bash
  LLM_PROVIDER=mistral
  MISTRAL_API_KEY=...
  MISTRAL_MODEL=mistral-small-latest
  ```
- **Models:** Mistral Small, Large, etc.
- **Cost:** FREE tier + paid
- **Latency:** Low

### 5. **Ollama** (Local/Offline)
- **Setup:**
  ```bash
  LLM_PROVIDER=ollama
  OLLAMA_BASE_URL=http://localhost:11434
  OLLAMA_MODEL=mistral  # or llama2, neural-chat, etc.
  ```
- **Models:** Any Ollama model
- **Cost:** FREE (runs locally)
- **Latency:** Depends on hardware
- **Privacy:** 100% offline

---

## 🎬 User Flow (Frontend to Backend)

### From User's Perspective:

```
1. Open Web UI at http://localhost:8000

2. See Configuration Panel:
   ┌─────────────────────────────────────┐
   │ Target WhatsApp Group: [____text___] │
   │ LLM Provider: [dropdown ▼]           │
   │              • Mistral Small         │
   │              • Claude 3 Sonnet       │ ← User selects
   │              • Ollama: Local         │
   │ Model: [dropdown ▼] (auto-updates)  │
   │ API Key: [____password___] optional  │
   │ Execution Mode: [Production/Test]    │
   │ [💾 Save Config] [🧪 Test]          │
   └─────────────────────────────────────┘

3. User selects provider → backend updates .env

4. User clicks "Run Task Extraction"

5. System:
   - Opens WhatsApp browser
   - Collects messages
   - Sends to selected LLM (Claude, Mistral, etc.)
   - LLM extracts tasks
   - Saves to database
   - Shows: ✅ 47 tasks extracted from 150 messages

6. User can view/download tasks
```

---

## 🧪 Test Your LLM

### In Frontend:
1. Select LLM Provider
2. Enter API Key
3. Click **"🧪 Test Connection"** button
4. Shows: ✅ or ❌

### Via CLI:
```bash
# Test which provider is being used
python3 -c "
from app.config import settings
cfg = settings()
print(f'Provider: {cfg.llm_provider}')
print(f'Model: {cfg.llm_model}')
print(f'API Key set: {bool(cfg.openrouter_api_key or cfg.nvidia_api_key)}')
"
```

---

## 🎯 Quick Summary

### What's Already Done:
- ✅ 5 LLM providers pre-integrated (NVIDIA, OpenRouter, OpenAI, Mistral, Ollama)
- ✅ All use OpenAI-compatible interface
- ✅ Backend automatically detects provider from `LLM_PROVIDER` env var
- ✅ Frontend dropdown for easy selection
- ✅ API key management from UI

### To Add New LLM:
1. **If it's OpenAI-compatible (like Claude via OpenRouter):**
   - Just add option to HTML dropdown ✅
   - Update .env file ✅
   - Done! No code changes needed.

2. **If it's custom API:**
   - Add 5 lines to `config.py`
   - Add 5 lines to `extractor.py`
   - Update .env
   - Done!

3. **If it's a new native SDK (like Anthropic, Google):**
   - Create `app/ai/new_llm_client.py` with same interface
   - Add provider check in `extractor.py`
   - Update frontend + .env
   - Done!

---

## 📚 Environment Variables Reference

```bash
# LLM Provider Selection
LLM_PROVIDER=nvidia|openrouter|openai|mistral|ollama|custom

# NVIDIA NIM (OpenAI-compatible)
NVIDIA_API_KEY=sk-...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=mistralai/mistral-large-2-instruct

# OpenRouter (OpenAI-compatible, supports 100+ models)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3-sonnet

# OpenAI (Native)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Mistral (Native)
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-small-latest

# Ollama (Local, no API key needed)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Custom OpenAI-compatible API
CUSTOM_API_KEY=...
CUSTOM_BASE_URL=http://your-api.com/v1
CUSTOM_MODEL=your-model

# Other
TARGET_WINDOW_DAYS=7
WHATSAPP_GROUP_NAME=Your Group Name
DRY_RUN=false
```

---

## ✅ Done!

Your system is **production-ready** for any LLM. Users can switch providers from the UI without touching code. 🚀
