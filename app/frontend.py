import asyncio
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.repository import init_db
from app.logger import get_logger

logger = get_logger("frontend")

app = FastAPI(title="WhatsApp Task Automation", version="1.0.0")

base_dir    = Path(__file__).resolve().parent
root_dir    = base_dir.parent
static_dir  = base_dir / "static"
templates_dir = base_dir / "templates"
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _env_path() -> Path:
    return root_dir / ".env"


def _read_env() -> dict[str, str]:
    """Read .env into a dict preserving all keys."""
    env: dict[str, str] = {}
    p = _env_path()
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            env[k.strip()] = v.strip()
    return env


def _write_env(env: dict[str, str]) -> None:
    """Overwrite .env keeping existing comments, updating only changed keys."""
    p = _env_path()
    if not p.exists():
        p.write_text("")

    lines = p.read_text().splitlines()
    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            new_lines.append(line)
            continue
        if "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in env:
                new_lines.append(f"{k}={env[k]}")
                written_keys.add(k)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append any new keys not previously in .env
    for k, v in env.items():
        if k not in written_keys:
            new_lines.append(f"{k}={v}")

    p.write_text("\n".join(new_lines) + "\n")


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Data download ────────────────────────────────────────────────────────────

@app.get("/api/download/excel")
async def download_excel():
    """Download the generated Excel file."""
    cfg  = settings()
    path = cfg.resolved_excel_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found. Run extraction first.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="tenbit_tasks.xlsx",
    )


# ── Config ───────────────────────────────────────────────────────────────────

@app.post("/api/config")
async def save_config(request: Request):
    """Save general + LLM config to .env."""
    body = await request.json()

    updates: dict[str, str] = {}

    # WhatsApp
    if "whatsapp_group_name" in body and body["whatsapp_group_name"].strip():
        updates["WHATSAPP_GROUP_NAME"] = body["whatsapp_group_name"].strip()

    # Execution
    if "dry_run" in body:
        updates["DRY_RUN"] = "true" if str(body["dry_run"]).lower() == "true" else "false"

    # LLM provider + model
    if "llm_provider" in body and body["llm_provider"].strip():
        updates["LLM_PROVIDER"] = body["llm_provider"].strip().lower()

    if "llm_model" in body and body["llm_model"].strip():
        provider = body.get("llm_provider", "").strip().lower()
        model    = body["llm_model"].strip()
        updates["LLM_MODEL"] = model
        if provider == "openrouter":
            updates["OPENROUTER_MODEL"] = model
        elif provider == "nvidia":
            updates["NVIDIA_MODEL"] = model
        elif provider == "mistral":
            updates["MISTRAL_MODEL"] = model
        elif provider == "ollama":
            updates["OLLAMA_MODEL"] = model

    # API keys / base URLs
    for field, env_key in [
        ("openrouter_api_key",  "OPENROUTER_API_KEY"),
        ("openrouter_base_url", "OPENROUTER_BASE_URL"),
        ("nvidia_api_key",      "NVIDIA_API_KEY"),
        ("nvidia_base_url",     "NVIDIA_BASE_URL"),
        ("mistral_api_key",     "MISTRAL_API_KEY"),
        ("openai_api_key",      "OPENAI_API_KEY"),
        ("ollama_base_url",     "OLLAMA_BASE_URL"),
        ("ollama_model",        "OLLAMA_MODEL"),
    ]:
        if field in body and str(body[field]).strip():
            updates[env_key] = str(body[field]).strip()

    if not updates:
        raise HTTPException(status_code=400, detail="No valid config fields provided.")

    _write_env(updates)

    # Reload env so next settings() call picks up changes
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path(), override=True)

    cfg = settings()
    return {
        "status": "saved",
        "group_name": cfg.whatsapp_group_name,
        "llm_provider": cfg.llm_provider,
        "llm_model": cfg.llm_model,
        "dry_run": cfg.dry_run,
    }


@app.get("/api/config")
async def get_config():
    cfg = settings()
    return {
        "whatsapp_group_name": cfg.whatsapp_group_name,
        "dry_run":             cfg.dry_run,
        "llm_provider":        cfg.llm_provider,
        "llm_model":           cfg.llm_model,
        "openrouter_model":    cfg.openrouter_model,
        "openrouter_base_url": cfg.openrouter_base_url,
        "nvidia_model":        cfg.nvidia_model,
        "nvidia_base_url":     cfg.nvidia_base_url,
        "mistral_model":       cfg.mistral_model,
        "ollama_model":        cfg.ollama_model,
        "ollama_base_url":     cfg.ollama_base_url,
    }


# ── Google Sheets Config ──────────────────────────────────────────────────────

@app.post("/api/google-sheets/config")
async def save_google_sheets_config(request: Request):
    """Save Google Sheets configuration to .env."""
    body = await request.json()

    updates: dict[str, str] = {}

    if "enabled" in body:
        updates["GOOGLE_SHEETS_ENABLED"] = "true" if body["enabled"] else "false"

    if "sheet_id" in body:
        updates["GOOGLE_SHEETS_ID"] = str(body["sheet_id"]).strip()

    if "credentials_path" in body and str(body["credentials_path"]).strip():
        updates["GOOGLE_SHEETS_CREDENTIALS"] = str(body["credentials_path"]).strip()

    if "share_with" in body:
        val = body["share_with"]
        if isinstance(val, list):
            val = ",".join(val)
        updates["GOOGLE_SHEETS_SHARE_WITH"] = str(val).strip()

    if "sheet_name" in body and str(body["sheet_name"]).strip():
        updates["GOOGLE_SHEETS_SHEET_NAME"] = str(body["sheet_name"]).strip()

    _write_env(updates)

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path(), override=True)

    cfg = settings()
    return {
        "status":       "saved",
        "enabled":      cfg.google_sheets_enabled,
        "sheet_id":     cfg.google_sheets_id,
        "share_with":   cfg.google_sheets_share_with,
        "sheet_name":   cfg.google_sheets_sheet_name,
    }


@app.get("/api/google-sheets/config")
async def get_google_sheets_config():
    cfg = settings()
    return {
        "enabled":          cfg.google_sheets_enabled,
        "sheet_id":         cfg.google_sheets_id,
        "credentials_path": cfg.google_sheets_credentials,
        "share_with":       ",".join(cfg.google_sheets_share_with),
        "sheet_name":       cfg.google_sheets_sheet_name,
    }


@app.post("/api/google-sheets/test")
async def test_google_sheets():
    """Test Google Sheets connection using stored credentials."""
    cfg = settings()
    if not cfg.google_sheets_id:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Sheet ID not configured."})
    if not cfg.google_sheets_credentials:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Credentials path not configured."})
    creds_path = Path(cfg.google_sheets_credentials).expanduser()
    if not creds_path.exists():
        return JSONResponse(status_code=400, content={
            "status": "error",
            "detail": f"Credentials file not found: {creds_path}"
        })
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds  = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
        gc     = gspread.authorize(creds)
        sh     = gc.open_by_key(cfg.google_sheets_id)
        url    = f"https://docs.google.com/spreadsheets/d/{cfg.google_sheets_id}/edit"
        return {"status": "ok", "title": sh.title, "url": url}
    except ImportError:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "detail": "gspread not installed. Run: pip install gspread google-auth"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@app.post("/api/google-sheets/sync")
async def sync_google_sheets():
    """Manually sync all tasks in DB to Google Sheets."""
    def _sync():
        from app.pipeline.processor import TaskProcessor
        cfg = settings()
        if not cfg.google_sheets_enabled:
            return {"status": "error", "detail": "Google Sheets not enabled in config."}
        # Create a dummy processor (no messages) just to call write_google_sheets
        processor = TaskProcessor([])
        url = processor.write_google_sheets([])
        return {"status": "ok", "url": url}

    try:
        result = await asyncio.to_thread(_sync)
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


# ── DB Viewer ────────────────────────────────────────────────────────────────

@app.get("/api/db/messages")
async def get_messages():
    cfg = settings()
    db_path = cfg.resolved_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT sender, message_text_normalized, message_timestamp, processed_at, group_name "
            "FROM messages ORDER BY rowid DESC LIMIT 200"
        )
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        rows = []
    finally:
        conn.close()
    return {"messages": rows, "count": len(rows)}


@app.get("/api/db/tasks")
async def get_tasks():
    cfg = settings()
    db_path = cfg.resolved_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT task, assignee, status, priority, deadline, source_sender, "
            "message_timestamp, confidence, created_at FROM tasks ORDER BY rowid DESC LIMIT 500"
        )
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        rows = []
    finally:
        conn.close()
    return {"tasks": rows, "count": len(rows)}


# ── Pipeline ─────────────────────────────────────────────────────────────────

def _run_pipeline_sync():
    from datetime import datetime

    from app.pipeline.processor import TaskProcessor
    from app.whatsapp.browser import WhatsAppBrowser
    from app.whatsapp.group_finder import GroupFinder
    from app.whatsapp.message_collector import MessageCollector

    cfg = settings()
    if not cfg.whatsapp_group_name:
        raise ValueError("Configure WHATSAPP_GROUP_NAME first.")

    init_db()
    browser = WhatsAppBrowser()
    page = browser.open()
    try:
        browser.wait_until_loaded()
        finder = GroupFinder(page)
        finder.run()
        collector = MessageCollector(
            page, run_id=f"run-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        messages   = collector.collect()
        processor  = TaskProcessor(messages)
        tasks      = processor.run()
        sheets_url = processor.write_google_sheets(tasks)
        return {
            "status":       "completed",
            "task_count":   len(tasks),
            "messages_seen": len(messages),
            "sheets_url":   sheets_url,
        }
    finally:
        browser.close()


@app.post("/api/run")
async def run_pipeline():
    try:
        result = await asyncio.to_thread(_run_pipeline_sync)
        return result
    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "success": False, "detail": str(exc)},
        )


# ── Reprocess from DB ─────────────────────────────────────────────────────────

def _reprocess_from_db_sync():
    from app.pipeline.processor import TaskProcessor

    cfg = settings()
    init_db()

    db_path = cfg.resolved_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT sender, message_text_normalized, message_timestamp FROM messages ORDER BY rowid"
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {"status": "completed", "task_count": 0, "messages_seen": 0,
                "note": "No messages in DB", "sheets_url": ""}

    messages  = [dict(r) for r in rows]
    processor = TaskProcessor(messages)
    tasks     = processor.extract_tasks()
    processor.write_excel(tasks)
    sheets_url = processor.write_google_sheets(tasks)

    return {
        "status":        "completed",
        "task_count":    len(tasks),
        "messages_seen": len(messages),
        "note":          "Reprocessed from DB (no WhatsApp opened)",
        "sheets_url":    sheets_url,
    }


@app.post("/api/reprocess")
async def reprocess_from_db():
    try:
        result = await asyncio.to_thread(_reprocess_from_db_sync)
        return result
    except Exception as exc:
        from app.ai.mistral_client import RateLimitError
        if isinstance(exc, RateLimitError):
            return JSONResponse(
                status_code=429,
                content={"status": "rate_limited",
                         "detail": "Rate limit reached. Wait a few minutes and try again."},
            )
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(exc)},
        )
