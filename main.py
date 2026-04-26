"""
╔══════════════════════════════════════════════════════════════╗
║            Rubika Multi-Tool Bot — main.py                  ║
║  YouTube · Instagram · Pinterest · Screenshot · Web DL      ║
║  Telegram Monitor · New Configs · GitHub Actions 24/7       ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
from typing import Any

from rubpy import BotClient
from rubpy.bot.filters import text as text_filter
from rubpy.bot.enums import ChatKeypadTypeEnum

from config import BOT_TOKEN, TEMP_DIR
from database import init_db
from keyboards import BTN, main_menu
import handlers.youtube as yt
import handlers.instagram as ig
import handlers.pinterest as pin
import handlers.screenshot as ss
import handlers.website as web
import handlers.telegram_monitor as tgm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

os.makedirs(TEMP_DIR, exist_ok=True)

bot = BotClient(token=BOT_TOKEN)


# ══════════════════════════════════════════════════════════════
#  TEXTS
# ══════════════════════════════════════════════════════════════

WELCOME_TEXT = """
🤖 **به ربات چند‌ابزاره روبیکا خوش آمدید!**

از منو زیر یک گزینه را انتخاب کنید:

📥 **یوتیوب** — دانلود ویدیو و موسیقی
📸 **اینستاگرام** — دانلود پست، ریلز و استوری
📌 **پینترست** — دانلود عکس و ویدیو
🖥️ **اسکرین‌شات** — عکس از هر سایتی
💾 **دانلود سایت** — آفلاین کردن یا دانلود فایل
📢 **مانیتور تلگرام** — دریافت و هشدار کانال‌های عمومی
🔗 **کانفیگ‌های جدید** — آخرین کانفیگ‌های VPN

━━━━━━━━━━━━━━━━━━━━━━━
✨ _ساخته شده با ❤️_
"""

HELP_TEXT = """
ℹ️ **راهنمای ربات**

━━━━━━━━━━━━━━━━━━━━━━━

**📥 دانلود یوتیوب**
لینک ویدیو را ارسال کنید و کیفیت را انتخاب کنید.
حداکثر حجم: 48 مگابایت

**📸 دانلود اینستاگرام**
لینک پست یا ریلز از پروفایل‌های عمومی.

**📌 دانلود پینترست**
لینک پین عمومی.

**🖥️ اسکرین‌شات**
آدرس سایت را ارسال کنید، تصویر کامل صفحه.

**💾 دانلود سایت**
• آفلاین: HTML+CSS+JS را به صورت ZIP دانلود می‌کند
• فایل مستقیم: هر URL فایلی را دانلود می‌کند

**📢 مانیتور تلگرام**
آی‌دی کانال عمومی تلگرام را بدهید.
هشدار فعال کنید تا پیام‌های جدید دریافت کنید.

**🔗 کانفیگ‌های جدید**
آخرین کانفیگ‌های VPN از کانال‌های انتخاب شده.

━━━━━━━━━━━━━━━━━━━━━━━
🔧 /start — بازگشت به منوی اصلی
"""


# ══════════════════════════════════════════════════════════════
#  COMPAT LAYER
# ══════════════════════════════════════════════════════════════

def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _extract_chat_id(message: Any) -> Any:
    chat_id = _get_attr(message, "chat_id", "chat", "chat_guid", "dialog_id")
    if chat_id is None and hasattr(message, "peer"):
        chat_id = getattr(message.peer, "chat_id", None) or getattr(message.peer, "guid", None)
    return chat_id


def _extract_text(message: Any) -> str:
    text = _get_attr(message, "text", "raw_text", "caption", default="") or ""
    return str(text).strip()


class UpdateContext:
    """
    Small compatibility wrapper.

    Your old code expected:
      - update.new_message
      - update.chat_id
      - update.reply(...)

    rubpy BotClient handlers actually give:
      - client, message

    This wrapper keeps the older shape alive.
    """

    def __init__(self, message: Any):
        self.new_message = message

    @property
    def chat_id(self) -> Any:
        return _extract_chat_id(self.new_message)

    @property
    def text(self) -> str:
        return _extract_text(self.new_message)

    @property
    def raw_text(self) -> str:
        return self.text

    async def reply(self, *args, **kwargs):
        return await self.new_message.reply(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self.new_message, item)


# ══════════════════════════════════════════════════════════════
#  STATE ROUTER
# ══════════════════════════════════════════════════════════════

STATE_HANDLERS = {
    yt.STATE_WAIT_URL: yt.on_youtube_url,
    yt.STATE_WAIT_QUALITY: yt.on_youtube_quality,
    ig.STATE_WAIT_URL: ig.on_instagram_url,
    pin.STATE_WAIT_URL: pin.on_pinterest_url,
    ss.STATE_WAIT_URL: ss.on_screenshot_url,
    web.STATE_WAIT_MODE: web.on_website_mode_select,
    web.STATE_WAIT_OFFLINE: web.on_offline_url,
    web.STATE_WAIT_FILE: web.on_file_url,
    tgm.STATE_WAIT_CHANNEL: tgm.on_tg_channel_input,
}


async def _route_by_state(update: UpdateContext, bot_client: Any, state: str, text: str) -> bool:
    from database import reset_state

    if text in (BTN.CANCEL, BTN.BACK, "/start"):
        await reset_state(update.chat_id)
        await update.reply(
            WELCOME_TEXT if text == "/start" else "🏠 به منوی اصلی بازگشتید.",
            chat_keypad=main_menu(),
            chat_keypad_type=ChatKeypadTypeEnum.NEW,
        )
        return True

    handler = STATE_HANDLERS.get(state)
    if handler:
        await handler(update, bot_client)
        return True

    return False


# ══════════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════

@bot.on_update(text_filter)
async def on_message(client, message):
    from database import get_state, log_action, reset_state

    update = UpdateContext(message)
    _bot = client if client is not None else bot

    text = update.text
    if not text:
        return

    chat_id = update.chat_id
    if chat_id is None:
        logger.warning("Could not resolve chat_id for incoming message.")
        return

    user_state = await get_state(chat_id)
    state = user_state.get("state", "main")

    if state != "main":
        handled = await _route_by_state(update, _bot, state, text)
        if handled:
            return

    match text:
        case "/start" | "🔙 بازگشت به منوی اصلی" | "❌ لغو و بازگشت به منو":
            await reset_state(chat_id)
            await update.reply(
                WELCOME_TEXT,
                chat_keypad=main_menu(),
                chat_keypad_type=ChatKeypadTypeEnum.NEW,
            )

        case BTN.YOUTUBE:
            await log_action(chat_id, "youtube_start")
            await yt.on_youtube_start(update, _bot)

        case BTN.INSTAGRAM:
            await log_action(chat_id, "instagram_start")
            await ig.on_instagram_start(update, _bot)

        case BTN.PINTEREST:
            await log_action(chat_id, "pinterest_start")
            await pin.on_pinterest_start(update, _bot)

        case BTN.SCREENSHOT:
            await log_action(chat_id, "screenshot_start")
            await ss.on_screenshot_start(update, _bot)

        case BTN.WEBSITE_DL:
            await log_action(chat_id, "website_start")
            await web.on_website_start(update, _bot)

        case BTN.TELEGRAM_MON:
            await log_action(chat_id, "tg_monitor_start")
            await tgm.on_telegram_monitor_start(update, _bot)

        case BTN.NEW_CONFIGS:
            await log_action(chat_id, "new_configs")
            await tgm.on_new_configs(update, _bot)

        case BTN.HELP:
            await update.reply(HELP_TEXT, chat_keypad=main_menu())

        case BTN.STATS:
            from database import get_user_count
            count = await get_user_count()
            await update.reply(
                f"📊 **آمار ربات**\n\n👥 تعداد کاربران: **{count}**",
                chat_keypad=main_menu(),
            )

        case BTN.TG_ADD:
            await tgm.on_tg_add_channel(update, _bot)

        case BTN.TG_LIST:
            await tgm.on_tg_list_channels(update, _bot)

        case _:
            await update.reply(
                "🤔 متوجه نشدم! لطفاً از دکمه‌های منو استفاده کنید.",
                chat_keypad=main_menu(),
            )


# ══════════════════════════════════════════════════════════════
#  STARTUP & BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════

@bot.on_start()
async def on_start(client):
    logger.info("🚀 Bot starting up...")
    await init_db()
    logger.info("✅ Database initialized")

    shutdown_event = asyncio.Event()
    client._shutdown_event = shutdown_event

    asyncio.create_task(tgm.alert_loop(client), name="tg_alert_loop")
    logger.info("📡 Telegram alert loop task created")

    from utils.restart import watchdog_loop
    asyncio.create_task(watchdog_loop(client, shutdown_event), name="watchdog")
    logger.info("⏱  Watchdog task created")

    logger.info("✅ Bot is fully online and ready!")


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN is not set! Check your .env or environment variables.")
    logger.info("🤖 Starting Rubika Multi-Tool Bot (rubpy v7.x)")
    bot.run()
