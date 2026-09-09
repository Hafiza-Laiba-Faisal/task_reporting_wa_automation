from __future__ import annotations

import sys
from datetime import datetime

from app.config import settings
from app.database.repository import init_db
from app.logger import get_logger
from app.pipeline.processor import TaskProcessor
from app.whatsapp.browser import WhatsAppBrowser
from app.whatsapp.group_finder import GroupFinder
from app.whatsapp.message_collector import MessageCollector

logger = get_logger("main")


def run() -> None:
    cfg = settings()
    if not cfg.whatsapp_group_name:
        raise ValueError("WHATSAPP_GROUP_NAME must be set in the environment or .env file.")

    init_db()
    browser = WhatsAppBrowser()
    page = browser.open()
    try:
        browser.wait_until_loaded()
        finder = GroupFinder(page)
        finder.run()
        collector = MessageCollector(page, run_id=f"run-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        messages = collector.collect()
        processor = TaskProcessor(messages)
        processor.run()
        logger.info("Pipeline completed successfully.")
    finally:
        browser.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # pragma: no cover
        logger.exception("Unhandled pipeline error: %s", exc)
        sys.exit(1)
