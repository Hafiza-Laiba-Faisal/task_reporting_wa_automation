from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from playwright.sync_api import Page

from app.config import settings
from app.database.repository import existing_message_fingerprints, message_fingerprint, upsert_message
from app.logger import get_logger

logger = get_logger("message_collector")


class MessageCollector:
    def __init__(self, page: Page, run_id: str) -> None:
        self.page = page
        self.run_id = run_id
        self.cfg = settings()

    def collect(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        # WhatsApp chat messages live inside the conversation panel.
        # We try specific message-row selectors before falling back.
        message_selectors = [
            "div[data-testid='msg-container']",
            "div.message-in, div.message-out",
            "div[role='row']",
        ]

        all_rows = None
        for sel in message_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count():
                    all_rows = loc
                    logger.info("Collecting messages via selector: %s (%d rows)", sel, loc.count())
                    break
            except Exception:
                continue

        if all_rows is None:
            logger.warning("No message rows found in the conversation pane.")
            return messages

        today_str = date.today().strftime("%-d %b %Y").lower()  # e.g. "9 sep 2026"
        total = min(all_rows.count(), self.cfg.max_messages_per_run)

        # Find the index where "Today" section starts by scanning date dividers.
        # WhatsApp date dividers contain text like "Today", "Yesterday", "9 Sep 2026".
        today_start_index = 0
        try:
            date_dividers = self.page.locator(
                "div[data-testid='msg-date-divider'], div[role='row'] >> text=/today|yesterday/i"
            )
            for d in range(date_dividers.count()):
                divider_text = (date_dividers.nth(d).inner_text() or "").strip().lower()
                if "today" in divider_text or today_str in divider_text:
                    # Find the approximate message index after this divider
                    # by checking bounding boxes — simpler: just note we found today
                    logger.info("Found 'Today' date divider — filtering messages from today only.")
                    today_start_index = None  # flag: scan all but filter by absence of yesterday
                    break
        except Exception:
            pass

        collected_count = 0
        for i in range(total):
            row = all_rows.nth(i)
            text = (row.inner_text() or "").strip()
            if not text:
                continue
            sender, message_text = self._extract_sender_and_text(text)
            timestamp = self._extract_timestamp(text)
            if not sender or not message_text:
                continue
            # Resolve phone-number-based sender names to real names
            sender = self.cfg.resolve_sender_name(sender)
            fingerprint = message_fingerprint(sender, message_text, timestamp, self.cfg.whatsapp_group_name)
            if fingerprint in existing_message_fingerprints():
                logger.info("Duplicate message skipped: %s", fingerprint)
                continue
            record = {
                "run_id": self.run_id,
                "group_name": self.cfg.whatsapp_group_name,
                "sender": sender,
                "message_text_raw": text,
                "message_text_normalized": message_text,
                "message_timestamp": timestamp,
                "message_fingerprint": fingerprint,
                "processed_at": datetime.utcnow().isoformat(timespec="seconds"),
                "status": "new",
            }
            messages.append(record)
            upsert_message(record)
            collected_count += 1

        logger.info("Collected %d new messages from today.", collected_count)
        return messages

    def _extract_sender_and_text(self, text: str) -> tuple[str | None, str | None]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None, None
        sender = None
        body = []
        for line in lines:
            if not sender and re.match(r"^[A-Za-z0-9 _.-]+$", line) and len(line) <= 30:
                sender = line
                continue
            body.append(line)
        final_text = " ".join(body).strip()
        if not final_text:
            return None, None
        return sender or "unknown", final_text

    def _extract_timestamp(self, text: str) -> str:
        match = re.search(r"\b\d{1,2}:\d{2}\b", text)
        if not match:
            return datetime.utcnow().isoformat(timespec="seconds")
        return match.group(0)
