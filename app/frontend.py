import asyncio
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.repository import init_db

app = FastAPI(title="WhatsApp Task Automation", version="1.0.0")

base_dir = Path(__file__).resolve().parent
static_dir = base_dir / "static"
templates_dir = base_dir / "templates"
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Config ───────────────────────────────────────────────────────────────────

@app.post("/api/config")
async def save_config(
    whatsapp_group_name: str = Form(...),
    dry_run: str = Form("false"),
    llm_api_key: str = Form(""),
    llm_model: str = Form("mistral-small-latest"),
):
    cfg = settings()
    if not whatsapp_group_name.strip():
        raise HTTPException(status_code=400, detail="Group name is required.")
    cfg.whatsapp_group_name = whatsapp_group_name.strip()
    cfg.dry_run = dry_run.lower() == "true"
    cfg.llm_api_key = llm_api_key
    cfg.llm_model = llm_model
    init_db()
    return {"status": "saved", "group_name": cfg.whatsapp_group_name, "dry_run": cfg.dry_run}


@app.get("/api/config")
async def get_config():
    cfg = settings()
    return {
        "whatsapp_group_name": cfg.whatsapp_group_name,
        "dry_run": cfg.dry_run,
        "llm_model": cfg.llm_model,
    }


# ── DB Viewer ────────────────────────────────────────────────────────────────

@app.get("/api/db/messages")
async def get_messages():
    """Return all messages from DB for the viewer."""
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
    """Return all tasks from DB for the viewer."""
    cfg = settings()
    db_path = cfg.resolved_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT task, assignee, status, priority, deadline, source_sender, "
            "message_timestamp, confidence, created_at FROM tasks ORDER BY rowid DESC LIMIT 200"
        )
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        rows = []
    finally:
        conn.close()
    return {"tasks": rows, "count": len(rows)}


# ── Pipeline ─────────────────────────────────────────────────────────────────

def _run_pipeline_sync():
    """Open WhatsApp, collect messages, extract tasks, write Excel."""
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
        collector = MessageCollector(page, run_id=f"run-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        messages = collector.collect()
        processor = TaskProcessor(messages)
        tasks = processor.run()
        return {"status": "completed", "task_count": len(tasks), "messages_seen": len(messages)}
    finally:
        browser.close()


@app.post("/api/run")
async def run_pipeline():
    try:
        result = await asyncio.to_thread(_run_pipeline_sync)
        return result
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "success": False, "detail": str(exc)},
        )


# ── Reprocess from DB ─────────────────────────────────────────────────────────

def _reprocess_from_db_sync():
    """Re-run task extraction on messages already in DB. No WhatsApp needed."""
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
        return {"status": "completed", "task_count": 0, "messages_seen": 0, "note": "No messages in DB"}

    messages = [dict(r) for r in rows]
    processor = TaskProcessor(messages)
    tasks = processor.extract_tasks()
    processor.write_excel(tasks)

    return {
        "status": "completed",
        "task_count": len(tasks),
        "messages_seen": len(messages),
        "note": "Reprocessed from DB (no WhatsApp opened)",
    }


@app.post("/api/reprocess")
async def reprocess_from_db():
    """Re-extract tasks from already-collected messages in DB. No WhatsApp needed."""
    try:
        result = await asyncio.to_thread(_reprocess_from_db_sync)
        return result
    except Exception as exc:
        from app.ai.mistral_client import RateLimitError
        if isinstance(exc, RateLimitError):
            return JSONResponse(
                status_code=429,
                content={"status": "rate_limited", "detail": "Mistral rate limit. Wait a few minutes and try again."},
            )
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(exc)},
        )
