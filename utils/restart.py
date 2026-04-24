"""
GitHub Actions Self-Restart Utility
Triggers a new workflow dispatch before the 6-hour GitHub Actions limit.
"""

import os
import time
import asyncio
import logging
import requests

from config import (
    HUB_TOKEN,
    GITHUB_REPOSITORY,
    GITHUB_BRANCH,
    GITHUB_WORKFLOW_FILE,
    MAX_RUNTIME_SECONDS,
)

logger = logging.getLogger(__name__)
_start_time: float = time.time()


def elapsed() -> float:
    return time.time() - _start_time


def should_restart() -> bool:
    return elapsed() >= MAX_RUNTIME_SECONDS


def trigger_github_workflow() -> bool:
    """
    Dispatch a new run of the bot workflow via GitHub API.
    Returns True on success.
    """
    if not HUB_TOKEN or not GITHUB_REPOSITORY:
        logger.warning("HUB_TOKEN or GITHUB_REPOSITORY not set — cannot auto-restart.")
        return False

    url     = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
    headers = {
        "Authorization": f"Bearer {HUB_TOKEN}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": GITHUB_BRANCH}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code in (204, 200):
            logger.info("✅ New workflow dispatched successfully.")
            return True
        else:
            logger.error("❌ Workflow dispatch failed: %s %s", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.error("❌ Workflow dispatch exception: %s", exc)
        return False


async def watchdog_loop(bot, shutdown_event: asyncio.Event):
    """
    Runs in background. When MAX_RUNTIME_SECONDS is reached:
      1. Notifies admins (optional)
      2. Triggers a new GitHub Actions run
      3. Sets shutdown_event → bot gracefully stops
    """
    from config import ADMIN_IDS

    logger.info(
        "⏱  Watchdog started — will restart after %dh %dm",
        MAX_RUNTIME_SECONDS // 3600,
        (MAX_RUNTIME_SECONDS % 3600) // 60,
    )

    check_interval = 60  # check every 60 seconds
    while not shutdown_event.is_set():
        await asyncio.sleep(check_interval)

        if should_restart():
            logger.info("⏰ Runtime limit reached — initiating graceful restart...")

            # Notify admins
            for admin_id in ADMIN_IDS:
                if admin_id:
                    try:
                        await bot.send_message(
                            admin_id,
                            "⚙️ **ربات در حال ری‌استارت خودکار است**\n"
                            "دلیل: محدودیت زمانی GitHub Actions\n"
                            "⏳ چند ثانیه صبر کنید...",
                        )
                    except Exception:
                        pass

            success = trigger_github_workflow()

            if success:
                logger.info("✅ Restart workflow triggered. Shutting down current instance.")
            else:
                logger.warning("⚠️  Could not trigger restart. Shutting down anyway.")

            shutdown_event.set()
            break
