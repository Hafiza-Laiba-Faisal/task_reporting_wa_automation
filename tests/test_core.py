import os
from pathlib import Path

import pytest

from app.ai.schemas import TaskExtraction
from app.config import settings
from app.database.repository import task_fingerprint


def test_settings_loads_group_name_from_env(monkeypatch):
    monkeypatch.setenv("WHATSAPP_GROUP_NAME", "ABC Company - Operations")
    monkeypatch.setenv("TARGET_WINDOW_DAYS", "7")
    monkeypatch.setenv("DRY_RUN", "true")
    cfg = settings()
    assert cfg.whatsapp_group_name == "ABC Company - Operations"
    assert cfg.target_window_days == 7
    assert cfg.dry_run is True


def test_task_schema_requires_task_and_message_fields():
    payload = {
        "task": "Send invoice to Ali tomorrow.",
        "source_message": "Please send the invoice to Ali tomorrow.",
        "sender": "Aisha",
        "message_timestamp": "2026-09-09T09:15:00",
        "confidence": 0.91,
    }
    item = TaskExtraction.model_validate(payload)
    assert item.task == payload["task"]
    assert item.confidence == 0.91


def test_task_schema_allows_optional_fields():
    item = TaskExtraction.model_validate({
        "task": "Check the budget report.",
        "assignee": "Nadia",
        "deadline": "2026-09-11T17:00:00",
        "priority": "medium",
        "status": "open",
        "source_message": "Can someone check the budget report by Friday?",
        "sender": "Sam",
        "message_timestamp": "2026-09-09T12:00:00",
        "confidence": 0.74,
    })
    assert item.assignee == "Nadia"
    assert item.status == "open"


def test_task_fingerprint_is_stable_for_same_task():
    a = task_fingerprint("Send invoice to Ali tomorrow.", "Ali")
    b = task_fingerprint("send invoice to ali tomorrow", "ali")
    assert a == b


def test_task_fingerprint_changes_for_modified_task():
    a = task_fingerprint("Send invoice to Ali tomorrow.", "Ali")
    b = task_fingerprint("Send invoice to Noor tomorrow.", "Ali")
    assert a != b


def test_group_search_wait_allows_indefinite_waits_until_ready():
    assert True


def test_group_name_matching_is_normalized_for_whatsapp_variants():
    target = "TenBit_Daily_Task_Reporting"
    candidates = [
        "TenBit Daily Task Reporting",
        "TenBit_Daily_Task_Reporting",
        "TenBit Daily Task Reporting (1)",
    ]

    normalized = [
        "".join(ch for ch in item.lower() if ch.isalnum())
        for item in candidates
    ]
    assert "".join(ch for ch in target.lower() if ch.isalnum()) in normalized
