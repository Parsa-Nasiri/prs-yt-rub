"""
GitHub Actions Self-Restart Utility
Triggers a new workflow dispatch before the 6-hour GitHub Actions limit.
"""

import time
import asyncio
import logging
import requests

from config import (
    GITHUB_TOKEN,
    GITHUB_REPOSITORY,
    GITHUB_BRANCH,
    GITHUB_WORKFLOW_FILE,
    MAX_RUNTIME_SECONDS,
)

logger = logging.getLogger(__name__)


def trigger_github_workflow() -> bool:
    """
    Dispatch a new run of the bot workflow via GitHub API.
    Returns True on success.
    """
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        logger.warning("GITHUB_TOKEN or GITHUB_REPOSITORY not set — cannot auto-restart.")
        return False

    url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
        f"/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
    )
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": GITHUB_BRANCH}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code in (204, 200):
            logger.info("✅ New workflow dispatched successfully.")
            return True
        else:
            logger.error(
                "❌ Workflow dispatch failed: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as exc:
        logger.error("❌ Workflow dispatch exception: %s", exc)
        return False


async def watchdog_loop(bot, shutdown_event: asyncio.Event):
    """
    Runs in background. Starts the clock when called (i.e. after the bot
    is fully online), so MAX_RUNTIME_SECONDS reflects actual serving time.

    When the limit is reached:
      1. Triggers a new GitHub Actions workflow run
      2. Notifies admins
      3. Sets shutdown_event → bot exits gracefully
    """
    from config import ADMIN_IDS

    # Clock starts NOW — after startup is complete, not at module import.
    start_time = time.monotonic()

    logger.info(
        "⏱  Watchdog started — will restart after %dh %dm of serving time",
        MAX_RUNTIME_SECONDS // 3600,
        (MAX_RUNTIME_SECONDS % 3600) // 60,
    )

    check_interval = 60  # check every 60 seconds

    while not shutdown_event.is_set():
        await asyncio.sleep(check_interval)

        elapsed = time.monotonic() - start_time
        remaining = MAX_RUNTIME_SECONDS - elapsed

        if remaining <= 0:
            logger.info("⏰ Runtime limit reached — initiating graceful restart...")

            # Trigger new run FIRST so the new instance starts its setup
            # while this one is still alive (minimises downtime gap).
            success = trigger_github_workflow()

            # Notify admins
            for admin_id in ADMIN_IDS:
                if admin_id:
                    try:
                        status = "✅ جاب جدید راه‌اندازی شد." if success else "⚠️ راه‌اندازی جاب جدید ناموفق بود."
                        await bot.send_message(
                            admin_id,
                            "⚙️ **ربات در حال ری‌استارت خودکار است**\n"
                            f"دلیل: محدودیت زمانی GitHub Actions\n"
                            f"{status}\n"
                            "⏳ چند ثانیه صبر کنید...",
                        )
                    except Exception:
                        pass

            if success:
                logger.info("✅ Restart workflow triggered. Shutting down current instance.")
            else:
                logger.warning("⚠️  Could not trigger restart. Shutting down anyway.")

            shutdown_event.set()
            break

        # Log a reminder every hour
        if int(elapsed) % 3600 < check_interval:
            logger.info(
                "⏱  Watchdog: %.0f min elapsed, %.0f min remaining before restart",
                elapsed / 60,
                remaining / 60,
            )
