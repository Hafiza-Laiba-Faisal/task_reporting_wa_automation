from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from app.config import settings
from app.logger import get_logger

logger = get_logger("group_finder")


class GroupSelectionError(RuntimeError):
    pass


class GroupFinder:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.cfg = settings()

    def search_group(self, timeout_seconds: int | None = None) -> str:
        selector = "input[placeholder*='Search'], input[aria-label*='Search']"
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        while True:
            try:
                if self.page.locator(selector).count() and self.page.locator(selector).first.is_visible():
                    search_box = self.page.locator(selector).first
                    search_box.fill(self.cfg.whatsapp_group_name)
                    logger.info("Searching for configured group: %s", self.cfg.whatsapp_group_name)
                    # Give WhatsApp a moment to load search results before we read them
                    time.sleep(2)
                    return self.cfg.whatsapp_group_name
            except Exception:
                pass
            if deadline is not None and time.monotonic() >= deadline:
                raise GroupSelectionError(
                    f"WhatsApp search box did not become visible within {timeout_seconds} seconds."
                )
            logger.info("Waiting for WhatsApp search box to become visible before continuing.")
            time.sleep(2)

    # Selectors for the individual chat/group row containers.
    _ROW_SELECTORS = [
        "div[data-testid='cell-frame-container']",
        "li[data-testid='cell-frame-container']",
        "div[role='option']",
        "div[role='listitem']",
        "div[role='row']",
    ]

    # Within each row, these child selectors point to the title/name element.
    # We try each in order and use the first non-empty text we find.
    _TITLE_SELECTORS = [
        "span[data-testid='cell-frame-title']",
        "span[title]",
        "div[data-testid='cell-frame-title']",
        "span[dir='auto']",
    ]

    def _row_title(self, row_locator) -> str:
        """Extract only the group/chat name from a row element."""
        for title_sel in self._TITLE_SELECTORS:
            try:
                child = row_locator.locator(title_sel).first
                if child.count() and child.is_visible():
                    title = (child.get_attribute("title") or child.inner_text() or "").strip()
                    if title:
                        return title
            except Exception:
                continue
        # Last resort: first line of inner_text (name is always first line)
        try:
            text = (row_locator.inner_text() or "").strip()
            first_line = text.splitlines()[0].strip() if text else ""
            return first_line
        except Exception:
            return ""

    def find_group_candidates(self) -> list[str]:
        """Poll for chat / search-result items and return their title labels."""
        deadline = time.monotonic() + int(self.cfg.max_group_search_wait_seconds)
        while True:
            for sel in self._ROW_SELECTORS:
                try:
                    results = self.page.locator(sel)
                    count = results.count()
                    if count:
                        candidates: list[str] = []
                        for i in range(min(count, 40)):
                            try:
                                title = self._row_title(results.nth(i))
                            except Exception:
                                title = ""
                            if title:
                                candidates.append(title)
                        if candidates:
                            logger.info(
                                "Candidate titles found via '%s': %s — %s",
                                sel, len(candidates), candidates[:5],
                            )
                            return candidates
                except Exception:
                    logger.debug("Exception while reading selector '%s'; will retry.", sel)

            if time.monotonic() >= deadline:
                logger.info("No chat list items found after %s seconds.", self.cfg.max_group_search_wait_seconds)
                return []

            logger.info("Waiting for chat list to populate before checking candidates.")
            time.sleep(1)

    @staticmethod
    def _normalize_group_name(value: str) -> str:
        return "".join(ch.lower() for ch in value if ch.isalnum())

    def exact_match(self, candidates: list[str]) -> str | None:
        target = self.cfg.whatsapp_group_name.strip()
        normalized_target = self._normalize_group_name(target)
        logger.debug("exact_match: target='%s' normalized='%s' candidates=%s", target, normalized_target, candidates)
        for candidate in candidates:
            candidate_text = candidate.strip()
            if candidate_text == target:
                return candidate_text
            if self._normalize_group_name(candidate_text) == normalized_target:
                return candidate_text
        return None

    def open_group(self, candidate_name: str) -> None:
        """Click the chat row whose title matches candidate_name."""
        # Try each row selector and match against the extracted title.
        for sel in self._ROW_SELECTORS:
            try:
                rows = self.page.locator(sel)
                for i in range(min(rows.count(), 40)):
                    row = rows.nth(i)
                    title = self._row_title(row)
                    if self._normalize_group_name(title) == self._normalize_group_name(candidate_name):
                        row.click()
                        logger.info("Opened group via selector '%s': %s", sel, candidate_name)
                        return
            except Exception:
                continue
        raise GroupSelectionError(f"Could not click the group row for: {candidate_name}")

    def verify_group(self, expected_name: str) -> bool:
        # Use the conversation header specifically — multiple <header> elements
        # exist on the page (chat list header, conversation header, etc.)
        # data-testid='conversation-header' is the one showing the open chat name.
        header_locator = self.page.locator("header[data-testid='conversation-header']")
        if not header_locator.count():
            # Fallback: any header that is NOT the chatlist header
            header_locator = self.page.locator("header").last
        header_text = header_locator.inner_text()
        logger.info("Header text after open: %s", header_text)
        return expected_name.lower() in header_text.lower()

    def wait_for_chat_to_load(self, timeout_seconds: int = 15) -> None:
        """Wait until the chat message pane is visible after opening a group."""
        # The main message list has data-testid='conversation-panel-messages'
        # or a div[role='application'] inside the conversation area.
        selectors = [
            "div[data-testid='conversation-panel-messages']",
            "div[role='application']",
            "div[data-testid='msg-container']",
        ]
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            for sel in selectors:
                try:
                    if self.page.locator(sel).count():
                        logger.info("Chat messages pane loaded (selector: %s).", sel)
                        return
                except Exception:
                    pass
            time.sleep(0.5)
        logger.warning("Chat messages pane did not confirm load within %s seconds; continuing anyway.", timeout_seconds)

    def run(self) -> str:
        if not self.cfg.whatsapp_group_name:
            raise GroupSelectionError("WHATSAPP_GROUP_NAME is not configured.")

        self.search_group()
        # Try an initial candidate pass.
        candidates = self.find_group_candidates()
        exact = self.exact_match(candidates)
        if not exact:
            # Allow a second, user-driven window where they can make the group visible
            # (click the chat or unarchive) before we fail. During this window we poll
            # for changes and take a screenshot before raising an error to aid debugging.
            extra_wait = min(int(self.cfg.max_group_search_wait_seconds), 30)
            deadline = time.monotonic() + extra_wait
            target = self.cfg.whatsapp_group_name.strip()
            while time.monotonic() < deadline:
                logger.info("No exact match yet — waiting %s more seconds for user to reveal the group.",
                            int(deadline - time.monotonic()))
                time.sleep(1)
                candidates = self.find_group_candidates()
                exact = self.exact_match(candidates)
                if exact:
                    break

            if not exact:
                logger.warning("Attempting fallback searches for '%s' before failing.", target)
                try:
                    # Try multiple fallback locator strategies to handle DOM differences.
                    fallback_selectors = [
                        f"text={target}",
                        f"xpath=//*[contains(normalize-space(string(.)), '{target}')]",
                        "div[role='listitem']",
                        "div[role='row']",
                        "div[role='option']",
                    ]
                    clicked = False
                    for sel in fallback_selectors:
                        try:
                            loc = self.page.locator(sel)
                            if loc.count():
                                # find first visible and click
                                for i in range(min(loc.count(), 10)):
                                    candidate = loc.nth(i)
                                    try:
                                        if candidate.is_visible():
                                            logger.info("Fallback: clicking selector %s", sel)
                                            candidate.click()
                                            clicked = True
                                            break
                                    except Exception:
                                        continue
                            if clicked:
                                break
                        except Exception:
                            logger.debug("Fallback selector %s raised", sel)

                    if clicked:
                        # verify header
                        if self.verify_group(target):
                            logger.info("Fallback succeeded: opened group '%s'", target)
                            return target
                        else:
                            logger.debug("Fallback clicked but header verification failed.")
                except Exception as e:
                    logger.debug("Fallback searches raised an exception: %s", e)

                logger.error("No exact group match found for '%s'. Search results were empty or did not match the target group.", target)
                # Save a screenshot to help the user debug why the group wasn't visible.
                try:
                    path = Path("./screenshots")
                    path.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    file_path = path / f"group_lookup_{stamp}.png"
                    self.page.screenshot(path=str(file_path), full_page=True)
                    logger.info("Saved group lookup screenshot: %s", file_path)
                    raise GroupSelectionError(
                        f"No exact group match found for '{target}'. Screenshot saved: {file_path}"
                    )
                except Exception:
                    raise GroupSelectionError(
                        f"No exact group match found for '{target}'. Also failed to capture screenshot."
                    )

        self.open_group(exact)
        if not self.verify_group(self.cfg.whatsapp_group_name):
            logger.error("Wrong group opened or verification failed.")
            raise GroupSelectionError("Group verification failed; target group was not opened.")

        logger.info("Verified target group: %s", self.cfg.whatsapp_group_name)
        self.wait_for_chat_to_load()
        return self.cfg.whatsapp_group_name
