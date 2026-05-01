"""
╔══════════════════════════════════════════════════════════════╗
║            Rubika Multi-Tool Bot — main.py                   ║
║  YouTube · Instagram · Pinterest · Screenshot · Web DL       ║
║  Telegram Monitor · New Configs · GitHub Actions 24/7        ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os

from rubpy import BotClient
from rubpy.bot.enums import ChatKeypadTypeEnum

from config import BOT_TOKEN, TEMP_DIR
from database import init_db
from keyboards import BTN, main_menu, cancel_menu, back_menu
import handlers.youtube         as yt
import handlers.instagram       as ig
import handlers.pinterest       as pin
import handlers.screenshot      as ss
import handlers.website         as web
import handlers.telegram_monitor as tgm

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
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
آدرس سایت را ارسال کنید — تصویر کامل صفحه.

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
#  STATE ROUTER
# ══════════════════════════════════════════════════════════════

STATE_HANDLERS = {
    # YouTube
    yt.STATE_WAIT_URL:      yt.on_youtube_url,
    yt.STATE_WAIT_QUALITY:  yt.on_youtube_quality,
    # Instagram
    ig.STATE_WAIT_URL:      ig.on_instagram_url,
    # Pinterest
    pin.STATE_WAIT_URL:     pin.on_pinterest_url,
    # Screenshot
    ss.STATE_WAIT_URL:      ss.on_screenshot_url,
    # Website
    web.STATE_WAIT_MODE:    web.on_website_mode_select,
    web.STATE_WAIT_OFFLINE: web.on_offline_url,
    web.STATE_WAIT_FILE:    web.on_file_url,
    # Telegram Monitor
    tgm.STATE_WAIT_CHANNEL: tgm.on_tg_channel_input,
}


async def _route_by_state(update, bot, state: str, text: str):
    """Dispatch to the correct handler based on current user state."""

    # ── Cancel / Back ──────────────────────────────────────
    if text in (BTN.CANCEL, BTN.BACK, "/start"):
        from database import reset_state
        await reset_state(update.chat_id)
        await update.reply(
            "🏠 به منوی اصلی بازگشتید." if text != "/start" else WELCOME_TEXT,
            chat_keypad=main_menu(),
            chat_keypad_type=ChatKeypadTypeEnum.NEW,
        )
        return True

    handler = STATE_HANDLERS.get(state)
    if handler:
        await handler(update, bot)
        return True

    return False


# ══════════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════

@bot.on_update()
async def on_message(update):
    from database import get_state, log_action, reset_state

    try:
        # Handle text messages
        if update.new_message and update.new_message.text:
            chat_id = update.chat_id
            text    = (update.new_message.text or "").strip()
            
            if not text:
                return
        else:
            # No text message to process
            return

        # ── Fetch user state ──────────────────────────────────
        user_state = await get_state(chat_id)
        state      = user_state["state"]

        # ── If user is in a sub-flow, route there ─────────────
        if state != "main":
            handled = await _route_by_state(update, bot, state, text)
            if handled:
                return

        # ── Main menu routing ─────────────────────────────────
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
                await yt.on_youtube_start(update, bot)

            case BTN.INSTAGRAM:
                await log_action(chat_id, "instagram_start")
                await ig.on_instagram_start(update, bot)

            case BTN.PINTEREST:
                await log_action(chat_id, "pinterest_start")
                await pin.on_pinterest_start(update, bot)

            case BTN.SCREENSHOT:
                await log_action(chat_id, "screenshot_start")
                await ss.on_screenshot_start(update, bot)

            case BTN.WEBSITE_DL:
                await log_action(chat_id, "website_start")
                await web.on_website_start(update, bot)

            case BTN.TELEGRAM_MON:
                await log_action(chat_id, "tg_monitor_start")
                await tgm.on_telegram_monitor_start(update, bot)

            case BTN.NEW_CONFIGS:
                await log_action(chat_id, "new_configs")
                await tgm.on_new_configs(update, bot)

            case BTN.HELP:
                await update.reply(HELP_TEXT, chat_keypad=main_menu())

            case BTN.STATS:
                from database import get_user_count
                count = await get_user_count()
                await update.reply(
                    f"📊 **آمار ربات**\n\n👥 تعداد کاربران: **{count}**",
                    chat_keypad=main_menu(),
                )

            # Telegram monitor sub-menu buttons
            case BTN.TG_ADD:
                await tgm.on_tg_add_channel(update, bot)

            case BTN.TG_LIST:
                await tgm.on_tg_list_channels(update, bot)

            case _:
                # Unknown input in main state
                await update.reply(
                    "🤔 متوجه نشدم! لطفاً از دکمه‌های منو استفاده کنید.",
                    chat_keypad=main_menu(),
                )
    except Exception as exc:
        logger.error("❌ Error in message handler for chat_id %s: %s", chat_id if 'chat_id' in locals() else 'unknown', exc, exc_info=True)
        try:
            await update.reply(
                f"❌ خطا در پردازش پیام:\n{str(exc)[:100]}",
                chat_keypad=main_menu(),
            )
        except Exception as reply_exc:
            logger.error("❌ Failed to send error message: %s", reply_exc)


# ══════════════════════════════════════════════════════════════
#  STARTUP & BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════

@bot.on_start
async def on_start(client):
    logger.info("🚀 Bot starting up...")
    await init_db()
    logger.info("✅ Database initialized")

    shutdown_event = asyncio.Event()
    client._shutdown_event = shutdown_event

    # Start background tasks
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
        logger.error("\n" + "="*70)
        logger.error("❌ BOT_TOKEN is not set!")
        logger.error("\nFor GitHub Actions:")
        logger.error("  1. Go to Settings → Secrets and variables → Actions")
        logger.error("  2. Click 'New repository secret'")
        logger.error("  3. Add BOT_TOKEN with your Rubika bot token")
        logger.error("\nFor local testing:")
        logger.error("  1. Create .env file")
        logger.error("  2. Add: BOT_TOKEN=your_token_here")
        logger.error("="*70 + "\n")
        raise SystemExit("❌ BOT_TOKEN is not set! Check your .env or GitHub secrets.")
    logger.info("🤖 Starting Rubika Multi-Tool Bot (rubpy v7.x)")
    logger.info("✅ BOT_TOKEN loaded successfully")
    bot.run()
