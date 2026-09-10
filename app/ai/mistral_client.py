from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from app.ai.prompts import TASK_EXTRACTION_SYSTEM_PROMPT
from app.ai.schemas import TaskExtraction
from app.config import settings
from app.logger import get_logger

logger = get_logger("mistral_client")


def _get_system_prompt(cfg) -> str:
    """Return custom prompt from config if set, else default."""
    if cfg.custom_system_prompt:
        logger.info("Using custom system prompt from config.")
        return cfg.custom_system_prompt
    return TASK_EXTRACTION_SYSTEM_PROMPT


class RateLimitError(Exception):
    """Raised when API returns 429 rate limit."""
    pass


def _build_conversation_text(messages: list[dict[str, Any]]) -> str:
    today = date.today().strftime("%d %b %Y")
    lines = [f"Date: {today}", ""]
    for msg in messages:
        sender = msg.get("sender", "unknown")
        timestamp = msg.get("message_timestamp", "")
        text = msg.get("message_text_normalized", "").strip()
        if text:
            lines.append(f"[{timestamp}] {sender}: {text}")
    return "\n".join(lines)


def _parse_response(raw: str) -> list[dict]:
    """Extract JSON array from LLM response — handles markdown code fences."""
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    parsed = json.loads(clean)
    if isinstance(parsed, dict):
        for key in ("tasks", "task_list", "results"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        return [parsed]
    return parsed


def _to_task_extractions(payload_list: list[dict], message_count: int, source: str) -> list[TaskExtraction]:
    allowed_priorities = {"low", "medium", "high", "urgent"}
    allowed_statuses = {"open", "in_progress", "completed", "blocked", "review"}
    tasks: list[TaskExtraction] = []
    for item in payload_list:
        if not item.get("task"):
            continue
        normalized = {
            "task": item.get("task", ""),
            "assignee": item.get("assignee") or item.get("assigned_to"),
            "deadline": item.get("deadline"),
            "priority": item.get("priority", "medium"),
            "status": item.get("status", "in_progress"),
            "source_message": item.get("source_message", ""),
            "sender": item.get("source_sender") or item.get("sender", "unknown"),
            "message_timestamp": item.get("message_timestamp", ""),
            "confidence": item.get("confidence", 0.88),
        }
        if normalized["priority"] not in allowed_priorities:
            normalized["priority"] = "medium"
        if normalized["status"] not in allowed_statuses:
            normalized["status"] = "open"
        try:
            tasks.append(TaskExtraction.model_validate(normalized))
        except Exception as e:
            logger.warning("Validation failed [%s]: %s | item: %s", source, e, item)
    logger.info("[%s] Extracted %d tasks from %d messages.", source, len(tasks), message_count)
    return tasks


# ── NVIDIA NIM ────────────────────────────────────────────────────────────────

class NvidiaBatchExtractor:
    """
    Uses NVIDIA NIM (OpenAI-compatible API) for batch task extraction.
    Preferred provider — no rate limit issues like Mistral free tier.
    """

    def __init__(self, config=None) -> None:
        self.cfg = config or settings()
        from openai import OpenAI
        self.client = OpenAI(
            api_key=self.cfg.nvidia_api_key,
            base_url=self.cfg.nvidia_base_url,
        )

    def extract_all(self, messages: list[dict[str, Any]]) -> list[TaskExtraction]:
        if not messages:
            return []

        conversation_text = _build_conversation_text(messages)
        logger.info("Sending %d messages to NVIDIA NIM (%s) for batch extraction.",
                    len(messages), self.cfg.nvidia_model)
        logger.debug("Conversation:\n%s", conversation_text)

        try:
            response = self.client.chat.completions.create(
                model=self.cfg.nvidia_model,
                messages=[
                    {"role": "system", "content": TASK_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract tasks from these WhatsApp messages:\n\n{conversation_text}"},
                ],
                temperature=0.1,
                max_tokens=4096,
            )
            raw = response.choices[0].message.content
            logger.debug("NVIDIA raw response:\n%s", raw)
            payload_list = _parse_response(raw)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                raise RateLimitError(f"NVIDIA NIM rate limit: {e}") from e
            logger.error("NVIDIA NIM batch call failed: %s", e)
            return []

        return _to_task_extractions(payload_list, len(messages), "NVIDIA")


# ── Mistral (fallback) ────────────────────────────────────────────────────────

class MistralBatchExtractor:
    """Fallback: uses Mistral API directly."""

    def __init__(self, config=None) -> None:
        self.cfg = config or settings()
        try:
            from mistralai import Mistral
        except ImportError:
            from mistralai.client.sdk import Mistral
        self.client = Mistral(api_key=self.cfg.mistral_api_key) if self.cfg.mistral_api_key else None

    def extract_all(self, messages: list[dict[str, Any]]) -> list[TaskExtraction]:
        if not self.client:
            raise RuntimeError("MISTRAL_API_KEY not set.")
        if not messages:
            return []

        conversation_text = _build_conversation_text(messages)
        logger.info("Sending %d messages to Mistral for batch extraction.", len(messages))

        try:
            response = self.client.chat.complete(
                model=self.cfg.mistral_model,
                messages=[
                    {"role": "system", "content": TASK_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract tasks from these WhatsApp messages:\n\n{conversation_text}"},
                ],
                temperature=0.1,
            )
            raw = response.choices[0].message.content
            payload_list = _parse_response(raw)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower():
                raise RateLimitError(f"Mistral rate limit: {e}") from e
            logger.error("Mistral batch call failed: %s", e)
            return []

        return _to_task_extractions(payload_list, len(messages), "Mistral")
