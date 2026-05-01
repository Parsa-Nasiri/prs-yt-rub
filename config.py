"""
╔══════════════════════════════════════════╗
║       Rubika Multi-Tool Bot Config       ║
╚══════════════════════════════════════════╝
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Credentials ──────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ─── GitHub Actions Self-Restart ─────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPOSITORY: str = os.getenv("GITHUB_REPOSITORY", "")   # e.g. "username/rubika-bot"
GITHUB_BRANCH: str = os.getenv("GITHUB_BRANCH", "main")
GITHUB_WORKFLOW_FILE: str = os.getenv("GITHUB_WORKFLOW_FILE", "bot.yml")

# ─── Runtime Limit ───────────────────────────────────────
# GitHub Actions kills jobs after 6h, we restart at 5h40m (340 min)
# This ensures graceful restart and new job dispatch before hard limit
MAX_RUNTIME_SECONDS: int = int(os.getenv("MAX_RUNTIME_SECONDS", str(5 * 3600 + 40 * 60)))

# ─── File Settings ────────────────────────────────────────
TEMP_DIR: str = "/tmp/rubika_bot_files"
MAX_VIDEO_SIZE_MB: int = int(os.getenv("MAX_VIDEO_SIZE_MB", "48"))
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "48"))
DB_PATH: str = os.getenv("DB_PATH", "bot_data.db")

# ─── Admin IDs ────────────────────────────────────────────
ADMIN_IDS: list = [i.strip() for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

# ─── Predefined Telegram Config Channels ─────────────────
#   These appear when user presses "کانفیگ‌های جدید 🔗"
#   Add public Telegram channel usernames (without @)
CONFIG_CHANNELS: list = [
    ch.strip()
    for ch in os.getenv(
        "CONFIG_CHANNELS",
        "v2ray_free,v2rayng_config,v2ray_configs_pool"
    ).split(",")
    if ch.strip()
]

# ─── Website Download Settings ────────────────────────────
WEBSITE_DOWNLOAD_TIMEOUT: int = 30   # seconds
SCREENSHOT_TIMEOUT: int = 30         # seconds

# ─── Telegram Monitor Settings ────────────────────────────
MONITOR_POLL_INTERVAL: int = 120     # check every 2 minutes

# ─── Messages & Branding ─────────────────────────────────
BOT_NAME: str = "🤖 ربات چند‌ابزاره روبیکا"
