import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from app.config import settings


def _db_path() -> Path:
    cfg = settings()
    path = cfg.resolved_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                group_name TEXT,
                sender TEXT,
                message_text_raw TEXT,
                message_text_normalized TEXT,
                message_timestamp TEXT,
                message_fingerprint TEXT UNIQUE,
                processed_at TEXT,
                status TEXT,
                source_message_uri TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_key TEXT UNIQUE,
                task TEXT,
                assignee TEXT,
                deadline TEXT,
                priority TEXT,
                status TEXT,
                source_group TEXT,
                source_sender TEXT,
                source_message TEXT,
                message_timestamp TEXT,
                confidence REAL,
                review_required INTEGER,
                created_at TEXT,
                updated_at TEXT,
                last_processed_run_id TEXT
            );

            CREATE TABLE IF NOT EXISTS processing_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE,
                started_at TEXT,
                ended_at TEXT,
                status TEXT,
                target_group TEXT,
                messages_discovered INTEGER DEFAULT 0,
                new_messages INTEGER DEFAULT 0,
                tasks_detected INTEGER DEFAULT 0,
                tasks_updated INTEGER DEFAULT 0,
                tasks_skipped INTEGER DEFAULT 0,
                duplicates INTEGER DEFAULT 0,
                errors TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def message_fingerprint(sender: str, message_text: str, timestamp: str, group_name: str) -> str:
    source = f"{group_name}|{sender}|{timestamp}|{message_text.strip().lower()}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def task_fingerprint(task: str, assignee: str | None = None) -> str:
    def clean(value: str | None) -> str:
        if value is None:
            return ""
        normalized = re.sub(r"[^a-z0-9\s]", " ", value.lower())
        return " ".join(normalized.split())

    scope = f"{clean(task)}|{clean(assignee)}"
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()


def upsert_message(record: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO messages (
                run_id, group_name, sender, message_text_raw, message_text_normalized,
                message_timestamp, message_fingerprint, processed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_fingerprint) DO UPDATE SET
                run_id=excluded.run_id,
                group_name=excluded.group_name,
                sender=excluded.sender,
                message_text_raw=excluded.message_text_raw,
                message_text_normalized=excluded.message_text_normalized,
                message_timestamp=excluded.message_timestamp,
                processed_at=excluded.processed_at,
                status=excluded.status
            """,
            (
                record.get("run_id"),
                record.get("group_name"),
                record.get("sender"),
                record.get("message_text_raw"),
                record.get("message_text_normalized"),
                record.get("message_timestamp"),
                record.get("message_fingerprint"),
                record.get("processed_at"),
                record.get("status", "processed"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_task(record: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO tasks (
                task_key, task, assignee, deadline, priority, status, source_group,
                source_sender, source_message, message_timestamp, confidence,
                review_required, created_at, updated_at, last_processed_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_key) DO UPDATE SET
                task=excluded.task,
                assignee=excluded.assignee,
                deadline=excluded.deadline,
                priority=excluded.priority,
                status=excluded.status,
                source_group=excluded.source_group,
                source_sender=excluded.source_sender,
                source_message=excluded.source_message,
                message_timestamp=excluded.message_timestamp,
                confidence=excluded.confidence,
                review_required=excluded.review_required,
                updated_at=excluded.updated_at,
                last_processed_run_id=excluded.last_processed_run_id
            """,
            (
                record.get("task_key"),
                record.get("task"),
                record.get("assignee"),
                record.get("deadline"),
                record.get("priority"),
                record.get("status"),
                record.get("source_group"),
                record.get("source_sender"),
                record.get("source_message"),
                record.get("message_timestamp"),
                record.get("confidence"),
                int(bool(record.get("review_required"))),
                record.get("created_at"),
                record.get("updated_at"),
                record.get("last_processed_run_id"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def existing_message_fingerprints() -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT message_fingerprint FROM messages").fetchall()
    finally:
        conn.close()
    return {row["message_fingerprint"] for row in rows}


def existing_task_keys() -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT task_key FROM tasks").fetchall()
    finally:
        conn.close()
    return {row["task_key"] for row in rows}


def record_run(run_id: str, target_group: str, started_at: str, status: str = "running", errors: str | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO processing_runs (run_id, started_at, status, target_group, errors)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                started_at=excluded.started_at,
                status=excluded.status,
                target_group=excluded.target_group,
                errors=excluded.errors
            """,
            (run_id, started_at, status, target_group, errors),
        )
        conn.commit()
    finally:
        conn.close()


def finalize_run(run_id: str, ended_at: str, status: str, **counts) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE processing_runs
            SET ended_at = ?, status = ?, messages_discovered = COALESCE(messages_discovered, 0) + ?,
                new_messages = COALESCE(new_messages, 0) + ?, tasks_detected = COALESCE(tasks_detected, 0) + ?,
                tasks_updated = COALESCE(tasks_updated, 0) + ?, tasks_skipped = COALESCE(tasks_skipped, 0) + ?,
                duplicates = COALESCE(duplicates, 0) + ?
            WHERE run_id = ?
            """,
            (
                ended_at,
                status,
                counts.get("messages_discovered", 0),
                counts.get("new_messages", 0),
                counts.get("tasks_detected", 0),
                counts.get("tasks_updated", 0),
                counts.get("tasks_skipped", 0),
                counts.get("duplicates", 0),
                run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
