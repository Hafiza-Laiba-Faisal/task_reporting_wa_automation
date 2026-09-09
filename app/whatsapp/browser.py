from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from app.config import settings
from app.logger import get_logger

logger = get_logger("browser")


class WhatsAppBrowser:
    def __init__(self) -> None:
        self.cfg = settings()
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def open(self) -> Page:
        self.playwright = sync_playwright().start()

        profile_path = self.cfg.whatsapp_profile_path
        if profile_path:
            # Use persistent context so the WhatsApp session (QR scan) is saved
            # and reused across runs — no re-scan needed every time.
            profile_dir = Path(profile_path).expanduser().resolve()
            profile_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Using persistent browser profile at: %s", profile_dir)
            self.context = self.playwright.chromium.launch_persistent_context(
                str(profile_dir),
                headless=False,
                channel="chrome",
                viewport={"width": 1600, "height": 1100},
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self.browser = None  # persistent context owns itself
        else:
            # Fallback: ephemeral context (QR scan required every run)
            self.browser = self.playwright.chromium.launch(headless=False)
            self.context = self.browser.new_context(viewport={"width": 1600, "height": 1100})

        self.page = self.context.new_page()
        self.page.goto(self.cfg.whatsapp_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(10000)
        logger.info("WhatsApp Web opened.")
        return self.page

    def wait_until_loaded(self, timeout_seconds: int | None = None) -> None:
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        selector = "input[placeholder*='Search'], input[aria-label*='Search']"
        while True:
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            try:
                if self.page.locator(selector).count() and self.page.locator(selector).first.is_visible():
                    logger.info("WhatsApp Web ready.")
                    return
            except Exception:
                pass
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"WhatsApp Web was not ready within {timeout_seconds} seconds.")
            logger.info("Waiting for WhatsApp login/session to finish before continuing.")
            time.sleep(2)

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
        if self.browser is not None:
            self.browser.close()
        if self.playwright is not None:
            self.playwright.stop()
        logger.info("Browser closed.")

    def take_screenshot(self, name: str) -> str:
        if self.page is None:
            raise RuntimeError("Page is not available for screenshot")
        file_path = Path("./screenshots") / f"{name}.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(file_path), full_page=True)
        logger.info("Screenshot saved: %s", file_path)
        return str(file_path)
