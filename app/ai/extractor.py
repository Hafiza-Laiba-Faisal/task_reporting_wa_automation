from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.ai.schemas import TaskExtraction
from app.config import settings
from app.logger import get_logger

logger = get_logger("extractor")


class LLMTaskExtractor:
    """
    Batch extractor: sends ALL messages together to Mistral in one API call
    so the LLM understands full conversation context.
    Falls back to rule-based extraction if API key is not set.
    """

    def __init__(self, config=None) -> None:
        self.cfg = config or settings()
        self._client = None

        provider = self.cfg.llm_provider  # nvidia | mistral | openai

        if provider == "nvidia" and self.cfg.nvidia_api_key:
            try:
                from app.ai.mistral_client import NvidiaBatchExtractor
                self._client = NvidiaBatchExtractor(self.cfg)
                logger.info("Using NVIDIA NIM (model: %s)", self.cfg.nvidia_model)
            except Exception as e:
                logger.warning("NVIDIA init failed: %s", e)

        elif provider == "openai" and self.cfg.openai_api_key:
            try:
                from app.ai.mistral_client import NvidiaBatchExtractor
                # OpenAI uses same interface — just different base_url (None = default)
                self._client = NvidiaBatchExtractor(self.cfg)
                logger.info("Using OpenAI (model: %s)", self.cfg.openai_model)
            except Exception as e:
                logger.warning("OpenAI init failed: %s", e)

        elif provider == "mistral" and self.cfg.mistral_api_key:
            try:
                from app.ai.mistral_client import MistralBatchExtractor
                self._client = MistralBatchExtractor(self.cfg)
                logger.info("Using Mistral (model: %s)", self.cfg.mistral_model)
            except Exception as e:
                logger.warning("Mistral init failed: %s", e)

        # Auto-fallback chain if preferred provider failed
        if self._client is None:
            for fallback_provider, init_fn in [
                ("nvidia",  self._try_nvidia),
                ("mistral", self._try_mistral),
            ]:
                if fallback_provider != provider:
                    client = init_fn()
                    if client:
                        self._client = client
                        break

        if self._client is None:
            logger.warning("No LLM configured — using rule-based fallback")

    def _try_nvidia(self):
        if self.cfg.nvidia_api_key:
            try:
                from app.ai.mistral_client import NvidiaBatchExtractor
                c = NvidiaBatchExtractor(self.cfg)
                logger.info("Fallback: using NVIDIA NIM")
                return c
            except Exception:
                pass
        return None

    def _try_mistral(self):
        if self.cfg.mistral_api_key:
            try:
                from app.ai.mistral_client import MistralBatchExtractor
                c = MistralBatchExtractor(self.cfg)
                logger.info("Fallback: using Mistral")
                return c
            except Exception:
                pass
        return None

    def extract_batch(self, messages: list[dict[str, Any]]) -> list[TaskExtraction]:
        """Process all messages at once and return extracted tasks."""
        if self._client:
            return self._client.extract_all(messages)
        return _RuleBasedExtractor().extract_batch(messages)

    def extract(self, message: dict[str, Any]) -> TaskExtraction | None:
        """Single-message extraction (used as fallback compatibility)."""
        results = self.extract_batch([message])
        return results[0] if results else None


class _RuleBasedExtractor:
    """Simple heuristic fallback when no LLM is available."""

    _TASK_KEYWORDS = [
        "working on", "kam kar", "kaam kar", "complete", "done", "finish",
        "please", "send", "check", "review", "prepare", "update", "call",
        "invoice", "report", "creative", "design", "post", "carousel",
        "need", "must", "follow up", "confirm", "schedule",
    ]

    def extract_batch(self, messages: list[dict[str, Any]]) -> list[TaskExtraction]:
        results = []
        for msg in messages:
            result = self._extract_single(msg)
            if result:
                results.append(result)
        return results

    def _extract_single(self, message: dict[str, Any]) -> TaskExtraction | None:
        text = message.get("message_text_normalized", "")
        if not text or len(text) < 5:
            return None

        lower = text.lower()
        if not any(kw in lower for kw in self._TASK_KEYWORDS):
            return None

        if re.search(r"\b(complete|done|finish|kar diya|ho gaya)\b", lower):
            status = "completed"
        elif re.search(r"\b(working on|kaam kar|kam kar|i am working)\b", lower):
            status = "in_progress"
        else:
            status = "open"

        priority = "high" if re.search(r"\b(urgent|asap|immediately|jaldi)\b", lower) else "medium"
        deadline = None
        if re.search(r"\b(today|aaj|kal|tomorrow|friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b", lower, re.I):
            deadline = datetime.utcnow().isoformat(timespec="seconds")

        return TaskExtraction.model_validate({
            "task": text[:200],
            "assignee": message.get("sender"),
            "deadline": deadline,
            "priority": priority,
            "status": status,
            "source_message": text,
            "sender": message.get("sender", "unknown"),
            "message_timestamp": message.get("message_timestamp", datetime.utcnow().isoformat(timespec="seconds")),
            "confidence": 0.75,
        })
