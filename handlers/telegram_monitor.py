"""
Telegram Public Channel Monitor
Scrapes t.me/s/{channel} — no API key or account needed.
Supports:
  • View latest N messages from any public channel
  • Background alert loop: notify user when new message appears
"""

import asyncio
import re
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import CONFIG_CHANNELS, MONITOR_POLL_INTERVAL
from keyboards import (
    cancel_menu, main_menu, telegram_monitor_menu,
    channel_actions_menu, config_channels_menu, BTN,
)

logger = logging.getLogger(__name__)

STATE_WAIT_CHANNEL   = "tg_wait_channel"
STATE_CHANNEL_DETAIL = "tg_channel_detail"   # state_data = {"channel": "chan_name"}
STATE_WAIT_MSG_COUNT = "tg_wait_msg_count"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_MESSAGES_PER_REQUEST = 10   # Telegram preview page usually shows ~20


# ─── Scraper ──────────────────────────────────────────────────────────────────

def _fetch_channel_messages(channel: str, limit: int = 10) -> list[dict]:
    """
    Scrape t.me/s/{channel} and return list of dicts:
      {text, link, has_media, date}
    """
    url  = f"https://t.me/s/{channel.lstrip('@')}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code == 404:
        raise ValueError(f"کانال @{channel} پیدا نشد یا عمومی نیست.")
    resp.raise_for_status()

    soup     = BeautifulSoup(resp.text, "html.parser")
    bubbles  = soup.find_all("div", class_="tgme_widget_message_wrap", limit=40)

    messages = []
    for bubble in reversed(bubbles[-limit:]):
        text_div  = bubble.find("div", class_="tgme_widget_message_text")
        date_tag  = bubble.find("a", class_="tgme_widget_message_date")
        media_div = bubble.find("div", class_=re.compile(r"tgme_widget_message_(photo|video|document)"))

        text      = text_div.get_text("\n", strip=True) if text_div else ""
        link      = date_tag["href"] if date_tag and date_tag.get("href") else ""
        date_str  = ""
        if date_tag:
            time_tag = date_tag.find("time")
            if time_tag:
                date_str = time_tag.get("datetime", "")[:16].replace("T", " ")

        if text or media_div:
            messages.append({
                "text":      text[:600] if text else "[ رسانه / فایل ]",
                "link":      link,
                "has_media": bool(media_div),
                "date":      date_str,
            })

    return messages


def _get_latest_link(channel: str) -> Optional[str]:
    """Return the link of the most recent message, or None."""
    try:
        msgs = _fetch_channel_messages(channel, limit=1)
        return msgs[-1]["link"] if msgs else None
    except Exception:
        return None


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def on_telegram_monitor_start(update, bot):
    from database import set_state
    await set_state(update.chat_id, STATE_WAIT_CHANNEL)
    await update.reply(
        "📢 **مانیتور کانال تلگرام**\n\nانتخاب کنید:",
        chat_keypad=telegram_monitor_menu(),
    )


async def on_tg_add_channel(update, bot):
    from database import set_state
    await set_state(update.chat_id, STATE_WAIT_CHANNEL)
    await update.reply(
        "➕ **اضافه کردن کانال**\n\n"
        "آی‌دی کانال عمومی تلگرام را ارسال کنید:\n\n"
        "📝 مثال: `v2ray_free` یا `@v2ray_free`",
        chat_keypad=cancel_menu(),
    )


async def on_tg_channel_input(update, bot):
    from database import add_monitored_channel, reset_state, get_user_channels

    chat_id = update.chat_id
    channel = (update.new_message.text or "").strip().lstrip("@")

    if not channel or len(channel) < 3:
        await update.reply("❌ آی‌دی کانال معتبر نیست.", chat_keypad=cancel_menu())
        return

    status = await bot.send_message(chat_id, f"🔍 در حال بررسی کانال @{channel}...")

    try:
        loop  = asyncio.get_event_loop()
        msgs  = await loop.run_in_executor(None, _fetch_channel_messages, channel, 1)
        added = await add_monitored_channel(chat_id, channel)

        if added:
            text = f"✅ کانال **@{channel}** با موفقیت اضافه شد!\n"
        else:
            text = f"ℹ️ کانال **@{channel}** قبلاً اضافه شده بود.\n"

        await bot.edit_message_text(chat_id, status.message_id, text)
    except Exception as exc:
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا: {str(exc)[:200]}")
    finally:
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())


async def on_tg_list_channels(update, bot):
    from database import get_user_channels

    chat_id  = update.chat_id
    channels = await get_user_channels(chat_id)

    if not channels:
        await update.reply(
            "📋 شما هنوز کانالی اضافه نکرده‌اید.\n\n"
            "از دکمه «➕ اضافه کردن کانال» استفاده کنید.",
            chat_keypad=telegram_monitor_menu(),
        )
        return

    lines = ["📋 **کانال‌های شما:**\n"]
    for ch, last_link, alert_on in channels:
        alert_icon = "🔔" if alert_on else "🔕"
        lines.append(f"{alert_icon} @{ch}")

    await update.reply(
        "\n".join(lines) + "\n\nبرای مدیریت یک کانال، آی‌دی آن را ارسال کنید.",
        chat_keypad=telegram_monitor_menu(),
    )


async def on_new_configs(update, bot):
    """Show predefined config channels & fetch their latest message."""
    chat_id  = update.chat_id
    channels = CONFIG_CHANNELS

    if not channels:
        await update.reply("⚠️ هیچ کانال کانفیگی تعریف نشده است.", chat_keypad=main_menu())
        return

    status = await bot.send_message(
        chat_id,
        f"🔗 در حال دریافت آخرین کانفیگ‌ها از {len(channels)} کانال...",
    )

    results = []
    loop    = asyncio.get_event_loop()

    for channel in channels:
        try:
            msgs = await loop.run_in_executor(None, _fetch_channel_messages, channel, 3)
            if msgs:
                results.append((channel, msgs))
        except Exception as exc:
            results.append((channel, None))

    await bot.edit_message_text(chat_id, status.message_id,
                                "✅ دریافت شد! در حال ارسال...")

    for channel, msgs in results:
        if msgs is None:
            await bot.send_message(chat_id, f"❌ @{channel}: خطا در دریافت")
            continue

        header = f"📡 **@{channel}** — آخرین پیام‌ها:\n{'─' * 30}\n"
        body   = ""
        for i, m in enumerate(msgs, 1):
            media_tag = "📎 " if m["has_media"] else ""
            link_tag  = f"\n🔗 {m['link']}" if m["link"] else ""
            body      += f"**[{i}]** {media_tag}{m['text'][:300]}{link_tag}\n\n"

        await bot.send_message(chat_id, header + body)
        await asyncio.sleep(0.5)

    await bot.send_message(chat_id, "✅ همه کانفیگ‌ها ارسال شدند.", chat_keypad=main_menu())


async def on_tg_get_channel_messages(update, bot, channel: str, count: int = 5):
    """Fetch and send last N messages from a specific channel."""
    chat_id = update.chat_id
    status  = await bot.send_message(chat_id, f"⏳ در حال دریافت پیام‌های @{channel}...")

    try:
        loop = asyncio.get_event_loop()
        msgs = await loop.run_in_executor(None, _fetch_channel_messages, channel, count)

        if not msgs:
            await bot.edit_message_text(chat_id, status.message_id,
                                        f"⚠️ هیچ پیامی در @{channel} پیدا نشد.")
            return

        await bot.edit_message_text(chat_id, status.message_id,
                                    f"📨 آخرین {len(msgs)} پیام از @{channel}:")

        for i, m in enumerate(msgs, 1):
            media_tag = "📎 " if m["has_media"] else ""
            link_part = f"\n🔗 {m['link']}" if m["link"] else ""
            date_part = f"\n🕒 {m['date']}" if m["date"] else ""
            text      = (
                f"**[{i}/{len(msgs)}]** @{channel}\n"
                f"{media_tag}{m['text'][:500]}"
                f"{date_part}{link_part}"
            )
            await bot.send_message(chat_id, text)
            await asyncio.sleep(0.3)

    except Exception as exc:
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا: {str(exc)[:200]}")


# ─── Background Alert Loop ────────────────────────────────────────────────────

async def alert_loop(bot):
    """
    Runs forever in background.
    Every MONITOR_POLL_INTERVAL seconds checks subscribed channels for new messages.
    """
    from database import get_all_alert_subs, update_last_msg_link

    logger.info("📡 Telegram alert loop started (interval=%ds)", MONITOR_POLL_INTERVAL)
    loop = asyncio.get_event_loop()

    while True:
        try:
            subs = await get_all_alert_subs()
            for chat_id, channel, last_link in subs:
                try:
                    msgs = await loop.run_in_executor(
                        None, _fetch_channel_messages, channel, 1
                    )
                    if not msgs:
                        continue

                    latest = msgs[-1]
                    if latest["link"] and latest["link"] != last_link:
                        # New message detected!
                        media_tag = "📎 " if latest["has_media"] else ""
                        alert_text = (
                            f"🔔 **پیام جدید در @{channel}**\n\n"
                            f"{media_tag}{latest['text'][:400]}\n"
                            f"🔗 {latest['link']}"
                        )
                        await bot.send_message(chat_id, alert_text)
                        await update_last_msg_link(chat_id, channel, latest["link"])

                except Exception as exc:
                    logger.warning("Alert loop error for %s/%s: %s", chat_id, channel, exc)

                await asyncio.sleep(1)   # small delay between channels

        except Exception as exc:
            logger.error("Alert loop outer error: %s", exc)

        await asyncio.sleep(MONITOR_POLL_INTERVAL)
