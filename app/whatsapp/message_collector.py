from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from playwright.sync_api import Page

from app.config import settings
from app.database.repository import existing_message_fingerprints, message_fingerprint, upsert_message
from app.logger import get_logger

logger = get_logger("message_collector")

# ── Selectors ─────────────────────────────────────────────────────────────────
_PANEL_SEL    = "div[data-testid='conversation-panel-messages']"
_DIVIDER_SEL  = "div[data-testid='msg-date-divider']"
_MSG_SELS     = [
    "div[data-testid='msg-container']",
    "div.message-in, div.message-out",
    "div[role='row']",
]


class MessageCollector:
    def __init__(self, page: Page, run_id: str) -> None:
        self.page    = page
        self.run_id  = run_id
        self.cfg     = settings()

    # ── Public ────────────────────────────────────────────────────────────────

    def collect(self) -> list[dict[str, Any]]:
        """
        1. Scroll up until target date divider is visible (or max attempts)
        2. Build date map from all visible dividers
        3. Walk every message row top-to-bottom, tagging each with its date
        4. Save new messages to DB (skip duplicates via fingerprint)
        """
        target_date = date.today() - timedelta(days=self.cfg.target_window_days - 1)
        logger.info(
            "Collecting messages back to %s (%d days)",
            target_date.isoformat(), self.cfg.target_window_days
        )

        # ── Step 1: scroll until target date visible ──────────────────────────
        self._scroll_until_date_visible(target_date)

        # ── Step 2: build date divider → YYYY-MM-DD map ───────────────────────
        date_map = self._build_date_map()
        logger.info("Date dividers found: %s", list(date_map.values()))

        # ── Step 3: find message rows ─────────────────────────────────────────
        all_rows = self._find_message_rows()
        if all_rows is None:
            logger.warning("No message rows found.")
            return []

        total = min(all_rows.count(), self.cfg.max_messages_per_run)
        logger.info("Processing %d visible message rows.", total)

        # ── Step 4: collect each row with proper date ─────────────────────────
        existing_fps  = existing_message_fingerprints()
        collected:    list[dict[str, Any]] = []
        skipped_dup   = 0
        current_date  = date.today().isoformat()   # fallback until first divider seen

        for i in range(total):
            row  = all_rows.nth(i)
            text = (row.inner_text() or "").strip()
            if not text:
                continue

            # Check if this row IS a date divider (update current_date)
            maybe_date = self._check_if_divider(text, date_map)
            if maybe_date:
                current_date = maybe_date
                logger.debug("Date changed to: %s", current_date)
                continue

            sender, message_text = self._extract_sender_and_text(text)
            if not sender or not message_text:
                continue

            sender    = self.cfg.resolve_sender_name(sender)
            timestamp = self._extract_timestamp(text)

            fp = message_fingerprint(sender, message_text, timestamp, self.cfg.whatsapp_group_name)
            if fp in existing_fps:
                skipped_dup += 1
                continue

            record = {
                "run_id":                  self.run_id,
                "group_name":              self.cfg.whatsapp_group_name,
                "sender":                  sender,
                "message_text_raw":        text,
                "message_text_normalized": message_text,
                "message_timestamp":       timestamp,
                "message_date":            current_date,
                "message_fingerprint":     fp,
                "processed_at":            datetime.now().isoformat(timespec="seconds"),
                "status":                  "new",
            }
            collected.append(record)
            existing_fps.add(fp)
            upsert_message(record)

        logger.info(
            "Collected %d new messages | Skipped %d duplicates.",
            len(collected), skipped_dup
        )
        return collected

    # ── Scroll until target date visible ──────────────────────────────────────

    def _scroll_until_date_visible(self, target_date: date) -> None:
        """
        Keep scrolling up until target date divider visible or top of chat reached.
        Each scroll waits for new messages to actually render before checking.
        """
        MAX_ATTEMPTS  = 40
        PAUSE_MS      = 1500   # after each scroll, wait for WhatsApp to render new messages
        panel         = self.page.locator(_PANEL_SEL)

        # Initial settle — let WhatsApp fully render current messages
        logger.info("Waiting 4s for chat messages to fully render...")
        self.page.wait_for_timeout(4000)

        # Log what's visible before we start
        initial_msgs = self.page.locator("div[data-testid='msg-container']").count()
        logger.info("Messages visible before scrolling: %d", initial_msgs)
        logger.info("Scrolling to load history (target: %s, max %d scrolls)...",
                    target_date.isoformat(), MAX_ATTEMPTS)

        prev_height   = -1
        no_change_cnt = 0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Check if target date divider is already on screen
            if self._date_divider_visible(target_date):
                logger.info("Target date divider found after %d scrolls.", attempt)
                return

            # Scroll to absolute top of panel
            try:
                panel.evaluate("el => { el.scrollTop = 0; }")
            except Exception:
                pass

            # Wait for WhatsApp to lazy-load older messages
            self.page.wait_for_timeout(PAUSE_MS)

            # Check if scroll height grew (new messages loaded)
            try:
                cur_height = panel.evaluate("el => el.scrollHeight")
                cur_msgs   = self.page.locator("div[data-testid='msg-container']").count()
            except Exception:
                cur_height = prev_height
                cur_msgs   = 0

            if cur_height == prev_height:
                no_change_cnt += 1
                if no_change_cnt >= 4:
                    logger.info(
                        "scrollHeight unchanged for %d scrolls (height=%d) — reached top of chat.",
                        no_change_cnt, cur_height
                    )
                    return
            else:
                no_change_cnt = 0
                logger.debug("Scroll %d: height %d→%d | msgs: %d",
                             attempt, prev_height, cur_height, cur_msgs)

            prev_height = cur_height

            if attempt % 5 == 0:
                dividers = self._visible_dividers()
                logger.info("Scroll %d/%d | height=%d | msgs=%d | dividers=%s",
                            attempt, MAX_ATTEMPTS, cur_height, cur_msgs, dividers)

        logger.warning("Max scroll attempts (%d) reached. Collecting what's visible.", MAX_ATTEMPTS)

    def _date_divider_visible(self, target_date: date) -> bool:
        """Return True if any divider on screen matches target_date or earlier."""
        try:
            dividers = self.page.locator(_DIVIDER_SEL)
            for i in range(dividers.count()):
                txt = (dividers.nth(i).inner_text() or "").strip()
                parsed = self._parse_date_string(txt)
                if parsed:
                    d = date.fromisoformat(parsed)
                    if d <= target_date:
                        return True
                if txt.lower() in ("today", "yesterday"):
                    pass  # these are always recent, keep scrolling
        except Exception:
            pass
        return False

    def _visible_dividers(self) -> list[str]:
        """Return text of all visible date dividers."""
        result = []
        try:
            dividers = self.page.locator(_DIVIDER_SEL)
            for i in range(dividers.count()):
                txt = (dividers.nth(i).inner_text() or "").strip()
                if txt:
                    result.append(txt)
        except Exception:
            pass
        return result

    # ── Date map builder ──────────────────────────────────────────────────────

    def _build_date_map(self) -> dict[str, str]:
        """
        Returns {divider_text_lower: YYYY-MM-DD} for all visible dividers.
        """
        today = date.today()
        mapping: dict[str, str] = {
            "today":     today.isoformat(),
            "yesterday": (today - timedelta(days=1)).isoformat(),
        }
        try:
            dividers = self.page.locator(_DIVIDER_SEL)
            for i in range(dividers.count()):
                txt   = (dividers.nth(i).inner_text() or "").strip()
                lower = txt.lower()
                if lower not in mapping:
                    parsed = self._parse_date_string(txt)
                    if parsed:
                        mapping[lower] = parsed
        except Exception as e:
            logger.debug("Date map build error: %s", e)
        return mapping

    def _check_if_divider(self, text: str, date_map: dict[str, str]) -> str | None:
        """If row text matches a date divider, return its YYYY-MM-DD else None."""
        lower = text.strip().lower()
        # Exact match first
        if lower in date_map:
            return date_map[lower]
        # Try parsing the text directly
        parsed = self._parse_date_string(text.strip())
        if parsed:
            return parsed
        return None

    # ── Message row finder ────────────────────────────────────────────────────

    def _find_message_rows(self):
        for sel in _MSG_SELS:
            try:
                loc = self.page.locator(sel)
                if loc.count():
                    logger.info("Using selector '%s' (%d rows)", sel, loc.count())
                    return loc
            except Exception:
                continue
        return None

    # ── Parsing helpers ───────────────────────────────────────────────────────

    def _parse_date_string(self, text: str) -> str | None:
        """'10 Sep 2026' → '2026-09-10'"""
        for fmt in ("%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def _extract_sender_and_text(self, text: str) -> tuple[str | None, str | None]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return None, None
        sender = None
        body   = []
        for line in lines:
            if not sender and re.match(r"^[A-Za-z0-9 _.+()\-]+$", line) and len(line) <= 40:
                sender = line
                continue
            body.append(line)
        final = " ".join(body).strip()
        if not final:
            return None, None
        return sender or "unknown", final

    def _extract_timestamp(self, text: str) -> str:
        m = re.search(r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b", text)
        return m.group(0).strip() if m else datetime.now().strftime("%H:%M")
