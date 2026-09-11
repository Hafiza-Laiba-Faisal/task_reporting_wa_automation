from __future__ import annotations

import re
from datetime import date, datetime, timedelta
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

    # ── Public ────────────────────────────────────────────────────────────────

    def collect(self) -> list[dict[str, Any]]:
        """
        Scroll up enough to load TARGET_WINDOW_DAYS worth of messages,
        then collect ALL visible messages. Duplicates are skipped via
        message_fingerprint. Each message gets the actual calendar date
        attached (derived from WhatsApp date dividers).
        """
        self._scroll_to_load_history()

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
            return []

        # Build a date map: approximate which calendar date each message belongs to
        # by scanning the full page text for WhatsApp date dividers.
        date_map = self._build_date_map()

        existing_fps = existing_message_fingerprints()
        collected: list[dict[str, Any]] = []
        skipped_dup = 0

        total = min(all_rows.count(), self.cfg.max_messages_per_run)
        for i in range(total):
            row = all_rows.nth(i)
            text = (row.inner_text() or "").strip()
            if not text:
                continue

            sender, message_text = self._extract_sender_and_text(text)
            timestamp = self._extract_timestamp(text)
            if not sender or not message_text:
                continue

            sender = self.cfg.resolve_sender_name(sender)

            # Determine message date from divider map
            msg_date = self._resolve_date_for_message(text, timestamp, date_map)

            fp = message_fingerprint(sender, message_text, timestamp, self.cfg.whatsapp_group_name)
            if fp in existing_fps:
                skipped_dup += 1
                continue

            record = {
                "run_id":                   self.run_id,
                "group_name":               self.cfg.whatsapp_group_name,
                "sender":                   sender,
                "message_text_raw":         text,
                "message_text_normalized":  message_text,
                "message_timestamp":        timestamp,
                "message_date":             msg_date,        # YYYY-MM-DD
                "message_fingerprint":      fp,
                "processed_at":             datetime.now().isoformat(timespec="seconds"),
                "status":                   "new",
            }
            collected.append(record)
            existing_fps.add(fp)
            upsert_message(record)

        logger.info(
            "Collected %d new messages. Skipped %d duplicates.",
            len(collected), skipped_dup
        )
        return collected

    # ── Scroll history ────────────────────────────────────────────────────────

    def _scroll_to_load_history(self) -> None:
        """
        Scroll up in the chat panel to load messages from the last
        TARGET_WINDOW_DAYS days. WhatsApp lazy-loads older messages.
        """
        days = self.cfg.target_window_days
        logger.info("Scrolling up to load %d day(s) of history...", days)

        panel_sel = "div[data-testid='conversation-panel-messages']"
        try:
            panel = self.page.locator(panel_sel)
            # Scroll up several times to trigger lazy-load
            for _ in range(max(3, days * 2)):
                panel.evaluate("el => el.scrollTop = 0")
                self.page.wait_for_timeout(600)
        except Exception as e:
            logger.warning("Scroll attempt failed: %s", e)

    # ── Date divider map ──────────────────────────────────────────────────────

    def _build_date_map(self) -> dict[str, str]:
        """
        Parse WhatsApp date dividers from the page to build a mapping:
          divider_text_lower → YYYY-MM-DD

        WhatsApp shows dividers like:
          "Today", "Yesterday", "10 Sep 2026", "8 Sep 2026"
        """
        today = date.today()
        mapping: dict[str, str] = {
            "today":     today.isoformat(),
            "yesterday": (today - timedelta(days=1)).isoformat(),
        }

        try:
            dividers = self.page.locator("div[data-testid='msg-date-divider']")
            for i in range(dividers.count()):
                txt = (dividers.nth(i).inner_text() or "").strip()
                lower = txt.lower()
                if lower in mapping:
                    continue
                # Try parsing "10 Sep 2026" or "Sep 10, 2026" etc.
                parsed = self._parse_date_string(txt)
                if parsed:
                    mapping[lower] = parsed
        except Exception as e:
            logger.debug("Date divider scan failed: %s", e)

        logger.debug("Date map built: %s", mapping)
        return mapping

    def _parse_date_string(self, text: str) -> str | None:
        """Try to parse a date string like '10 Sep 2026' → '2026-09-10'."""
        formats = [
            "%d %b %Y",   # 10 Sep 2026
            "%d %B %Y",   # 10 September 2026
            "%B %d, %Y",  # September 10, 2026
            "%b %d, %Y",  # Sep 10, 2026
            "%d/%m/%Y",   # 10/09/2026
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def _resolve_date_for_message(
        self,
        text: str,
        timestamp: str,
        date_map: dict[str, str],
    ) -> str:
        """
        Best-effort: return YYYY-MM-DD for a message.
        We can't reliably tie every message to a divider without DOM
        position info, so we use today's date as default and let
        the pipeline pass the WhatsApp-scrolled date from dividers
        when it can be inferred.
        """
        # If text contains a recognizable date divider, use it
        lower = text.lower()
        for key, iso_date in date_map.items():
            if key in lower:
                return iso_date
        # Default: today
        return date_map.get("today", date.today().isoformat())

    # ── Parsing helpers ───────────────────────────────────────────────────────

    def _extract_sender_and_text(self, text: str) -> tuple[str | None, str | None]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None, None
        sender = None
        body = []
        for line in lines:
            if not sender and re.match(r"^[A-Za-z0-9 _.+()-]+$", line) and len(line) <= 40:
                sender = line
                continue
            body.append(line)
        final_text = " ".join(body).strip()
        if not final_text:
            return None, None
        return sender or "unknown", final_text

    def _extract_timestamp(self, text: str) -> str:
        match = re.search(r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b", text)
        if not match:
            return datetime.now().strftime("%H:%M")
        return match.group(0).strip()
