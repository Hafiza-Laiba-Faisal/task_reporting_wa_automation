from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook

from app.logger import get_logger

logger = get_logger("excel_writer")


class ExcelWriter:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path).expanduser()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def write_tasks(self, rows: list[dict]) -> None:
        if not rows:
            logger.info("No task rows to write to Excel.")
            return

        target = self.file_path
        temp_target = target.with_suffix(".tmp.xlsx")

        if target.exists():
            workbook = load_workbook(target)
            ws = workbook.active
        else:
            workbook = Workbook()
            ws = workbook.active
            ws.title = "Tasks"
            ws.append([
                "Task ID",
                "Date",
                "Task",
                "Assigned To",
                "Deadline",
                "Priority",
                "Status",
                "Source Group",
                "Source Sender",
                "Source Message",
                "Message Timestamp",
                "Confidence",
                "Created At",
                "Updated At",
                "Review Required",
            ])

        for row in rows:
            values = [
                row.get("task_id", ""),
                row.get("date", ""),
                row.get("task", ""),
                row.get("assignee", ""),
                row.get("deadline", ""),
                row.get("priority", ""),
                row.get("status", ""),
                row.get("source_group", ""),
                row.get("source_sender", ""),
                row.get("source_message", ""),
                row.get("message_timestamp", ""),
                row.get("confidence", ""),
                row.get("created_at", ""),
                row.get("updated_at", ""),
                bool(row.get("review_required", False)),
            ]
            ws.append(values)

        workbook.save(temp_target)
        temp_target.replace(target)
        logger.info("Excel workbook updated successfully: %s", target)
