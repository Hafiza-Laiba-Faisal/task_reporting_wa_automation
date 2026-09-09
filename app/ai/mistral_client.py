from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

try:
    from mistralai import Mistral  # v1 style
except ImportError:
    from mistralai.client.sdk import Mistral  # v2 style (namespace package)

from app.ai.prompts import TASK_EXTRACTION_SYSTEM_PROMPT
from app.ai.schemas import TaskExtraction
from app.config import settings
from app.logger import get_logger

logger = get_logger("mistral_client")


class RateLimitError(Exception):
    """Raised when Mistral API returns 429 rate limit."""
    pass


class MistralBatchExtractor:
    """
    Sends ALL messages from today to Mistral in a single API call.
    Mistral reads the full conversation context and returns a list of tasks.
    """

    def __init__(self, config=None) -> None:
        self.cfg = config or settings()
        self.client = Mistral(api_key=self.cfg.mistral_api_key) if self.cfg.mistral_api_key else None

    def _build_conversation_text(self, messages: list[dict[str, Any]]) -> str:
        today = date.today().strftime("%d %b %Y")
        lines = [f"Date: {today}", ""]
        for msg in messages:
            sender = msg.get("sender", "unknown")
            timestamp = msg.get("message_timestamp", "")
            text = msg.get("message_text_normalized", "").strip()
            if text:
                lines.append(f"[{timestamp}] {sender}: {text}")
        return "\n".join(lines)

    def _parse_response(self, raw: str) -> list[dict]:
        """Extract JSON array from LLM response — handles markdown code fences."""
        clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        # Sometimes LLM wraps in object instead of array
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            # e.g. {"tasks": [...]}
            for key in ("tasks", "task_list", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            return [parsed]
        return parsed  # already a list

    def extract_all(self, messages: list[dict[str, Any]]) -> list[TaskExtraction]:
        """Process all messages together and return list of extracted tasks."""
        if not self.client:
            raise RuntimeError("Mistral API key is missing. Set MISTRAL_API_KEY in .env")

        if not messages:
            return []

        conversation_text = self._build_conversation_text(messages)
        logger.info("Sending %d messages to Mistral for batch extraction.", len(messages))
        logger.debug("Conversation text:\n%s", conversation_text)

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
            logger.debug("Mistral raw response:\n%s", raw)
            payload_list = self._parse_response(raw)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower() or "rate limit" in error_str.lower():
                logger.error("Mistral rate limit hit. Wait a few minutes and try again. Error: %s", e)
                raise RateLimitError("Mistral API rate limit exceeded. Please wait and retry.") from e
            logger.error("Mistral batch call failed: %s", e)
            return []

        tasks: list[TaskExtraction] = []
        for item in payload_list:
            if not item.get("task"):
                continue

            # Normalize field names — LLM sometimes uses slightly different keys
            normalized = {
                "task": item.get("task", ""),
                "assignee": item.get("assignee") or item.get("assigned_to"),
                "deadline": item.get("deadline"),
                "priority": item.get("priority", "medium"),
                "status": item.get("status", "in_progress"),
                "source_message": item.get("source_message", ""),
                "sender": item.get("source_sender") or item.get("sender", "unknown"),
                "message_timestamp": item.get("message_timestamp", ""),
                "confidence": item.get("confidence", 0.85),
            }

            # Sanitize priority and status to allowed values
            allowed_priorities = {"low", "medium", "high", "urgent"}
            allowed_statuses = {"open", "in_progress", "completed", "blocked", "review"}
            if normalized["priority"] not in allowed_priorities:
                normalized["priority"] = "medium"
            if normalized["status"] not in allowed_statuses:
                normalized["status"] = "open"

            try:
                tasks.append(TaskExtraction.model_validate(normalized))
            except Exception as e:
                logger.warning("Validation failed for task item: %s | item: %s", e, item)

        logger.info("Mistral extracted %d tasks from %d messages.", len(tasks), len(messages))
        return tasks
