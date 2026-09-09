from __future__ import annotations

import uuid
from datetime import datetime

from app.ai.extractor import LLMTaskExtractor
from app.config import settings
from app.database.repository import finalize_run, init_db, record_run, task_fingerprint, upsert_task
from app.excel.writer import ExcelWriter
from app.logger import get_logger

logger = get_logger("pipeline")


class TaskProcessor:
    def __init__(self, messages: list[dict], dry_run: bool | None = None):
        self.messages = messages
        self.cfg = settings()
        self.dry_run = self.cfg.dry_run if dry_run is None else dry_run
        self.extractor = LLMTaskExtractor(self.cfg)

    def extract_tasks(self) -> list[dict]:
        """
        Send all messages to LLM in one batch call so it understands
        the full conversation context before extracting tasks.
        """
        valid_messages = [
            m for m in self.messages
            if m.get("message_text_normalized", "").strip()
        ]

        if not valid_messages:
            logger.info("No messages to process.")
            return []

        logger.info("Extracting tasks from %d messages via batch LLM call.", len(valid_messages))
        extracted = self.extractor.extract_batch(valid_messages)

        tasks: list[dict] = []
        for payload in extracted:
            task_key = task_fingerprint(payload.task, payload.assignee)
            record = {
                "task_key": task_key,
                "task": payload.task,
                "assignee": payload.assignee,
                "deadline": payload.deadline,
                "priority": payload.priority,
                "status": payload.status,
                "source_group": self.cfg.whatsapp_group_name,
                "source_sender": payload.sender,
                "source_message": payload.source_message,
                "message_timestamp": payload.message_timestamp,
                "confidence": payload.confidence,
                "review_required": payload.confidence < 0.8,
                "created_at": datetime.utcnow().isoformat(timespec="seconds"),
                "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
                "last_processed_run_id": str(uuid.uuid4()),
            }
            tasks.append(record)
            if not self.dry_run:
                upsert_task(record)

        logger.info("Extracted %d tasks from %d messages.", len(tasks), len(valid_messages))
        return tasks

    def write_excel(self, tasks: list[dict]) -> None:
        if self.dry_run:
            logger.info("Dry run enabled; no Excel update performed.")
            return
        # Simple reporting format — only what matters
        rows = [
            {
                "task":     task.get("task", ""),
                "assignee": task.get("assignee", ""),
                "status":   task.get("status", "open"),
                "priority": task.get("priority", "medium"),
                "deadline": task.get("deadline", ""),
                "date":     task.get("message_timestamp", ""),
            }
            for task in tasks
        ]
        writer = ExcelWriter(self.cfg.excel_output_path)
        writer.write_tasks(rows)
        logger.info("Excel update complete for %s tasks.", len(rows))

    def run(self) -> list[dict]:
        init_db()
        run_id = str(uuid.uuid4())
        started_at = datetime.utcnow().isoformat(timespec="seconds")
        record_run(run_id, self.cfg.whatsapp_group_name, started_at, "running")
        tasks = self.extract_tasks()
        self.write_excel(tasks)
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
        return tasks
