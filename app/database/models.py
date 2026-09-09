from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MessageRecord:
    id: str | None = None
    group_name: str | None = None
    sender: str | None = None
    message_text_raw: str | None = None
    message_text_normalized: str | None = None
    message_timestamp: str | None = None
    message_fingerprint: str | None = None
    status: str = "pending"
    processed_at: str | None = None
    run_id: str | None = None


@dataclass
class TaskRecord:
    id: str | None = None
    task_key: str | None = None
    task: str | None = None
    assignee: str | None = None
    deadline: str | None = None
    priority: str | None = None
    status: str | None = None
    source_group: str | None = None
    source_sender: str | None = None
    source_message: str | None = None
    message_timestamp: str | None = None
    confidence: float | None = None
    review_required: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    last_processed_run_id: str | None = None
