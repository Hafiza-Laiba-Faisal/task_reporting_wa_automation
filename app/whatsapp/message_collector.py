from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from playwright.sync_api import Page

from app.config import settings
from app.database.repository import existing_message_fingerprints, message_fingerprint, upsert_message
from app.logger import get_logger

logger = get_logger("message_collector")

_PANEL_SEL   = "div[data-testid='conversation-panel-messages']"
_DIVIDER_SEL = "div[data-testid='msg-date-divider']"
_MSG_SELS    = [
    "div[data-testid='msg-container']",
    "div.message-in, div.message-out",
    "div[role='row']",
]


class MessageCollector:
    def __init__(self, page: Page, run_id: str) -> None:
        self.page   = page
        self.run_id = run_id
        self.cfg    = settings()

    # ── Public ────────────────────────────────────────────────────────────────

    def collect(self) -> list[dict[str, Any]]:
        target_date = date.today() - timedelta(days=self.cfg.target_window_days - 1)
        logger.info("Collecting messages back to %s (%d days)",
                    target_date.isoformat(), self.cfg.target_window_days)

        self._scroll_until_date_visible(target_date)

        date_map  = self._build_date_map()
        all_rows  = self._find_message_rows()
        if all_rows is None:
            logger.warning("No message rows found.")
            return []

        total = min(all_rows.count(), self.cfg.max_messages_per_run)
        logger.info("Processing %d message rows.", total)

        existing_fps = existing_message_fingerprints()
        collected: list[dict[str, Any]] = []
        skipped_dup  = 0
        current_date = date_map.get("today", date.today().isoformat())

        for i in range(total):
            row  = all_rows.nth(i)
            text = (row.inner_text() or "").strip()
            if not text:
                continue

            maybe_date = self._check_if_divider(text, date_map)
            if maybe_date:
                current_date = maybe_date
                logger.debug("Date divider: %s", current_date)
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

        logger.info("Collected %d new | Skipped %d duplicates.", len(collected), skipped_dup)
        return collected

    # ── Scroll ────────────────────────────────────────────────────────────────

    def _scroll_panel(self) -> None:
        """Scroll the chat panel to top using JS on the element."""
        try:
            self.page.evaluate(f"""() => {{
                const el = document.querySelector('{_PANEL_SEL}');
                if (el) el.scrollTop = 0;
            }}""")
        except Exception:
            pass

    def _get_scroll_height(self) -> int:
        try:
            return int(self.page.evaluate(f"""() => {{
                const el = document.querySelector('{_PANEL_SEL}');
                return el ? el.scrollHeight : 0;
            }}""") or 0)
        except Exception:
            return 0

    def _wait_stable_msgs(self, max_wait_ms: int = 3000) -> int:
        """Wait until msg-container count stops changing. Returns stable count."""
        prev  = -1
        steps = max_wait_ms // 400
        for _ in range(steps):
            try:
                cur = self.page.locator("div[data-testid='msg-container']").count()
            except Exception:
                break
            if cur == prev:
                return cur
            prev = cur
            self.page.wait_for_timeout(400)
        return prev if prev >= 0 else 0

    def _scroll_until_date_visible(self, target_date: date) -> None:
        """
        Scroll up until:
        - target date divider appears on screen, OR
        - scrollHeight stops growing (genuinely at top of chat)
        Uses document.querySelector scroll (not locator.evaluate) to avoid
        Playwright timeout when panel scrolls out of viewport.
        """
        MAX_ATTEMPTS = 40

        logger.info("Waiting 4s for initial messages to render...")
        self.page.wait_for_timeout(4000)

        initial = self._wait_stable_msgs()
        logger.info("Messages visible before scrolling: %d", initial)
        logger.info("Scrolling to load history (target: %s, max %d scrolls)...",
                    target_date.isoformat(), MAX_ATTEMPTS)

        prev_height   = -1
        no_change_cnt = 0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Check full page text for date strings (works even with virtual DOM)
            if self._date_visible_in_page(target_date):
                logger.info("Target date %s found in page after %d scrolls.",
                            target_date.isoformat(), attempt)
                self.page.wait_for_timeout(1000)  # let rendering settle
                return

            self._scroll_panel()
            self.page.wait_for_timeout(2000)  # let WhatsApp lazy-load
            stable = self._wait_stable_msgs()
            cur_height = self._get_scroll_height()

            if cur_height == prev_height:
                no_change_cnt += 1
                if no_change_cnt >= 4:
                    logger.info("scrollHeight stable at %d for %d scrolls — reached top.",
                                cur_height, no_change_cnt)
                    return
            else:
                no_change_cnt = 0

            prev_height = cur_height

            if attempt % 3 == 0:
                dates_seen = self._dates_in_page()
                logger.info("Scroll %d/%d | height=%d | msgs=%d | dates_on_page=%s",
                            attempt, MAX_ATTEMPTS, cur_height, stable, dates_seen)

        logger.warning("Max scrolls (%d) reached.", MAX_ATTEMPTS)

    # ── Date detection ────────────────────────────────────────────────────────

    def _dates_in_page(self) -> list[str]:
        """Scan full page text for date strings like '11 Sep 2026'."""
        try:
            text = self.page.inner_text("body") or ""
            matches = re.findall(
                r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b',
                text, re.IGNORECASE
            )
            results = []
            for day, mon, year in matches:
                parsed = self._parse_date_string(f"{day} {mon[:3].capitalize()} {year}")
                if parsed and parsed not in results:
                    results.append(parsed)
            return sorted(set(results))
        except Exception:
            return []

    def _date_visible_in_page(self, target_date: date) -> bool:
        """Return True if target_date or any earlier date is visible on page."""
        for d_str in self._dates_in_page():
            try:
                if date.fromisoformat(d_str) <= target_date:
                    return True
            except Exception:
                pass
        # Also check WhatsApp divider elements directly
        try:
            dividers = self.page.locator(_DIVIDER_SEL)
            for i in range(dividers.count()):
                txt    = (dividers.nth(i).inner_text() or "").strip()
                parsed = self._parse_date_string(txt)
                if parsed:
                    if date.fromisoformat(parsed) <= target_date:
                        return True
        except Exception:
            pass
        return False

    def _build_date_map(self) -> dict[str, str]:
        """Build {text_lower: YYYY-MM-DD} from dividers + full page scan."""
        today = date.today()
        mapping: dict[str, str] = {
            "today":     today.isoformat(),
            "yesterday": (today - timedelta(days=1)).isoformat(),
        }

        # WhatsApp divider elements
        try:
            dividers = self.page.locator(_DIVIDER_SEL)
            for i in range(dividers.count()):
                txt   = (dividers.nth(i).inner_text() or "").strip()
                lower = txt.lower()
                if lower not in mapping:
                    parsed = self._parse_date_string(txt)
                    if parsed:
                        mapping[lower] = parsed
        except Exception:
            pass

        # Full page scan fallback
        for iso in self._dates_in_page():
            try:
                d = date.fromisoformat(iso)
                label = d.strftime("%-d %b %Y").lower()
                if label not in mapping:
                    mapping[label] = iso
            except Exception:
                pass

        logger.info("Date map built: %s", sorted(mapping.values()))
        return mapping

    def _check_if_divider(self, text: str, date_map: dict[str, str]) -> str | None:
        lower = text.strip().lower()
        if lower in date_map:
            return date_map[lower]
        parsed = self._parse_date_string(text.strip())
        if parsed:
            return parsed
        return None

    def _date_divider_visible(self, target_date: date) -> bool:
        return self._date_visible_in_page(target_date)

    def _visible_dividers(self) -> list[str]:
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

    # ── Row finder ────────────────────────────────────────────────────────────

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

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_date_string(self, text: str) -> str | None:
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
