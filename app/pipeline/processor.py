from __future__ import annotations

import uuid
from datetime import date, datetime

from app.ai.extractor import LLMTaskExtractor
from app.config import settings
from app.database.repository import finalize_run, init_db, record_run, task_fingerprint, upsert_task
from app.excel.writer import ExcelWriter
from app.logger import get_logger

logger = get_logger("pipeline")


def _today_iso() -> str:
    return date.today().isoformat()   # YYYY-MM-DD


def _resolve_message_date(messages: list[dict]) -> str:
    """
    Try to derive the actual message date from collected messages.
    message_timestamp is typically just a time string ("7:45 PM") — use today's date.
    If messages have a full ISO timestamp, extract the date from there.
    Falls back to today.
    """
    for m in messages:
        ts = str(m.get("message_timestamp", ""))
        # Full ISO or datetime string
        if len(ts) >= 10 and ts[4] == "-":
            return ts[:10]
        processed = str(m.get("processed_at", ""))
        if len(processed) >= 10:
            return processed[:10]
    return _today_iso()


class TaskProcessor:
    def __init__(self, messages: list[dict], dry_run: bool | None = None):
        self.messages = messages
        self.cfg = settings()
        self.dry_run = self.cfg.dry_run if dry_run is None else dry_run
        self.extractor = LLMTaskExtractor(self.cfg)
        # Date the messages belong to (used for task fingerprinting + Excel date column)
        self.run_date = _resolve_message_date(messages) if messages else _today_iso()

    def _fix_known_aliases(self) -> None:
        """
        Post-extraction correction:
        - AT → Ayan (WhatsApp alias used by Ayan)
        - unknown with no source_sender → keep as-is (cannot infer)
        Runs after every extract_tasks() call to keep DB clean.
        """
        from app.database.repository import get_connection
        conn = get_connection()
        # AT is always Ayan per SENDER_NAME_MAP
        updated = conn.execute(
            "UPDATE tasks SET assignee='Ayan', source_sender='Ayan' WHERE assignee='AT'"
        ).rowcount
        conn.commit()
        conn.close()
        if updated:
            logger.info("Alias fix: AT → Ayan (%d tasks)", updated)

    def extract_tasks(self) -> list[dict]:
        """
        Send all messages to LLM in one batch call so it understands
        the full conversation context before extracting tasks.

        Morning messages ("I am working on X") → status = in_progress
        Evening messages ("X done") → status = completed
        Both are on the same day → same task_key (date-scoped) → ON CONFLICT upserts,
        so the evening run updates the morning record's status to completed.
        """
        valid_messages = [
            m for m in self.messages
            if m.get("message_text_normalized", "").strip()
        ]

        if not valid_messages:
            logger.info("No messages to process.")
            return []

        logger.info(
            "Extracting tasks from %d messages via batch LLM call (date: %s).",
            len(valid_messages), self.run_date
        )
        extracted = self.extractor.extract_batch(valid_messages)

        tasks: list[dict] = []
        for payload in extracted:
            # Fingerprint is scoped to task + assignee + date
            # → same task updated in evening will UPSERT (update status) not duplicate
            task_key = task_fingerprint(payload.task, payload.assignee, self.run_date)
            record = {
                "task_key":              task_key,
                "task":                  payload.task,
                "assignee":              payload.assignee,
                "deadline":              payload.deadline,
                "priority":              payload.priority,
                "status":                payload.status,
                "source_group":          self.cfg.whatsapp_group_name,
                "source_sender":         payload.sender,
                "source_message":        payload.source_message,
                "message_timestamp":     payload.message_timestamp,
                "confidence":            payload.confidence,
                "review_required":       payload.confidence < 0.8,
                "date":                  self.run_date,   # ← actual message date for Excel
                "created_at":            datetime.utcnow().isoformat(timespec="seconds"),
                "updated_at":            datetime.utcnow().isoformat(timespec="seconds"),
                "last_processed_run_id": str(uuid.uuid4()),
            }
            tasks.append(record)
            if not self.dry_run:
                upsert_task(record)

        logger.info("Extracted %d tasks from %d messages.", len(tasks), len(valid_messages))
        self._fix_known_aliases()
        return tasks

    def _get_recent_task_rows(self, days: int = 2) -> list[dict]:
        """
        Read tasks from DB for the last `days` days only.
        Excel/Sheets always shows: today + yesterday (max).
        DB data is preserved forever — only the export is limited.
        """
        from app.database.repository import get_connection
        from datetime import timedelta

        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()  # e.g. yesterday
        conn = get_connection()
        conn.row_factory = __import__("sqlite3").Row
        all_tasks = [dict(r) for r in conn.execute(
            "SELECT task, assignee, status, priority, deadline, date, created_at "
            "FROM tasks WHERE date >= ? ORDER BY date, assignee",
            (cutoff,)
        ).fetchall()]
        conn.close()
        logger.info("Export: %d tasks from last %d days (cutoff: %s)", len(all_tasks), days, cutoff)
        return [
            {
                "task":     t.get("task", ""),
                "assignee": t.get("assignee", ""),
                "status":   t.get("status", "open"),
                "priority": t.get("priority", "medium"),
                "deadline": t.get("deadline", ""),
                "date":     t.get("date") or t.get("created_at", "")[:10],
            }
            for t in all_tasks
        ]

    def write_excel(self, tasks: list[dict]) -> None:
        if self.dry_run:
            logger.info("Dry run enabled; no Excel update performed.")
            return
        rows = self._get_recent_task_rows(days=2)
        writer = ExcelWriter(self.cfg.excel_output_path)
        writer.write_tasks(rows)
        logger.info("Excel updated with %d tasks (last 2 days).", len(rows))

    def write_google_sheets(self, tasks: list[dict]) -> str:
        """Sync last 2 days of tasks to Google Sheets. Returns sheet URL or empty string."""
        if self.dry_run:
            logger.info("Dry run enabled; skipping Google Sheets sync.")
            return ""
        if not self.cfg.google_sheets_enabled:
            return ""
        if not self.cfg.google_sheets_id:
            logger.warning("GOOGLE_SHEETS_ID not set — skipping Sheets sync.")
            return ""
        if not self.cfg.google_sheets_credentials:
            logger.warning("GOOGLE_SHEETS_CREDENTIALS not set — skipping Sheets sync.")
            return ""

        try:
            from app.google_sheets.writer import GoogleSheetsWriter
            rows   = self._get_recent_task_rows(days=2)
            writer = GoogleSheetsWriter(
                spreadsheet_id=self.cfg.google_sheets_id,
                credentials_path=self.cfg.google_sheets_credentials,
                sheet_name=self.cfg.google_sheets_sheet_name,
            )
            url = writer.write_tasks(rows)
            if self.cfg.google_sheets_share_with:
                writer.share_with_team(self.cfg.google_sheets_share_with)
            logger.info("Google Sheets synced: %s", url)
            return url
        except Exception as e:
            logger.error("Google Sheets sync failed: %s", e)
            return ""

    def run(self) -> list[dict]:
        init_db()
        run_id = str(uuid.uuid4())
        started_at = datetime.utcnow().isoformat(timespec="seconds")
        record_run(run_id, self.cfg.whatsapp_group_name, started_at, "running")
        tasks = self.extract_tasks()
        self.write_excel(tasks)
        sheets_url = self.write_google_sheets(tasks)
        finalize_run(
            run_id,
            datetime.utcnow().isoformat(timespec="seconds"),
            "completed",
            messages_discovered=len(self.messages),
            new_messages=len(self.messages),
            tasks_detected=len(tasks),
            tasks_updated=len(tasks),
            tasks_skipped=0,
            duplicates=0,
        )
        logger.info("Run completed for group: %s", self.cfg.whatsapp_group_name)
        result = {"tasks": tasks, "sheets_url": sheets_url}
        return tasks
